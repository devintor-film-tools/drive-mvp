import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("backup", SCRIPTS / "backup.py")
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


class BackupManifestTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="drive-backup-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "objects").mkdir()
        self.dump = b"not a real dump: manifest verification fixture"
        (self.root / "database.dump").write_bytes(self.dump)
        self.content = b"exact file contents\x00\xff"
        self.key = uuid.uuid4().hex
        (self.root / "objects" / self.key).write_bytes(self.content)
        self.manifest = {"format": 1, "database_sha256": hashlib.sha256(self.dump).hexdigest(), "files": [{
            "id": str(uuid.uuid4()), "owner_id": str(uuid.uuid4()), "blob_key": self.key,
            "byte_size": len(self.content), "sha256": hashlib.sha256(self.content).hexdigest()}]}
        self.write_manifest()

    def write_manifest(self):
        (self.root / "manifest.json").write_text(json.dumps(self.manifest))

    def test_valid_manifest_and_content(self):
        self.assertEqual(backup.verify(self.root)["files"], self.manifest["files"])

    def test_rejects_corrupt_dump(self):
        (self.root / "database.dump").write_bytes(b"changed")
        with self.assertRaises(backup.local.SetupError):
            backup.verify(self.root)

    def test_rejects_corrupt_file(self):
        (self.root / "objects" / self.key).write_bytes(b"x" * len(self.content))
        with self.assertRaises(backup.local.SetupError):
            backup.verify(self.root)

    def test_rejects_traversal_key(self):
        self.manifest["files"][0]["blob_key"] = "../../outside"
        self.write_manifest()
        with self.assertRaises(backup.local.SetupError):
            backup.verify(self.root)

    def test_rejects_symlink_blob(self):
        target = self.root / "objects" / self.key
        target.unlink()
        target.symlink_to(self.root / "database.dump")
        with self.assertRaises(backup.local.SetupError):
            backup.verify(self.root)

    def test_rejects_symlink_object_directory(self):
        (self.root / "objects").rename(self.root / "elsewhere")
        (self.root / "objects").symlink_to(self.root / "elsewhere", target_is_directory=True)
        with self.assertRaises(backup.local.SetupError):
            backup.verify(self.root)

    def test_rejects_duplicate_file_or_key(self):
        self.manifest["files"].append(self.manifest["files"][0].copy())
        self.write_manifest()
        with self.assertRaises(backup.local.SetupError):
            backup.verify(self.root)

    def test_rejects_malformed_manifest_shapes(self):
        for manifest in [[], {"format": 1, "files": [], "database_sha256": 123},
                         {**self.manifest, "files": [123]}]:
            (self.root / "manifest.json").write_text(json.dumps(manifest))
            with self.assertRaises(backup.local.SetupError):
                backup.verify(self.root)

    def test_copy_refuses_existing_destination(self):
        source = self.root / "objects" / self.key
        with self.assertRaises(FileExistsError):
            backup.copy_verified(source, source, len(self.content), hashlib.sha256(self.content).hexdigest())
        self.assertEqual(source.read_bytes(), self.content)

    def test_rejects_backup_inside_repository(self):
        with self.assertRaises(backup.local.SetupError):
            backup.outside_git(backup.local.REPO / "backups")


if __name__ == "__main__":
    unittest.main()
