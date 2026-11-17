"""Private immutable local blobs. No domain model ever stores a filesystem path."""
import hashlib
import os
import re
import shutil
import time
from pathlib import Path

from django.conf import settings

from .errors import ApiError

KEY_PATTERN = re.compile(r"^[0-9a-f]{32}$")


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def ensure_directory(path):
    """Persist newly created directory entries, including a new storage root."""
    missing = []
    current = path
    while not current.exists():
        missing.append(current)
        current = current.parent
    for directory in reversed(missing):
        try:
            directory.mkdir(mode=0o700)
        except FileExistsError:
            if not directory.is_dir():
                raise
        sync_directory(directory.parent)
    os.chmod(path, 0o700)


class LocalBlobStore:
    def __init__(self, root=None):
        self.root = Path(root or settings.DRIVE_DATA_DIR) / "blobs"
        self.staging = self.root / "staging"
        self.objects = self.root / "objects"
        for path in (self.root, self.staging, self.objects):
            ensure_directory(path)

    def _path(self, directory, key):
        if not KEY_PATTERN.fullmatch(key):
            raise ValueError("Invalid internal blob key")
        return directory / key

    def stage(self, stream, key, expected_bytes, progress):
        if shutil.disk_usage(self.root).free < expected_bytes + settings.DISK_HEADROOM_BYTES:
            raise ApiError("device_full", "This device is out of space.", 507)
        path = self._path(self.staging, key)
        digest = hashlib.sha256()
        total = 0
        started = last_checkpoint = time.monotonic()
        with open(path, "xb") as target:
            os.chmod(path, 0o600)
            while True:
                chunk = stream.read(min(1024 * 1024, expected_bytes - total + 1))
                if not chunk:
                    break
                total += len(chunk)
                if total > expected_bytes:
                    raise ApiError("size_mismatch", "File size changed. Choose the file again.", 422)
                target.write(chunk)
                digest.update(chunk)
                now = time.monotonic()
                if now - started > settings.UPLOAD_MAX_SECONDS:
                    raise ApiError("upload_timeout", "The upload took too long. Please retry.", 408)
                if now - last_checkpoint >= settings.UPLOAD_RENEW_SECONDS:
                    progress(total)
                    last_checkpoint = now
            if total != expected_bytes:
                raise ApiError("size_mismatch", "The upload was interrupted before all bytes arrived.", 422)
            target.flush()
            os.fsync(target.fileno())
        progress(total, verifying=True)
        return total, digest.hexdigest()

    def publish(self, key):
        source = self._path(self.staging, key)
        destination = self._path(self.objects, key)
        # Hard-link publication is same-filesystem, atomic and refuses overwrite.
        os.link(source, destination)
        sync_directory(self.objects)
        source.unlink()
        sync_directory(self.staging)
        return key

    def open(self, key):
        return open(self._path(self.objects, key), "rb")

    def inspect(self, key):
        path = self._path(self.objects, key)
        return path.stat()

    def remove_unreferenced(self, key):
        """Caller must fence the owning attempt and check File references under lock."""
        for directory in (self.staging, self.objects):
            path = self._path(directory, key)
            try:
                path.unlink()
            except FileNotFoundError:
                continue
            sync_directory(directory)
