#!/usr/bin/env python3
"""Run the real first-upload gates in disposable local databases, preserving evidence."""
from __future__ import annotations

import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

import local


def free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def private_json(path, value):
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
        json.dump(value, stream, indent=2)


def configure(root, pg_port, app_port):
    root.mkdir(mode=0o700)
    private_json(root / "local.json", dict(pg_port=pg_port, app_port=app_port,
        admin_password=secrets.token_urlsafe(40), db_password=secrets.token_urlsafe(40),
        secret_key=secrets.token_urlsafe(64)))


def fingerprint(base, username, password):
    browser = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    try:
        response = browser.open(base + "/api/session", timeout=10)
    except urllib.error.HTTPError as response:
        if response.code != 401:
            raise
        payload = json.load(response)
    else:
        payload = json.load(response)
    body = json.dumps(dict(username=username, password=password)).encode()
    with browser.open(urllib.request.Request(base + "/api/session", data=body,
            headers={"Content-Type": "application/json", "X-CSRFToken": payload["csrf_token"]}), timeout=10):
        pass
    records, cursor = [], None
    while True:
        url = base + "/api/files" + ("?cursor=" + urllib.parse.quote(cursor) if cursor else "")
        with browser.open(url, timeout=10) as response:
            page = json.load(response)
        for item in page["items"]:
            with browser.open(base + "/api/files/" + item["id"] + "/content", timeout=10) as response:
                actual = response.read()
            assert len(actual) == item["size_bytes"] and hashlib.sha256(actual).hexdigest() == item["sha256"], "Persisted file integrity mismatch"
            records.append(item)
        cursor = page["next_cursor"]
        if not cursor:
            return sorted(records, key=lambda row: row["id"])


def main():
    evidence_parent = Path.home() / "Library/Application Support/Drive MVP Verification"
    evidence_parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    evidence = Path(tempfile.mkdtemp(prefix="run-", dir=evidence_parent))
    os.chmod(evidence, 0o700)
    report = {"started_at": datetime.now(timezone.utc).isoformat(), "checks": [], "status": "running"}
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=local.REPO, capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain"], cwd=local.REPO, capture_output=True, text=True)
    report["git_revision"] = revision.stdout.strip() if revision.returncode == 0 else "unknown"
    report["working_tree_dirty"] = bool(dirty.stdout.strip()) if dirty.returncode == 0 else None
    log = (evidence / "verification.log").open("w")
    os.chmod(evidence / "verification.log", 0o600)
    process = None
    configs = []
    current_env = None
    stage = "prerequisites"

    def execute(command, env=None, input=None):
        result = subprocess.run([str(x) for x in command], cwd=local.REPO, env=env,
                                input=input, text=True, stdout=log, stderr=subprocess.STDOUT)
        log.flush()
        if result.returncode:
            raise RuntimeError(f"{stage} failed (exit {result.returncode}); see verification.log.")

    def passed(name):
        report["checks"].append({"name": name, "result": "PASS"})
        print(f"PASS  {name}", flush=True)

    def stop_app():
        nonlocal process
        if process and process.poll() is None:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=10)
        process = None

    def start_app(env, port):
        nonlocal process
        process = subprocess.Popen([str(local.PYTHON), "scripts/local.py", "start"], cwd=local.REPO,
                                   env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        for _ in range(80):
            if process.poll() is not None:
                raise RuntimeError("Local server exited; see verification.log.")
            if local.healthy({"app_port": port}):
                return
            time.sleep(.25)
        raise RuntimeError("Local server did not become ready.")

    try:
        local.pg_bin()
        if not local.PYTHON.is_file():
            raise RuntimeError("Open Install Local Tools.command first.")
        for name in ("add.svg", "upload.svg", "attach.svg", "roboto.ttf", "Roboto-LICENSE.txt"):
            asset = local.REPO / "frontend/public/assets" / name
            if not asset.is_file() or not asset.stat().st_size:
                raise RuntimeError(f"Missing reviewed asset {name}. Run Install Local Tools.command first.")
        execute([local.PYTHON, "-c", "import django, psycopg, waitress"])
        passed(stage)
        stage = "frontend unit tests and build"
        execute(["npm", "--prefix", "frontend", "test"])
        execute(["npm", "--prefix", "frontend", "run", "build"])
        passed(stage)
        stage = "backup manifest tests"
        execute([local.PYTHON, "-m", "unittest", "discover", "-s", "tests", "-p", "test_*.py"])
        passed(stage)
        stage = "isolated database setup"
        source = evidence / "source"
        db_port, app_port = free_port(), free_port()
        while app_port == db_port:
            app_port = free_port()
        configure(source, db_port, app_port)
        env = os.environ.copy()
        env.update(DRIVE_LOCAL_HOME=str(source), DRIVE_TEST_BASE_URL=f"http://127.0.0.1:{app_port}",
                   DRIVE_TEST_USER_A="quality-a", DRIVE_TEST_USER_B="quality-b",
                   DRIVE_TEST_PASSWORD_A=secrets.token_urlsafe(24), DRIVE_TEST_PASSWORD_B=secrets.token_urlsafe(24),
                   DRIVE_TEST_ARTIFACT_DIR=str(evidence / "browser"))
        current_env = env
        configs.append(env)
        execute([local.PYTHON, "scripts/local.py", "setup", "--skip-user", "--skip-dependencies"], env)
        passed(stage)
        stage = "backend schema and fault/concurrency tests"
        execute([local.PYTHON, "scripts/local.py", "manage", "makemigrations", "--check", "--dry-run"], env)
        execute([local.PYTHON, "scripts/local.py", "test"], env)
        passed(stage)
        for suffix in ("A", "B"):
            execute([local.PYTHON, "scripts/local.py", "manage", "seed_local_user", "--username", env[f"DRIVE_TEST_USER_{suffix}"], "--password-stdin"], env,
                    env[f"DRIVE_TEST_PASSWORD_{suffix}"] + "\n")
        stage = "real HTTP acceptance"
        start_app(env, app_port)
        execute([local.PYTHON, "tests/api_acceptance.py"], env)
        passed(stage)
        stage = "real browser acceptance"
        execute(["npm", "--prefix", "frontend", "run", "test:e2e"], env)
        passed(stage)
        stage = "restart persistence"
        before = {suffix: fingerprint(env["DRIVE_TEST_BASE_URL"], env[f"DRIVE_TEST_USER_{suffix}"], env[f"DRIVE_TEST_PASSWORD_{suffix}"]) for suffix in ("A", "B")}
        assert before["A"] and before["B"], "Acceptance did not create both fixtures"
        stop_app()
        execute([local.PYTHON, "scripts/local.py", "stop-db"], env)
        start_app(env, app_port)
        after = {suffix: fingerprint(env["DRIVE_TEST_BASE_URL"], env[f"DRIVE_TEST_USER_{suffix}"], env[f"DRIVE_TEST_PASSWORD_{suffix}"]) for suffix in ("A", "B")}
        assert before == after, "Files changed across app/database restart"
        passed(stage)
        stop_app()
        stage = "backup and isolated restore"
        backup = evidence / "backup"
        restored = evidence / "restored"
        execute([local.PYTHON, "scripts/backup.py", "create", "--destination", backup], env)
        restore_db_port, restore_app_port = free_port(), free_port()
        while restore_db_port == restore_app_port:
            restore_app_port = free_port()
        execute([local.PYTHON, "scripts/backup.py", "restore", backup, "--destination", restored,
                 "--pg-port", restore_db_port, "--app-port", restore_app_port], env)
        restored_env = dict(env, DRIVE_LOCAL_HOME=str(restored), DRIVE_TEST_BASE_URL=f"http://127.0.0.1:{restore_app_port}")
        configs.append(restored_env)
        start_app(restored_env, restore_app_port)
        recovered = {suffix: fingerprint(restored_env["DRIVE_TEST_BASE_URL"], env[f"DRIVE_TEST_USER_{suffix}"], env[f"DRIVE_TEST_PASSWORD_{suffix}"]) for suffix in ("A", "B")}
        assert recovered == before, "Restored files differ from original fixtures"
        passed(stage)
        report["status"] = "passed"
    except (Exception, KeyboardInterrupt) as error:
        report["status"] = "failed"
        report["failed_stage"] = stage
        report["error"] = str(error) or "Interrupted"
        print(f"STOP  {stage}: {report['error']}", file=sys.stderr)
    finally:
        try:
            stop_app()
        except Exception as error:
            report["status"] = "failed"
            report.setdefault("cleanup_errors", []).append(str(error))
        for env in reversed(configs):
            try:
                result = subprocess.run([str(local.PYTHON), "scripts/local.py", "stop-db"], cwd=local.REPO, env=env,
                                        stdout=log, stderr=subprocess.STDOUT, timeout=30)
                if result.returncode:
                    report["status"] = "failed"
                    report.setdefault("cleanup_errors", []).append("A verification database could not be stopped.")
            except Exception as error:
                report["status"] = "failed"
                report.setdefault("cleanup_errors", []).append(str(error))
        report["finished_at"] = datetime.now(timezone.utc).isoformat()
        report["scope"] = "First-upload local workflow only. Human usability, screen-reader review and public-hosting capacity remain unverified."
        private_json(evidence / "report.json", report)
        log.close()
        print(f"Evidence: {evidence}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
