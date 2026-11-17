import hashlib
import json
import logging
import mimetypes
import re
import uuid
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate, login, logout
from django.core import signing
from django.core.exceptions import RequestDataTooBig
from django.db import DatabaseError, connection, transaction
from django.db.models import Q
from django.http import FileResponse, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import services
from .errors import ApiError
from .models import File, LoginThrottle, Upload
from .storage import LocalBlobStore

logger = logging.getLogger("drive")


def error_response(request, code, message, status=400, **details):
    return JsonResponse({"error": {"code": code, "message": message, "request_id": getattr(request, "request_id", ""), **details}}, status=status)


def endpoint(*methods, authenticated=True):
    def decorate(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method not in methods:
                response = error_response(request, "method_not_allowed", "This action is not supported.", 405)
                response["Allow"] = ", ".join(methods)
                return response
            if authenticated and not request.user.is_authenticated:
                return error_response(request, "authentication_required", "Sign in to continue.", 401)
            try:
                return view(request, *args, **kwargs)
            except ApiError as error:
                return error_response(request, error.code, error.message, error.status, **error.details)
            except RequestDataTooBig:
                return error_response(request, "request_too_large", "The request is too large.", 413)
            except DatabaseError:
                logger.warning("database_unavailable request_id=%s", getattr(request, "request_id", ""))
                return error_response(request, "service_unavailable", "Please try again in a moment.", 503)
        return wrapped
    return decorate


def read_json(request):
    if request.content_type != "application/json":
        raise ApiError("invalid_content_type", "Send an application/json request.", 415)
    try:
        data = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise ApiError("invalid_json", "The request could not be read.") from None
    if not isinstance(data, dict):
        raise ApiError("invalid_json", "Send a JSON object.")
    return data


def serialize_account(account):
    return {"used_bytes": account.used_bytes, "reserved_bytes": account.reserved_bytes, "quota_bytes": account.quota_bytes}


def serialize_file(file):
    return {"id": str(file.id), "name": file.display_name, "size_bytes": file.byte_size, "sha256": file.sha256, "created_at": file.created_at.isoformat(), "trashed_at": file.trashed_at.isoformat() if file.trashed_at else None, "revision": file.revision}


def serialize_upload(upload):
    file = File.objects.filter(upload=upload).first() if upload.state == Upload.State.COMPLETE else None
    return {
        "id": str(upload.id), "name": upload.display_name, "state": upload.state,
        "error_code": upload.error_code or None,
        "expected_bytes": upload.expected_bytes, "received_bytes": upload.received_bytes,
        "expires_at": upload.expires_at.isoformat(),
        "retry_after_ms": 1500 if upload.state in Upload.ACTIVE else 0,
        "can_retry": upload.state == Upload.State.RETRYABLE,
        "file": serialize_file(file) if file else None,
    }


def session_payload(request):
    user = request.user
    return {
        "user": {"id": str(user.id), "username": user.username, "display_name": user.get_full_name() or user.username},
        "storage": serialize_account(services.account_for(user)),
        "limits": {"max_file_bytes": settings.MAX_FILE_BYTES},
        "csrf_token": get_token(request),
    }


def check_login_rate(request, username):
    key = hashlib.sha256((request.META.get("REMOTE_ADDR", "") + "\0" + username.casefold()).encode()).hexdigest()
    now = timezone.now()
    with transaction.atomic():
        LoginThrottle.objects.get_or_create(key=key, defaults={"window_started": now})
        throttle = LoginThrottle.objects.select_for_update().get(key=key)
        if throttle.window_started < now - timedelta(minutes=5):
            throttle.window_started = now
            throttle.attempts = 0
        if throttle.attempts >= 20:
            raise ApiError("rate_limited", "Too many sign-in attempts. Try again in five minutes.", 429, retry_after_ms=300000)
        throttle.attempts += 1
        throttle.save()
    return key


@endpoint("GET", "POST", "DELETE", authenticated=False)
def session(request):
    token = get_token(request)  # Also initializes CSRF for the signed-out screen.
    if request.method == "DELETE":
        logout(request)
        return HttpResponse(status=204)
    if request.method == "POST":
        data = read_json(request)
        username, password = data.get("username"), data.get("password")
        if not isinstance(username, str) or not isinstance(password, str) or not 1 <= len(username) <= 150 or not 1 <= len(password) <= 1024:
            raise ApiError("invalid_credentials", "Enter your username and password.", 400)
        try:
            username.encode("utf-8")
            password.encode("utf-8")
        except UnicodeEncodeError:
            raise ApiError("invalid_credentials", "Enter a valid username and password.", 400) from None
        throttle_key = check_login_rate(request, username)
        user = authenticate(request, username=username, password=password)
        if user is None:
            raise ApiError("invalid_credentials", "Username or password is incorrect.", 401)
        login(request, user)
        with transaction.atomic():
            throttle = LoginThrottle.objects.select_for_update().get(key=throttle_key)
            throttle.attempts = 0
            throttle.window_started = timezone.now()
            throttle.save(update_fields=["attempts", "window_started"])
    if not request.user.is_authenticated:
        response = error_response(request, "authentication_required", "Sign in to continue.", 401)
        response.content = json.dumps({**json.loads(response.content), "csrf_token": token}).encode()
        return response
    return JsonResponse(session_payload(request))


@endpoint("GET")
def files(request):
    location = request.GET.get("location", "drive")
    if location not in ("drive", "trash"):
        raise ApiError("invalid_location", "Choose My Drive or Trash.")
    query = File.objects.filter(owner=request.user, trashed_at__isnull=location == "drive").order_by("-created_at", "-id")
    cursor = request.GET.get("cursor")
    if cursor:
        try:
            decoded = signing.loads(cursor, salt="file-list", max_age=86400)
            if decoded["owner"] != str(request.user.id) or decoded.get("location", "drive") != location:
                raise ValueError
            created_at = parse_datetime(decoded["created_at"])
            file_id = uuid.UUID(decoded["id"])
            if created_at is None:
                raise ValueError
        except (signing.BadSignature, ValueError, KeyError, TypeError):
            raise ApiError("invalid_cursor", "Refresh your file list to continue.") from None
        query = query.filter(Q(created_at__lt=created_at) | Q(created_at=created_at, id__lt=file_id))
    try:
        limit = min(max(int(request.GET.get("limit", 100)), 1), 100)
    except ValueError:
        raise ApiError("invalid_limit", "Invalid page size.") from None
    items = list(query[:limit + 1])
    next_cursor = None
    if len(items) > limit:
        items = items[:limit]
        last = items[-1]
        next_cursor = signing.dumps({"owner": str(request.user.id), "location": location, "created_at": last.created_at.isoformat(), "id": str(last.id)}, salt="file-list")
    return JsonResponse({"items": [serialize_file(file) for file in items], "next_cursor": next_cursor, "storage": serialize_account(services.account_for(request.user))})


@endpoint("POST")
def uploads(request):
    upload, created = services.create_upload(request.user, read_json(request))
    return JsonResponse(serialize_upload(upload), status=201 if created else 200)


@endpoint("GET")
def active_upload(request):
    services.reconcile_user(request.user)
    upload = Upload.objects.filter(owner=request.user, state__in=Upload.ACTIVE).first()
    return JsonResponse({"upload": serialize_upload(upload) if upload else None})


@endpoint("GET")
def upload_status(request, upload_id):
    return JsonResponse(serialize_upload(services.get_upload(request.user, upload_id)))


@endpoint("PUT")
def upload_content(request, upload_id):
    if request.content_type != "application/octet-stream":
        raise ApiError("invalid_content_type", "Send the selected file as application/octet-stream.", 415)
    try:
        attempt_id = uuid.UUID(request.headers.get("X-Attempt-ID", ""))
    except ValueError:
        raise ApiError("invalid_attempt", "The upload attempt needs a valid identifier.") from None
    # request.read streams WSGI input; request.body would buffer the complete file.
    upload = services.receive_upload(request.user, upload_id, attempt_id, request)
    return JsonResponse(serialize_upload(upload))


@endpoint("PATCH")
def file_detail(request, file_id):
    data = read_json(request)
    if set(data) not in ({"name", "revision"}, {"trashed", "revision"}):
        raise ApiError("invalid_change", "Change one file property at a time.")
    revision = data["revision"]
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise ApiError("invalid_revision", "Refresh your file list.")
    if "name" in data:
        services.validate_name(data["name"])
    elif not isinstance(data["trashed"], bool):
        raise ApiError("invalid_change", "Use a boolean trash state.")
    with transaction.atomic():
        try:
            file = File.objects.select_for_update().get(id=file_id, owner=request.user)
        except File.DoesNotExist:
            raise ApiError("not_found", "File not found.", 404) from None
        if file.revision != revision:
            raise ApiError("file_changed", "This file changed. Refresh before trying again.", 409)
        if "name" in data:
            if file.trashed_at:
                raise ApiError("file_trashed", "Restore the file before renaming it.", 409)
            changed = file.display_name != data["name"]
            file.display_name = data["name"]
        else:
            changed = bool(file.trashed_at) != data["trashed"]
            if changed:
                file.trashed_at = timezone.now() if data["trashed"] else None
        if changed:
            file.revision += 1
            file.save(update_fields=["display_name", "trashed_at", "revision"])
        return JsonResponse(serialize_file(file))


@endpoint("GET")
def download(request, file_id):
    try:
        file = File.objects.get(id=file_id, owner=request.user, trashed_at__isnull=True)
    except File.DoesNotExist:
        raise ApiError("not_found", "File not found.", 404) from None
    try:
        store = LocalBlobStore()
        if store.inspect(file.blob_key).st_size != file.byte_size:
            raise OSError("Blob length mismatch")
        handle = store.open(file.blob_key)
    except OSError:
        logger.warning("blob_unavailable file_id=%s", file.id)
        raise ApiError("file_unavailable", "This file is temporarily unavailable.", 503) from None
    response = FileResponse(handle, as_attachment=True, filename=file.display_name, content_type="application/octet-stream")
    response["ETag"] = f'"{file.sha256}"'
    return response


@endpoint("GET", authenticated=False)
def health(request):
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()
    try:
        LocalBlobStore()
    except OSError:
        raise ApiError("storage_unavailable", "Storage is not ready.", 503) from None
    return JsonResponse({"status": "ok"})


def frontend(request):
    path = settings.FRONTEND_DIST / "index.html"
    if request.method not in ("GET", "HEAD"):
        return error_response(request, "method_not_allowed", "This action is not supported.", 405)
    if not path.is_file():
        return HttpResponse("The interface has not been built. Run the local setup command.", status=503, content_type="text/plain")
    response = FileResponse(path.open("rb"), content_type="text/html")
    response["Cache-Control"] = "no-store"
    response["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    return response


def frontend_asset(request, asset):
    root = (settings.FRONTEND_DIST / "assets").resolve()
    path = (root / asset).resolve()
    if request.method not in ("GET", "HEAD") or not path.is_relative_to(root) or not path.is_file():
        return not_found(request, None)
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    response = FileResponse(path.open("rb"), content_type=mime)
    response["Cache-Control"] = "public, max-age=31536000, immutable" if re.search(r"-[A-Za-z0-9_-]{8,}\.", path.name) else "no-cache"
    return response


def csrf_failure(request, reason=""):
    return error_response(request, "csrf_rejected", "Your session needs to be refreshed. Please reload this page.", 403)


def not_found(request, exception):
    return error_response(request, "not_found", "This page or resource was not found.", 404)


def server_error(request):
    return error_response(request, "internal_error", "Something went wrong. Please try again.", 500)


def bad_request(request, exception):
    return error_response(request, "invalid_request", "The request could not be accepted.", 400)
