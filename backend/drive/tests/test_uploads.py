import errno
import hashlib
import io
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

from django.db import DatabaseError, IntegrityError, close_old_connections, transaction
from django.core.management import call_command
from django.test import Client, TestCase, TransactionTestCase, override_settings
from django.utils import timezone

from drive import services
from drive.errors import ApiError
from drive.models import File, StorageAccount, Upload, UploadAttempt, User
from drive.storage import LocalBlobStore


TEST_SETTINGS = {
    "ALLOWED_HOSTS": ["testserver", "localhost", "127.0.0.1"],
    "PASSWORD_HASHERS": ["django.contrib.auth.hashers.MD5PasswordHasher"],
}


@override_settings(**TEST_SETTINGS)
class UploadContractTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="drive-backend-test-")
        self.addCleanup(self.temp.cleanup)
        self.override = override_settings(DRIVE_DATA_DIR=Path(self.temp.name))
        self.override.enable()
        self.addCleanup(self.override.disable)
        self.user = User.objects.create_user("owner", password="fixture-password-9273")
        self.other = User.objects.create_user("other", password="fixture-password-8251")
        self.client.force_login(self.user)

    def create(self, name="fixture.txt", body=b"private fixture", key=None):
        response = self.client.post("/api/uploads", {"name": name, "size_bytes": len(body), "client_key": str(key or uuid.uuid4())}, content_type="application/json")
        self.assertEqual(response.status_code, 201, response.content)
        return response.json()

    def put(self, upload, body=b"private fixture", attempt=None):
        return self.client.put(f"/api/uploads/{upload['id']}/content", body, content_type="application/octet-stream", HTTP_X_ATTEMPT_ID=str(attempt or uuid.uuid4()))

    def account(self):
        return StorageAccount.objects.get(user=self.user)

    def test_upload_is_private_persistent_and_charged_once(self):
        body = bytes(range(256)) * 4096
        key = uuid.uuid4()
        upload = self.create(body=body, key=key)
        duplicate = self.client.post("/api/uploads", {"name": "fixture.txt", "size_bytes": len(body), "client_key": str(key)}, content_type="application/json")
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(duplicate.json()["id"], upload["id"])
        attempt = uuid.uuid4()
        completed = self.put(upload, body, attempt)
        self.assertEqual(completed.status_code, 200, completed.content)
        file = completed.json()["file"]
        self.assertEqual(file["sha256"], hashlib.sha256(body).hexdigest())
        replay = self.put(upload, body, attempt)
        self.assertEqual(replay.status_code, 200)
        self.assertEqual(replay.json()["file"]["id"], file["id"])
        self.assertEqual(File.objects.count(), 1)
        self.assertEqual(self.account().used_bytes, len(body))
        self.assertEqual(self.account().reserved_bytes, 0)
        download = self.client.get(f"/api/files/{file['id']}/content")
        self.assertEqual(b"".join(download.streaming_content), body)
        self.assertIn("attachment", download["Content-Disposition"])
        self.assertEqual(download["Cache-Control"], "no-store")
        stored = File.objects.get(id=file["id"])
        self.assertEqual(stored.owner_id, stored.upload.owner_id)
        self.assertEqual(stored.successful_attempt.upload_id, stored.upload_id)
        self.assertTrue((Path(self.temp.name) / "blobs" / "objects" / stored.blob_key).is_file())

    def test_foreign_identity_cannot_list_status_write_or_download(self):
        upload = self.create()
        complete = self.put(upload).json()
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/api/files").json()["items"], [])
        self.assertEqual(self.client.get(f"/api/uploads/{upload['id']}").status_code, 404)
        self.assertEqual(self.put(upload).status_code, 404)
        self.assertEqual(self.client.get(f"/api/files/{complete['file']['id']}/content").status_code, 404)
        self.assertEqual(self.account().used_bytes, len(b"private fixture"))

    def test_short_upload_releases_quota_and_retry_never_duplicates(self):
        upload = self.create()
        attempt = uuid.uuid4()
        self.assertEqual(self.put(upload, b"short", attempt).status_code, 422)
        self.assertEqual(self.account().reserved_bytes, 0)
        status = self.client.get(f"/api/uploads/{upload['id']}").json()
        self.assertEqual(status["state"], "RETRYABLE")
        self.assertTrue(status["can_retry"])
        self.assertIsNone(status["file"])
        self.assertEqual(self.put(upload, attempt=attempt).status_code, 409)
        retried = self.put(upload)
        self.assertEqual(retried.status_code, 200, retried.content)
        self.assertEqual(File.objects.count(), 1)
        self.assertEqual(self.account().reserved_bytes, 0)

    def test_oversized_stream_does_not_create_file(self):
        upload = self.create(body=b"tiny")
        self.assertEqual(self.put(upload, b"bigger").status_code, 422)
        self.assertFalse(File.objects.exists())
        self.assertEqual(self.account().reserved_bytes, 0)

    def test_file_limit_metadata_validation_and_quota_are_server_owned(self):
        for name, size, status in [("a", True, 400), ("a", 0, 400), ("a", -1, 400), ("../bad", 1, 400), ("bad\x00", 1, 400), ("\ud800", 1, 400), ("a", 104857601, 413)]:
            response = self.client.post("/api/uploads", {"name": name, "size_bytes": size, "client_key": str(uuid.uuid4())}, content_type="application/json")
            self.assertEqual(response.status_code, status, response.content)
        account = services.account_for(self.user)
        account.quota_bytes = 2
        account.save()
        response = self.client.post("/api/uploads", {"name": "a", "size_bytes": 3, "client_key": str(uuid.uuid4())}, content_type="application/json")
        self.assertEqual(response.status_code, 507)
        self.assertEqual(response.json()["error"]["code"], "quota_exceeded")
        self.assertEqual(self.account().reserved_bytes, 0)

    def test_changed_metadata_with_same_key_conflicts(self):
        key = uuid.uuid4()
        self.create(key=key)
        response = self.client.post("/api/uploads", {"name": "different", "size_bytes": 15, "client_key": str(key)}, content_type="application/json")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(Upload.objects.count(), 1)

    def test_device_full_has_distinct_error_and_releases_reservation(self):
        upload = self.create()
        with patch.object(LocalBlobStore, "publish", side_effect=OSError(errno.ENOSPC, "fixture")):
            response = self.put(upload)
        self.assertEqual(response.status_code, 507)
        self.assertEqual(response.json()["error"]["code"], "device_full")
        self.assertFalse(File.objects.exists())
        self.assertEqual(self.account().reserved_bytes, 0)

    def test_crash_window_orphan_cleanup_preserves_successful_retry(self):
        upload = self.create()
        old_id = uuid.uuid4()
        with patch("drive.services.finalize", side_effect=DatabaseError("simulated commit outage")):
            response = self.put(upload, attempt=old_id)
        self.assertEqual(response.status_code, 503)
        self.assertFalse(File.objects.exists())
        self.assertTrue((Path(self.temp.name) / "blobs" / "objects" / old_id.hex).exists())
        self.assertEqual(self.put(upload).status_code, 200)
        successful_key = File.objects.get().blob_key
        UploadAttempt.objects.filter(id=old_id).update(updated_at=timezone.now() - timedelta(days=2))
        services.clean_orphans()
        self.assertFalse((Path(self.temp.name) / "blobs" / "objects" / old_id.hex).exists())
        self.assertTrue((Path(self.temp.name) / "blobs" / "objects" / successful_key).exists())
        self.assertEqual(self.account().used_bytes, len(b"private fixture"))

    def test_expired_writer_cannot_finalize_or_fail_new_attempt(self):
        upload = self.create()
        _, first = services.claim_attempt(self.user, upload["id"], uuid.uuid4())
        Upload.objects.filter(id=upload["id"]).update(lease_until=timezone.now() - timedelta(seconds=1))
        services.reconcile_user(self.user)
        _, second = services.claim_attempt(self.user, upload["id"], uuid.uuid4())
        with self.assertRaises(ApiError) as error:
            services.finalize(self.user, upload["id"], first, 15, "a" * 64)
        self.assertEqual(error.exception.code, "stale_attempt")
        services.fail_attempt(self.user, upload["id"], first)
        current = Upload.objects.get(id=upload["id"])
        self.assertEqual(current.state, "RECEIVING")
        self.assertEqual(current.generation, second.generation)
        self.assertEqual(self.account().reserved_bytes, 15)
        self.assertFalse(File.objects.exists())

    def test_expiry_releases_quota_only_once(self):
        upload = self.create()
        Upload.objects.filter(id=upload["id"]).update(lease_until=timezone.now() - timedelta(seconds=1), expires_at=timezone.now() - timedelta(seconds=1))
        services.reconcile_user(self.user)
        services.reconcile_user(self.user)
        self.assertEqual(Upload.objects.get(id=upload["id"]).state, "EXPIRED")
        self.assertEqual(self.account().reserved_bytes, 0)
        self.assertEqual(self.put(upload).status_code, 410)

    def test_database_rejects_cross_owner_file_relationship(self):
        upload = self.create()
        current, attempt = services.claim_attempt(self.user, upload["id"], uuid.uuid4())
        with self.assertRaises(IntegrityError), transaction.atomic():
            File.objects.create(owner=self.other, upload=current, successful_attempt=attempt, display_name="bad", byte_size=15, sha256="a" * 64, blob_key=attempt.blob_key)

    def test_database_rejects_attempt_from_different_upload(self):
        one = self.create()
        first, attempt = services.claim_attempt(self.user, one["id"], uuid.uuid4())
        services.fail_attempt(self.user, first.id, attempt)
        two = self.create()
        with self.assertRaises(IntegrityError), transaction.atomic():
            File.objects.create(owner=self.user, upload_id=two["id"], successful_attempt=attempt, display_name="bad", byte_size=15, sha256="a" * 64, blob_key=attempt.blob_key)

    def test_missing_blob_is_an_explicit_failure(self):
        upload = self.create()
        file_id = self.put(upload).json()["file"]["id"]
        stored = File.objects.get(id=file_id)
        (Path(self.temp.name) / "blobs" / "objects" / stored.blob_key).unlink()
        response = self.client.get(f"/api/files/{file_id}/content")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["error"]["code"], "file_unavailable")

    def test_signed_out_csrf_bootstrap_and_login_protection(self):
        client = Client(enforce_csrf_checks=True)
        response = client.get("/api/session")
        self.assertEqual(response.status_code, 401)
        self.assertIn("csrftoken", response.cookies)
        body = {"username": "owner", "password": "fixture-password-9273"}
        rejected = client.post("/api/session", body, content_type="application/json")
        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(rejected.json()["error"]["code"], "csrf_rejected")
        accepted = client.post("/api/session", body, content_type="application/json", HTTP_X_CSRFTOKEN=response.json()["csrf_token"])
        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.json()["user"]["id"], str(self.user.id))
        self.assertTrue(accepted.cookies["sessionid"]["httponly"])
        self.assertEqual(accepted["Cache-Control"], "no-store")

    def test_sign_in_rejects_unencodable_credentials(self):
        for username, password in [("\ud800", "valid-password"), ("owner", "\ud800")]:
            response = self.client.post("/api/session", {"username": username, "password": password}, content_type="application/json")
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.json()["error"]["code"], "invalid_credentials")

    def test_repeatable_setup_does_not_prompt_or_change_existing_credentials(self):
        original_hash = self.user.password
        output = io.StringIO()
        with patch("drive.management.commands.seed_local_user.getpass.getpass", side_effect=AssertionError("Unexpected password prompt")):
            call_command("seed_local_user", username="owner", if_missing=True, stdout=output)
        self.user.refresh_from_db()
        self.assertEqual(self.user.password, original_hash)
        self.assertIn("Credentials were not changed", output.getvalue())

    def test_safe_requests_validate_host_to_reject_dns_rebinding(self):
        response = self.client.get("/api/files", HTTP_HOST="untrusted.example")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "invalid_host")


@override_settings(**TEST_SETTINGS)
class ConcurrentReservationTests(TransactionTestCase):
    def test_parallel_initiations_have_one_winner_and_one_reservation(self):
        user = User.objects.create_user("parallel", password="fixture-password-9273")
        services.account_for(user)
        barrier = Barrier(2)

        def initiate():
            close_old_connections()
            try:
                owner = User.objects.get(id=user.id)
                barrier.wait(timeout=5)
                try:
                    services.create_upload(owner, {"name": "same.txt", "size_bytes": 10, "client_key": str(uuid.uuid4())})
                    return "created"
                except ApiError as error:
                    return error.code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: initiate(), range(2)))
        self.assertCountEqual(results, ["created", "upload_active"])
        self.assertEqual(Upload.objects.count(), 1)
        self.assertEqual(StorageAccount.objects.get(user=user).reserved_bytes, 10)
