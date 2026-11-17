"""Local-first settings: PostgreSQL is required, private data stays outside Git."""
import os
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BASE_DIR.parent
SECRET_KEY = os.environ.get("DRIVE_SECRET_KEY", "")
if len(SECRET_KEY) < 32:
    raise ImproperlyConfigured("Set DRIVE_SECRET_KEY to a random value of at least 32 characters.")
DEBUG = False
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]"]
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
INSTALLED_APPS = ["django.contrib.auth", "django.contrib.contenttypes", "django.contrib.sessions", "drive"]
MIDDLEWARE = [
    "drive.middleware.RequestMetadataMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]
AUTH_USER_MODEL = "drive.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
database_url = urlparse(os.environ.get("DATABASE_URL", "postgresql://drive_mvp@127.0.0.1:54329/drive_mvp"))
if database_url.scheme not in {"postgres", "postgresql"}:
    raise ImproperlyConfigured("DATABASE_URL must point to PostgreSQL; SQLite is not supported.")
DATABASES = {"default": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": unquote(database_url.path.lstrip("/")),
    "USER": unquote(database_url.username or ""),
    "PASSWORD": unquote(database_url.password or ""),
    "HOST": database_url.hostname or "127.0.0.1",
    "PORT": database_url.port or 5432,
    "CONN_MAX_AGE": 0,
    "OPTIONS": {"connect_timeout": 5},
}}
query = parse_qs(database_url.query)
if "sslmode" in query:
    DATABASES["default"]["OPTIONS"]["sslmode"] = query["sslmode"][0]
DRIVE_DATA_DIR = Path(os.environ.get("DRIVE_DATA_DIR", "~/.local/share/drive-mvp")).expanduser().resolve()
if DRIVE_DATA_DIR == REPO_DIR or DRIVE_DATA_DIR.is_relative_to(REPO_DIR):
    raise ImproperlyConfigured("DRIVE_DATA_DIR must be outside the Git repository.")
FRONTEND_DIST = REPO_DIR / "frontend" / "dist"
MAX_FILE_BYTES = 100 * 1024 * 1024
DEFAULT_QUOTA_BYTES = 1024 * 1024 * 1024
UPLOAD_LEASE_SECONDS = 120
UPLOAD_RENEW_SECONDS = 15
UPLOAD_MAX_SECONDS = 60 * 60
UPLOAD_SESSION_SECONDS = 24 * 60 * 60
ORPHAN_GRACE_SECONDS = 24 * 60 * 60
DISK_HEADROOM_BYTES = 16 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 8192
DATA_UPLOAD_MAX_NUMBER_FIELDS = 20
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Strict"
CSRF_COOKIE_SAMESITE = "Strict"
CSRF_FAILURE_VIEW = "drive.views.csrf_failure"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
USE_TZ = True
TIME_ZONE = "UTC"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "loggers": {"drive": {"handlers": ["console"], "level": "INFO", "propagate": False}},
}
