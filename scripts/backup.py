#!/usr/bin/env python3
"""Consistent local backups, checksum verification and isolated restore rehearsals."""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import urllib.parse
import uuid

import local

KEY = re.compile(r"^[0-9a-f]{32}$")
SHA = re.compile(r"^[0-9a-f]{64}$")


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sync_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_json(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def copy_verified(source, destination, expected_size, expected_hash):
    source, destination = Path(source), Path(destination)
    if source.is_symlink() or not source.is_file():
        raise local.SetupError("A referenced blob is missing or is not a regular file.")
    with source.open("rb") as incoming, os.fdopen(os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as outgoing:
        digest = hashlib.sha256()
        count = 0
        for chunk in iter(lambda: incoming.read(1024 * 1024), b""):
            count += len(chunk)
            digest.update(chunk)
            outgoing.write(chunk)
        if count != expected_size or digest.hexdigest() != expected_hash:
            raise local.SetupError("Blob size/checksum mismatch; operation stopped.")
        outgoing.flush()
        os.fsync(outgoing.fileno())


def outside_git(path):
    path = Path(path).expanduser().resolve()
    if path == local.REPO or local.REPO in path.parents:
        raise local.SetupError("Backups and restored data must stay outside the Git checkout.")
    return path


@contextlib.contextmanager
def exclusive_lock(data):
    data = Path(data)
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(data / ".maintenance.lock", os.O_RDWR | os.O_CREAT, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise local.SetupError("Stop the local app and other maintenance commands before continuing.") from error
        yield
    finally:
        os.close(fd)


def connect(config, database="drive_mvp", *, admin=True):
    try:
        import psycopg
    except ImportError as error:
        raise local.SetupError("Run this command with .venv/bin/python after local setup.") from error
    return psycopg.connect(host="127.0.0.1", port=config["pg_port"], dbname=database,
                          user="drive_admin" if admin else "drive_app",
                          password=config["admin_password"] if admin else config["db_password"],
                          connect_timeout=5)


def file_records(connection):
    rows = connection.execute("SELECT id, owner_id, byte_size, sha256, blob_key FROM drive_file ORDER BY id").fetchall()
    if any(not KEY.fullmatch(row[4]) or not SHA.fullmatch(row[3]) or row[2] < 1 for row in rows):
        raise local.SetupError("Database contains invalid file storage metadata.")
    return [dict(id=str(row[0]), owner_id=str(row[1]), byte_size=row[2], sha256=row[3], blob_key=row[4]) for row in rows]


def verify(backup):
    backup = outside_git(backup)
    manifest_path = backup / "manifest.json"
    if manifest_path.is_symlink():
        raise local.SetupError("Manifest must be a regular file.")
    manifest = json.loads(manifest_path.read_text())
    if not isinstance(manifest, dict) or manifest.get("format") != 1 or not isinstance(manifest.get("files"), list):
        raise local.SetupError("Unsupported or incomplete backup manifest.")
    dump = backup / "database.dump"
    dump_hash = manifest.get("database_sha256", "")
    if dump.is_symlink() or not dump.is_file() or not isinstance(dump_hash, str) or not SHA.fullmatch(dump_hash):
        raise local.SetupError("Database dump or manifest checksum is invalid.")
    if checksum(dump) != manifest["database_sha256"]:
        raise local.SetupError("Database dump checksum mismatch.")
    seen_keys, seen_ids = set(), set()
    objects = backup / "objects"
    if objects.is_symlink() or not objects.is_dir():
        raise local.SetupError("Backup objects must be a regular directory.")
    for item in manifest["files"]:
        if not isinstance(item, dict):
            raise local.SetupError("Invalid file entry in manifest.")
        key = item.get("blob_key", "")
        if not isinstance(key, str) or not KEY.fullmatch(key) or key in seen_keys:
            raise local.SetupError("Invalid or duplicate blob key in manifest.")
        try:
            file_id = str(uuid.UUID(item["id"]))
            uuid.UUID(item["owner_id"])
        except (ValueError, TypeError, KeyError, AttributeError) as error:
            raise local.SetupError("Invalid identity in manifest.") from error
        size = item.get("byte_size")
        digest = item.get("sha256", "")
        if file_id in seen_ids or type(size) is not int or size < 1 or not isinstance(digest, str) or not SHA.fullmatch(digest):
            raise local.SetupError("Invalid file metadata in manifest.")
        blob = backup / "objects" / key
        if blob.is_symlink() or not blob.is_file() or blob.stat().st_size != size or checksum(blob) != digest:
            raise local.SetupError("Referenced blob checksum or size mismatch.")
        seen_keys.add(key)
        seen_ids.add(file_id)
    return manifest


def create(args):
    try:
        import psycopg.sql
    except ImportError as error:
        raise local.SetupError("Run this command with .venv/bin/python after local setup.") from error
    config = local.load_config()
    destination = outside_git(args.destination or local.DATA / "backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    if destination.exists():
        raise local.SetupError("Backup destination already exists; choose a new directory.")
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with exclusive_lock(local.DATA):
        if local.healthy(config):
            raise local.SetupError("Stop the app before creating a backup.")
        local.start_db(config)
        temporary = Path(tempfile.mkdtemp(prefix=".backup-", dir=destination.parent))
        temporary.chmod(0o700)
        objects = temporary / "objects"
        objects.mkdir(mode=0o700)
        try:
            with connect(config) as connection:
                connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                connection.execute("SET LOCAL lock_timeout = '5s'")
                if connection.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND usename='drive_app')").fetchone()[0]:
                    raise local.SetupError("An application database connection is still open. Stop it before backup.")
                tables = connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").fetchall()
                if not tables:
                    raise local.SetupError("Database has no application tables; run migrations first.")
                identifiers = psycopg.sql.SQL(", ").join(psycopg.sql.Identifier("public", row[0]) for row in tables)
                connection.execute(psycopg.sql.SQL("LOCK TABLE {} IN SHARE MODE").format(identifiers))
                active = connection.execute("SELECT COUNT(*) FROM drive_upload WHERE state IN ('CREATED','RECEIVING','VERIFYING')").fetchone()[0]
                if active:
                    raise local.SetupError("Uploads are still active. Reconcile expired uploads before backup.")
                snapshot = connection.execute("SELECT pg_export_snapshot()").fetchone()[0]
                records = file_records(connection)
                manifest = {"format": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                            "postgres_version": connection.execute("SHOW server_version").fetchone()[0],
                            "git_revision": local.run(["git", "rev-parse", "HEAD"], capture=True).strip(),
                            "migrations": [list(row) for row in connection.execute("SELECT app, name FROM django_migrations ORDER BY app, name").fetchall()],
                            "files": records}
                local.run([local.pg_bin() / "pg_dump", "--format=custom", "--no-owner", "--no-privileges", "--snapshot", snapshot, "--file", temporary / "database.dump"], env=local.db_env(config, admin=True), capture=True)
                (temporary / "database.dump").chmod(0o600)
                with (temporary / "database.dump").open("rb") as dump:
                    os.fsync(dump.fileno())
                manifest["database_sha256"] = checksum(temporary / "database.dump")
                for item in records:
                    copy_verified(local.DATA / "files/blobs/objects" / item["blob_key"], objects / item["blob_key"], item["byte_size"], item["sha256"])
                write_json(temporary / "manifest.json", manifest)
                sync_dir(objects)
                sync_dir(temporary)
            verify(temporary)
            # Reserve a fresh directory atomically; never replace an existing one.
            destination.mkdir(mode=0o700)
            (temporary / "objects").rename(destination / "objects")
            (temporary / "database.dump").rename(destination / "database.dump")
            # Publish the manifest last: interrupted output is visibly incomplete.
            (temporary / "manifest.json").rename(destination / "manifest.json")
            temporary.rmdir()
            sync_dir(destination)
            sync_dir(destination.parent)
        except BaseException:
            # Only this newly created, private staging directory is removed.
            shutil.rmtree(temporary, ignore_errors=True)
            raise
    print(f"Verified backup: {destination}\nFiles: {len(manifest['files'])}")


def ensure_free_port(port):
    with socket.socket() as sock:
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as error:
            raise local.SetupError(f"Port {port} is already occupied; choose another port.") from error


def restore(args):
    backup = outside_git(args.backup)
    manifest = verify(backup)
    destination = outside_git(args.destination)
    if destination.exists():
        raise local.SetupError("Restore requires a new directory. Existing data is never overwritten.")
    if destination == local.DATA or destination in local.DATA.parents or local.DATA in destination.parents:
        raise local.SetupError("Restore must be separate from the original local data directory.")
    if args.pg_port == args.app_port:
        raise local.SetupError("Database and application ports must be different.")
    ensure_free_port(args.pg_port)
    ensure_free_port(args.app_port)
    pg = local.pg_bin()
    config = dict(pg_port=args.pg_port, app_port=args.app_port, admin_password=secrets.token_urlsafe(40),
                  db_password=secrets.token_urlsafe(40), secret_key=secrets.token_urlsafe(64), setup_complete=True)
    destination.mkdir(parents=True, mode=0o700)
    cluster = destination / "postgres"
    password_file = destination / ".init-password"
    started = False
    try:
        with exclusive_lock(destination):
            with os.fdopen(os.open(password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
                stream.write(config["admin_password"])
            try:
                local.run([pg / "initdb", "-D", cluster, "--username=drive_admin", "--auth=scram-sha-256", f"--pwfile={password_file}", "--encoding=UTF8", "--locale=C"], capture=True)
            finally:
                password_file.unlink(missing_ok=True)
            pg_config = cluster / "postgresql.conf"
            with pg_config.open("a") as stream:
                stream.write(f"\nlisten_addresses = '127.0.0.1'\nport = {args.pg_port}\nunix_socket_directories = ''\n")
            local.run([pg / "pg_ctl", "-D", cluster, "-l", destination / "postgres.log", "-w", "start"], capture=True)
            started = True
            admin = local.db_env(config, admin=True, database="postgres")
            local.run([pg / "psql", "-X", "-v", "ON_ERROR_STOP=1"], env=admin, capture=True,
                      input=f"CREATE ROLE drive_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{config['db_password']}';\nCREATE DATABASE drive_mvp OWNER drive_app;\n")
            local.run([pg / "pg_restore", "--exit-on-error", "--single-transaction", "--no-owner", "--no-privileges", "--dbname=drive_mvp", backup / "database.dump"], env=local.db_env(config), capture=True)
            objects = destination / "files/blobs/objects"
            objects.mkdir(parents=True, mode=0o700)
            (objects.parent / "staging").mkdir(mode=0o700)
            for item in manifest["files"]:
                copy_verified(backup / "objects" / item["blob_key"], objects / item["blob_key"], item["byte_size"], item["sha256"])
            with connect(config, admin=False) as connection:
                actual = file_records(connection)
                expected = sorted(manifest["files"], key=lambda row: row["id"])
                if actual != expected:
                    raise local.SetupError("Restored file metadata does not match the verified manifest.")
                migrations = [list(row) for row in connection.execute("SELECT app, name FROM django_migrations ORDER BY app, name").fetchall()]
                if migrations != manifest.get("migrations"):
                    raise local.SetupError("Restored schema history does not match the backup manifest.")
                accounts = connection.execute("SELECT user_id, used_bytes, reserved_bytes FROM drive_storageaccount").fetchall()
                sums = {}
                for item in actual:
                    sums[item["owner_id"]] = sums.get(item["owner_id"], 0) + item["byte_size"]
                account_owners = {str(owner) for owner, _, _ in accounts}
                if not set(sums).issubset(account_owners) or any(used != sums.get(str(owner), 0) or reserved != 0 for owner, used, reserved in accounts):
                    raise local.SetupError("Restored storage accounting is inconsistent.")
                # New signing secret intentionally invalidates old sessions; remove them explicitly.
                connection.execute("DELETE FROM django_session")
            write_json(destination / "local.json", config)
            write_json(destination / "restore-verification.json", {"verified_at": datetime.now(timezone.utc).isoformat(), "files": len(actual), "source_revision": manifest.get("git_revision"), "source_manifest_sha256": checksum(backup / "manifest.json")})
            sync_dir(objects)
            sync_dir(destination)
    finally:
        if started:
            local.run([pg / "pg_ctl", "-D", cluster, "-m", "fast", "-w", "stop"], capture=True)
    print(f"Restored and verified {len(manifest['files'])} files in {destination}. Original data was not changed.")
    print("The restored database is stopped. Use the original account password to sign in after starting:")
    print(f"DRIVE_LOCAL_HOME={shlex.quote(str(destination))} python3 scripts/local.py start --open-browser")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    backup = commands.add_parser("create")
    backup.add_argument("--destination")
    check = commands.add_parser("verify")
    check.add_argument("backup")
    recovery = commands.add_parser("restore")
    recovery.add_argument("backup")
    recovery.add_argument("--destination", required=True)
    recovery.add_argument("--pg-port", type=int, default=55433)
    recovery.add_argument("--app-port", type=int, default=8001)
    args = parser.parse_args()
    try:
        local.assert_data_location()
        if args.command == "create":
            create(args)
        elif args.command == "verify":
            manifest = verify(args.backup)
            print(f"Backup checksums valid: {len(manifest['files'])} files. Database restoration has not been tested by this command.")
        else:
            restore(args)
    except (local.SetupError, OSError, ValueError, KeyError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
