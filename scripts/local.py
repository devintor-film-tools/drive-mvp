#!/usr/bin/env python3
"""Own this project's isolated local services, never system-wide services."""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import secrets
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

REPO = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("DRIVE_LOCAL_HOME", Path.home() / "Library/Application Support/Drive MVP")).expanduser().resolve()
CONFIG = DATA / "local.json"
PYTHON = REPO / ".venv/bin/python"
PG_PORT = 55432
APP_PORT = 8000


class SetupError(Exception):
    pass


@contextlib.contextmanager
def maintenance_lock(*, exclusive):
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    with open(DATA / ".maintenance.lock", "a+") as lock:
        try:
            fcntl.flock(lock, (fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH) | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise SetupError("The app or a maintenance task is running. Stop it before this operation.") from error
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def run(args, *, env=None, cwd=REPO, capture=False, input=None):
    result = subprocess.run([str(a) for a in args], cwd=cwd, env=env, input=input,
                            text=True, stdout=subprocess.PIPE if capture else None,
                            stderr=subprocess.PIPE if capture else None)
    if result.returncode:
        # Never echo command arguments or environment: they may contain secrets.
        raise SetupError(f"{Path(str(args[0])).name} failed (exit {result.returncode})." +
                         (f"\n{result.stderr.strip()}" if capture else ""))
    return result.stdout or ""


def load_config():
    if not CONFIG.exists():
        raise SetupError("Run setup first: python3 scripts/local.py setup")
    return json.loads(CONFIG.read_text())


def save_config(config):
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    DATA.chmod(0o700)
    temporary = DATA / ".local.json.tmp"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(config, stream, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(CONFIG)
    CONFIG.chmod(0o600)


def pg_bin():
    override = os.environ.get("DRIVE_PG_BIN")
    candidates = [Path(override)] if override else []
    found = shutil.which("pg_ctl")
    if found:
        candidates.append(Path(found).parent)
    candidates += [Path("/opt/homebrew/opt/postgresql@18/bin"),
                   Path("/usr/local/opt/postgresql@18/bin"),
                   Path("/Applications/Postgres.app/Contents/Versions/latest/bin")]
    for directory in candidates:
        if all((directory / binary).is_file() for binary in ("pg_ctl", "initdb", "psql", "pg_dump", "pg_restore")):
            return directory
    raise SetupError("PostgreSQL is missing. On this Mac, open Install Local Tools.command, then run setup again.")


def db_env(config, *, admin=False, database="drive_mvp"):
    env = os.environ.copy()
    env.update(PGHOST="127.0.0.1", PGPORT=str(config["pg_port"]), PGDATABASE=database,
               PGUSER="drive_admin" if admin else "drive_app",
               PGPASSWORD=config["admin_password"] if admin else config["db_password"])
    return env


def app_env(config, *, admin=False):
    env = os.environ.copy()
    user = "drive_admin" if admin else "drive_app"
    password = config["admin_password"] if admin else config["db_password"]
    env.update(DATABASE_URL=f"postgresql://{user}:{urllib.parse.quote(password, safe='')}@127.0.0.1:{config['pg_port']}/drive_mvp",
               DRIVE_DATA_DIR=str(DATA / "files"), DRIVE_SECRET_KEY=config["secret_key"],
               DRIVE_ALLOWED_HOSTS="127.0.0.1,localhost", DRIVE_DEBUG="0")
    return env


def pg_running():
    if not (DATA / "postgres/PG_VERSION").exists():
        return False
    return subprocess.run([str(pg_bin() / "pg_ctl"), "-D", str(DATA / "postgres"), "status"],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0


def start_db(config):
    if pg_running():
        return
    run([pg_bin() / "pg_ctl", "-D", DATA / "postgres", "-l", DATA / "postgres.log", "-w", "start"], capture=True)


def manage(config, arguments, *, admin=False):
    return run([PYTHON, REPO / "backend/manage.py", *arguments], env=app_env(config, admin=admin))


def assert_data_location():
    if DATA == REPO or REPO in DATA.parents:
        raise SetupError("DRIVE_LOCAL_HOME must be outside the Git checkout.")


def require_assets(directory):
    for name in ("add.svg", "upload.svg", "attach.svg", "roboto.ttf", "Roboto-LICENSE.txt"):
        asset = directory / name
        if not asset.is_file() or not asset.stat().st_size:
            raise SetupError(f"Reviewed design asset {name} is missing. Open Install Local Tools.command first.")


def setup(args):
    assert_data_location()
    pg = pg_bin()
    require_assets(REPO / "frontend/public/assets")
    if not (3, 10) <= sys.version_info[:2] <= (3, 14):
        raise SetupError("Use Python 3.10–3.14 for Django 5.2. Start Drive.command selects a supported interpreter.")
    if not shutil.which("npm"):
        raise SetupError("Node/npm is missing. Open Install Local Tools.command first.")
    DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
    DATA.chmod(0o700)
    config = load_config() if CONFIG.exists() else dict(pg_port=PG_PORT, app_port=APP_PORT,
             admin_password=secrets.token_urlsafe(40), db_password=secrets.token_urlsafe(40),
             secret_key=secrets.token_urlsafe(64))
    save_config(config)
    if not PYTHON.exists():
        run([sys.executable, "-m", "venv", REPO / ".venv"])
    if not getattr(args, "skip_dependencies", False):
        run([PYTHON, "-m", "pip", "install", "-r", REPO / "backend/requirements.txt"])
        run(["npm", "ci"], cwd=REPO / "frontend")
        run(["npm", "run", "build"], cwd=REPO / "frontend")
    cluster = DATA / "postgres"
    if not (cluster / "PG_VERSION").exists():
        password_file = DATA / ".init-password"
        fd = os.open(password_file, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w") as stream:
                stream.write(config["admin_password"])
            run([pg / "initdb", "-D", cluster, "--username=drive_admin", "--auth=scram-sha-256",
                 f"--pwfile={password_file}", "--encoding=UTF8", "--locale=C"], capture=True)
        finally:
            password_file.unlink(missing_ok=True)
        # The cluster is project-owned. Never edit another installation's config.
        (cluster / "postgresql.conf").write_text((cluster / "postgresql.conf").read_text() +
            f"\nlisten_addresses = '127.0.0.1'\nport = {config['pg_port']}\nunix_socket_directories = ''\n")
    start_db(config)
    admin = db_env(config, admin=True, database="postgres")
    exists = run([pg / "psql", "-X", "-A", "-t", "-c", "SELECT 1 FROM pg_roles WHERE rolname='drive_app'"], env=admin, capture=True).strip()
    if not exists:
        # Password consists solely of URL-safe random characters. Feed SQL over stdin.
        run([pg / "psql", "-X", "-v", "ON_ERROR_STOP=1"], env=admin, capture=True,
            input=f"CREATE ROLE drive_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD '{config['db_password']}';\n")
    exists = run([pg / "psql", "-X", "-A", "-t", "-c", "SELECT 1 FROM pg_database WHERE datname='drive_mvp'"], env=admin, capture=True).strip()
    if not exists:
        run([pg / "psql", "-X", "-v", "ON_ERROR_STOP=1", "-c", "CREATE DATABASE drive_mvp OWNER drive_app"], env=admin, capture=True)
    manage(config, ["migrate", "--noinput"])
    manage(config, ["check"])
    if not args.skip_user:
        username = input("Local sign-in username [devin]: ").strip() or "devin"
        manage(config, ["seed_local_user", "--username", username, "--if-missing"])
    config["setup_complete"] = True
    save_config(config)
    print("Setup complete. Start with: python3 scripts/local.py start")


def healthy(config):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{config['app_port']}/api/health", timeout=2) as response:
            return response.status == 200 and json.load(response).get("status") == "ok"
    except (OSError, urllib.error.URLError, ValueError):
        return False


def start(args):
    config = load_config()
    start_db(config)
    if not (REPO / "frontend/dist/index.html").is_file():
        raise SetupError("Frontend build missing. Run setup first.")
    require_assets(REPO / "frontend/dist/assets")
    if healthy(config):
        print(f"Already running: http://127.0.0.1:{config['app_port']}")
        return
    # Let Waitress bind its own socket. A separate plain bind probe can reject
    # a recently stopped server's TIME_WAIT connections even though Waitress's
    # SO_REUSEADDR socket can restart safely. A real listener conflict still
    # makes the child exit and is reported by the readiness check below.
    manage(config, ["reconcile_uploads"])
    # Keep the launcher attached: Ctrl-C stops its owned app process cleanly.
    print(f"Open http://127.0.0.1:{config['app_port']} — press Ctrl-C here to stop the app.", flush=True)
    command = [PYTHON, REPO / "backend/serve.py", "--port", str(config["app_port"])]
    process = subprocess.Popen([str(x) for x in command], cwd=REPO, env=app_env(config))
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    old_handler = signal.signal(signal.SIGTERM, interrupted)
    try:
        for _ in range(60):
            if process.poll() is not None:
                raise SetupError("Local application exited before becoming ready.")
            if healthy(config):
                if args.open_browser:
                    import webbrowser
                    webbrowser.open(f"http://127.0.0.1:{config['app_port']}")
                break
            time.sleep(.25)
        else:
            raise SetupError("The application did not become ready in 15 seconds.")
        process.wait()
    except KeyboardInterrupt:
        print("\nStopping the local app…")
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        signal.signal(signal.SIGTERM, old_handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    setup_parser = sub.add_parser("setup")
    setup_parser.add_argument("--skip-user", action="store_true")
    setup_parser.add_argument("--skip-dependencies", action="store_true", help="Use already installed dependencies and an existing frontend build (verification harness).")
    start_parser = sub.add_parser("start")
    start_parser.add_argument("--open-browser", action="store_true")
    launch_parser = sub.add_parser("launch")
    launch_parser.add_argument("--prepared", action="store_true", help="Dependencies and frontend were already prepared by the setup launcher.")
    sub.add_parser("stop-db")
    sub.add_parser("status")
    command = sub.add_parser("manage")
    command.add_argument("arguments", nargs=argparse.REMAINDER)
    sub.add_parser("test")
    args = parser.parse_args()
    try:
        assert_data_location()
        if args.command == "setup":
            with maintenance_lock(exclusive=True):
                setup(args)
        elif args.command == "start":
            with maintenance_lock(exclusive=False):
                start(args)
        elif args.command == "launch":
            ready = CONFIG.exists() and load_config().get("setup_complete") and PYTHON.exists() and (REPO / "frontend/dist/index.html").exists()
            if not ready:
                with maintenance_lock(exclusive=True):
                    setup(argparse.Namespace(skip_user=False, skip_dependencies=args.prepared))
            with maintenance_lock(exclusive=False):
                start(argparse.Namespace(open_browser=True))
        elif args.command == "stop-db":
            with maintenance_lock(exclusive=True):
                if pg_running():
                    run([pg_bin() / "pg_ctl", "-D", DATA / "postgres", "-m", "fast", "-w", "stop"], capture=True)
            print("Project database stopped. No system services were changed.")
        elif args.command == "status":
            config = load_config()
            print(f"Database: {'running' if pg_running() else 'stopped'}")
            print(f"Application: {'ready' if healthy(config) else 'not ready'}")
            print(f"Data directory: {DATA}")
        elif args.command == "manage":
            with maintenance_lock(exclusive=True):
                manage(load_config(), args.arguments)
        elif args.command == "test":
            with maintenance_lock(exclusive=False):
                config = load_config()
                start_db(config)
                manage(config, ["test", "drive.tests", "--noinput"], admin=True)
    except (SetupError, OSError, ValueError) as error:
        print(f"\n{error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
