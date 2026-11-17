"""Upload transitions. Always lock StorageAccount before Upload/UploadAttempt."""
import errno
import logging
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone

from .errors import ApiError
from .models import File, StorageAccount, Upload, UploadAttempt
from .storage import LocalBlobStore

logger = logging.getLogger("drive")


def lease_deadline(now):
    return now + timedelta(seconds=settings.UPLOAD_LEASE_SECONDS)


def session_deadline(now):
    return now + timedelta(seconds=settings.UPLOAD_SESSION_SECONDS)


def account_for(user):
    account, _ = StorageAccount.objects.get_or_create(user=user)
    return account


def locked_account(user):
    account_for(user)
    return StorageAccount.objects.select_for_update().get(user=user)


def reconcile_locked(account, now):
    """Caller holds account lock. Lease fencing and reservation release are atomic."""
    changed = 0
    for upload in Upload.objects.select_for_update().filter(owner_id=account.user_id, state__in=Upload.ACTIVE).order_by("id"):
        if upload.lease_until is not None and upload.lease_until > now:
            continue
        account.reserved_bytes -= upload.expected_bytes
        upload.state = Upload.State.RETRYABLE
        upload.error_code = "upload_interrupted"
        upload.lease_until = None
        upload.generation += 1
        upload.save(update_fields=["state", "error_code", "lease_until", "generation", "updated_at"])
        upload.attempts.exclude(state=UploadAttempt.State.COMPLETE).update(state=UploadAttempt.State.FAILED, updated_at=now)
        changed += 1
    if changed:
        account.save(update_fields=["reserved_bytes"])
    changed += Upload.objects.filter(owner_id=account.user_id, state=Upload.State.RETRYABLE, expires_at__lte=now).update(state=Upload.State.EXPIRED, updated_at=now)
    return changed


def reconcile_user(user):
    with transaction.atomic():
        account = locked_account(user)
        return reconcile_locked(account, timezone.now())


def validate_name(name):
    try:
        valid_name = isinstance(name, str) and bool(name.strip()) and len(name.encode("utf-8")) <= 255
    except UnicodeEncodeError:
        valid_name = False
    if not valid_name:
        raise ApiError("invalid_name", "Use a file name between 1 and 255 UTF-8 bytes.")
    if any(ord(char) < 32 or ord(char) == 127 for char in name) or "/" in name or "\\" in name or not name.strip(". "):
        raise ApiError("invalid_name", "This file name is not supported.")
    return name


def validate_metadata(data):
    if not isinstance(data, dict):
        raise ApiError("invalid_metadata", "Choose one file to upload.")
    name = data.get("name")
    size = data.get("size_bytes")
    validate_name(name)
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise ApiError("invalid_size", "Choose a file that is not empty.")
    if size > settings.MAX_FILE_BYTES:
        raise ApiError("file_too_large", "The maximum file size is 100 MiB.", 413)
    try:
        key = uuid.UUID(str(data.get("client_key", "")))
    except (ValueError, AttributeError):
        raise ApiError("invalid_key", "The upload request is missing a valid identifier.") from None
    return name, size, key


def reserve(account, size):
    if account.used_bytes + account.reserved_bytes + size > account.quota_bytes:
        raise ApiError("quota_exceeded", "Your storage limit has been reached.", 507)
    account.reserved_bytes += size
    account.save(update_fields=["reserved_bytes"])


def create_upload(user, data):
    name, size, key = validate_metadata(data)
    now = timezone.now()
    with transaction.atomic():
        account = locked_account(user)
        reconcile_locked(account, now)
        existing = Upload.objects.filter(owner=user, client_key=key).first()
        if existing:
            if existing.display_name != name or existing.expected_bytes != size:
                raise ApiError("idempotency_mismatch", "This request identifier belongs to a different file.", 409)
            return existing, False
        active = Upload.objects.filter(owner=user, state__in=Upload.ACTIVE).first()
        if active:
            raise ApiError("upload_active", "Finish the active upload before starting another.", 409, upload_id=str(active.id))
        reserve(account, size)
        upload = Upload.objects.create(owner=user, client_key=key, display_name=name, expected_bytes=size, lease_until=lease_deadline(now), expires_at=session_deadline(now))
        return upload, True


def get_upload(user, upload_id):
    # Look up ownership before creating/locking any account rows.
    if not Upload.objects.filter(id=upload_id, owner=user).exists():
        raise ApiError("not_found", "Upload not found.", 404)
    reconcile_user(user)
    return Upload.objects.get(id=upload_id, owner=user)


def claim_attempt(user, upload_id, attempt_id):
    now = timezone.now()
    with transaction.atomic():
        account = locked_account(user)
        reconcile_locked(account, now)
        try:
            upload = Upload.objects.select_for_update().get(id=upload_id, owner=user)
        except Upload.DoesNotExist:
            raise ApiError("not_found", "Upload not found.", 404) from None
        if upload.state == Upload.State.COMPLETE:
            return upload, None
        if upload.state == Upload.State.EXPIRED:
            raise ApiError("upload_expired", "Choose your file again to start a new upload.", 410)
        if UploadAttempt.objects.filter(id=attempt_id).exists():
            raise ApiError("attempt_spent", "Check upload status before retrying with a new attempt.", 409, upload_id=str(upload.id))
        if upload.state in (Upload.State.RECEIVING, Upload.State.VERIFYING):
            raise ApiError("upload_active", "This upload is still in progress.", 409, upload_id=str(upload.id), retry_after_ms=1500)
        if upload.state == Upload.State.RETRYABLE:
            active = Upload.objects.filter(owner=user, state__in=Upload.ACTIVE).first()
            if active:
                raise ApiError("upload_active", "Another upload is in progress.", 409, upload_id=str(active.id))
            reserve(account, upload.expected_bytes)
        upload.generation += 1
        upload.state = Upload.State.RECEIVING
        upload.error_code = ""
        upload.received_bytes = 0
        upload.lease_until = lease_deadline(now)
        upload.expires_at = session_deadline(now)
        upload.save(update_fields=["generation", "state", "error_code", "received_bytes", "lease_until", "expires_at", "updated_at"])
        attempt = UploadAttempt.objects.create(id=attempt_id, upload=upload, generation=upload.generation, blob_key=attempt_id.hex)
        return upload, attempt


def assert_current(upload, attempt, now):
    if upload.generation != attempt.generation or upload.state not in (Upload.State.RECEIVING, Upload.State.VERIFYING) or upload.lease_until is None or upload.lease_until <= now:
        raise ApiError("stale_attempt", "This upload attempt expired. Check its status before retrying.", 409, upload_id=str(upload.id))


def checkpoint(user, upload_id, attempt, total, verifying=False):
    with transaction.atomic():
        locked_account(user)
        upload = Upload.objects.select_for_update().get(id=upload_id, owner=user)
        now = timezone.now()
        assert_current(upload, attempt, now)
        upload.received_bytes = total
        upload.lease_until = lease_deadline(now)
        if verifying:
            upload.state = Upload.State.VERIFYING
        upload.save(update_fields=["received_bytes", "lease_until", "state", "updated_at"])
        UploadAttempt.objects.filter(id=attempt.id).update(actual_bytes=total, state=UploadAttempt.State.VERIFYING if verifying else UploadAttempt.State.RECEIVING, updated_at=now)


def fail_attempt(user, upload_id, attempt, error_code="upload_interrupted"):
    with transaction.atomic():
        account = locked_account(user)
        upload = Upload.objects.select_for_update().get(id=upload_id, owner=user)
        # A stale worker must never change a later attempt or a committed result.
        if upload.generation != attempt.generation or upload.state not in Upload.ACTIVE:
            return
        account.reserved_bytes -= upload.expected_bytes
        account.save(update_fields=["reserved_bytes"])
        upload.state = Upload.State.RETRYABLE
        upload.error_code = error_code
        upload.lease_until = None
        upload.save(update_fields=["state", "error_code", "lease_until", "updated_at"])
        UploadAttempt.objects.filter(id=attempt.id).update(state=UploadAttempt.State.FAILED, updated_at=timezone.now())


def finalize(user, upload_id, attempt, total, checksum):
    with transaction.atomic():
        account = locked_account(user)
        upload = Upload.objects.select_for_update().get(id=upload_id, owner=user)
        assert_current(upload, attempt, timezone.now())
        if upload.state != Upload.State.VERIFYING or total != upload.expected_bytes:
            raise ApiError("invalid_finalization", "The upload could not be verified.", 409)
        file = File.objects.create(owner=user, upload=upload, successful_attempt=attempt, display_name=upload.display_name, byte_size=total, sha256=checksum, blob_key=attempt.blob_key)
        account.reserved_bytes -= total
        account.used_bytes += total
        account.save(update_fields=["reserved_bytes", "used_bytes"])
        upload.state = Upload.State.COMPLETE
        upload.lease_until = None
        upload.received_bytes = total
        upload.save(update_fields=["state", "lease_until", "received_bytes", "updated_at"])
        UploadAttempt.objects.filter(id=attempt.id).update(state=UploadAttempt.State.COMPLETE, actual_bytes=total, sha256=checksum, updated_at=timezone.now())
        return upload, file


def receive_upload(user, upload_id, attempt_id, stream):
    upload, attempt = claim_attempt(user, upload_id, attempt_id)
    if attempt is None:
        return upload
    try:
        store = LocalBlobStore()
        total, checksum = store.stage(stream, attempt.blob_key, upload.expected_bytes, lambda count, verifying=False: checkpoint(user, upload.id, attempt, count, verifying))
        store.publish(attempt.blob_key)
        upload, _ = finalize(user, upload.id, attempt, total, checksum)
        return upload
    except (ApiError, OSError, DatabaseError) as error:
        code = error.code if isinstance(error, ApiError) else "device_full" if isinstance(error, OSError) and error.errno in (errno.ENOSPC, errno.EDQUOT) else "storage_unavailable"
        try:
            fail_attempt(user, upload.id, attempt, code)
        except DatabaseError:
            # A database outage leaves the lease to be reconciled later.
            logger.warning("upload_failure_pending_reconciliation upload_id=%s", upload.id)
        if isinstance(error, ApiError):
            raise
        if isinstance(error, OSError) and error.errno in (errno.ENOSPC, errno.EDQUOT):
            raise ApiError("device_full", "This device is out of space.", 507) from error
        raise ApiError("storage_unavailable", "Upload confirmation is temporarily unavailable. Check its status.", 503) from error


def clean_orphans():
    """Only tracked, fenced attempts are collected. Unknown files are never guessed at."""
    cutoff = timezone.now() - timedelta(seconds=settings.ORPHAN_GRACE_SECONDS)
    candidates = UploadAttempt.objects.filter(state=UploadAttempt.State.FAILED, updated_at__lt=cutoff).values_list("id", "upload__owner_id", "upload_id")
    removed = 0
    store = LocalBlobStore()
    for attempt_id, owner_id, upload_id in candidates.iterator():
        with transaction.atomic():
            StorageAccount.objects.select_for_update().get(user_id=owner_id)
            upload = Upload.objects.select_for_update().get(id=upload_id)
            attempt = UploadAttempt.objects.select_for_update().get(id=attempt_id)
            if attempt.state != UploadAttempt.State.FAILED or attempt.updated_at >= cutoff or File.objects.filter(blob_key=attempt.blob_key).exists():
                continue
            if upload.generation == attempt.generation and upload.state in Upload.ACTIVE:
                continue
            # Holding the finalization locks makes unlink safe. A late fenced writer
            # can only leave another orphan; it cannot publish a File reference.
            store.remove_unreferenced(attempt.blob_key)
            removed += 1
    return removed
