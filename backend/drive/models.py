import uuid

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F, Q


class User(AbstractUser):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)


class StorageAccount(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, primary_key=True, on_delete=models.PROTECT)
    used_bytes = models.PositiveBigIntegerField(default=0)
    reserved_bytes = models.PositiveBigIntegerField(default=0)
    quota_bytes = models.PositiveBigIntegerField(default=settings.DEFAULT_QUOTA_BYTES)

    class Meta:
        constraints = [models.CheckConstraint(
            condition=Q(quota_bytes__gte=F("used_bytes") + F("reserved_bytes")),
            name="account_usage_within_quota",
        )]


class Folder(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT)
    name = models.CharField(max_length=255)
    client_key = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["id", "owner"], name="folder_id_owner_unique"),
            models.UniqueConstraint(fields=["owner", "client_key"], name="folder_owner_client_key"),
            models.UniqueConstraint(fields=["owner", "parent", "name"], nulls_distinct=False, name="folder_sibling_name_unique"),
            models.CheckConstraint(condition=~Q(id=F("parent_id")), name="folder_not_own_parent"),
        ]
        indexes = [models.Index(fields=["owner", "parent", "name", "id"], name="folder_children_idx")]


class Upload(models.Model):
    class State(models.TextChoices):
        CREATED = "CREATED"
        RECEIVING = "RECEIVING"
        VERIFYING = "VERIFYING"
        RETRYABLE = "RETRYABLE"
        COMPLETE = "COMPLETE"
        EXPIRED = "EXPIRED"

    ACTIVE = (State.CREATED, State.RECEIVING, State.VERIFYING)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    folder = models.ForeignKey(Folder, null=True, blank=True, on_delete=models.PROTECT)
    client_key = models.UUIDField()
    display_name = models.CharField(max_length=255)
    expected_bytes = models.PositiveBigIntegerField()
    received_bytes = models.PositiveBigIntegerField(default=0)
    state = models.CharField(max_length=12, choices=State.choices, default=State.CREATED)
    error_code = models.CharField(max_length=40, blank=True)
    generation = models.PositiveBigIntegerField(default=0)
    lease_until = models.DateTimeField(null=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "client_key"], name="upload_owner_client_key"),
            models.UniqueConstraint(fields=["id", "owner"], name="upload_id_owner_unique"),
            models.UniqueConstraint(fields=["owner"], condition=Q(state__in=["CREATED", "RECEIVING", "VERIFYING"]), name="one_active_upload_per_owner"),
            models.CheckConstraint(condition=Q(expected_bytes__gt=0), name="upload_nonempty"),
            models.CheckConstraint(condition=Q(received_bytes__lte=F("expected_bytes")), name="upload_progress_bounded"),
        ]
        indexes = [models.Index(fields=["state", "lease_until"], name="upload_state_lease_idx")]


class UploadAttempt(models.Model):
    class State(models.TextChoices):
        RECEIVING = "RECEIVING"
        VERIFYING = "VERIFYING"
        COMPLETE = "COMPLETE"
        FAILED = "FAILED"

    id = models.UUIDField(primary_key=True, editable=False)
    upload = models.ForeignKey(Upload, on_delete=models.PROTECT, related_name="attempts")
    generation = models.PositiveBigIntegerField()
    state = models.CharField(max_length=12, choices=State.choices, default=State.RECEIVING)
    actual_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, blank=True)
    blob_key = models.CharField(max_length=40, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["upload", "generation"], name="attempt_generation_unique"),
            models.UniqueConstraint(fields=["id", "upload"], name="attempt_id_upload_unique"),
        ]


class File(models.Model):
    folder = models.ForeignKey(Folder, null=True, blank=True, on_delete=models.PROTECT)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    upload = models.OneToOneField(Upload, on_delete=models.PROTECT, related_name="file")
    successful_attempt = models.OneToOneField(UploadAttempt, on_delete=models.PROTECT)
    display_name = models.CharField(max_length=255)
    byte_size = models.PositiveBigIntegerField()
    sha256 = models.CharField(max_length=64)
    blob_key = models.CharField(max_length=40, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    trashed_at = models.DateTimeField(null=True, blank=True)
    revision = models.PositiveBigIntegerField(default=1)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [models.Index(fields=["owner", "-created_at", "-id"], name="file_owner_recent_idx")]


class LoginThrottle(models.Model):
    """Bounded local login attempts, shared across application processes."""
    key = models.CharField(max_length=64, primary_key=True)
    attempts = models.PositiveIntegerField(default=0)
    window_started = models.DateTimeField()
