#!/usr/bin/env python3
"""Exercise the running API with two disposable local test accounts.

This creates fixture files; run only against a disposable database/data directory.
Credentials come from DRIVE_TEST_USER_A/PASSWORD_A and USER_B/PASSWORD_B.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import http.cookiejar
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid


class Client:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))

    def request(self, method, path, payload=None, *, raw=None, csrf=True, headers=None):
        request_headers = {"Accept": "application/json"}
        if payload is not None:
            raw = json.dumps(payload).encode()
            request_headers["Content-Type"] = "application/json"
        elif raw is not None:
            request_headers["Content-Type"] = "application/octet-stream"
        if csrf:
            token = next((cookie.value for cookie in self.jar if cookie.name == "csrftoken"), None)
            if token:
                request_headers["X-CSRFToken"] = token
        request_headers.update(headers or {})
        request = urllib.request.Request(self.base_url + path, data=raw, method=method, headers=request_headers)
        try:
            response = self.opener.open(request, timeout=30)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            body = response.read()
            parsed = json.loads(body) if response.headers.get_content_type() == "application/json" else body
            return response.status, parsed, response.headers

    def sign_in(self, username, password):
        status, _, _ = self.request("GET", "/api/session")
        check(status == 401, "anonymous session returns JSON 401")
        check(any(cookie.name == "csrftoken" for cookie in self.jar), "anonymous session initializes CSRF")
        status, _, headers = self.request("POST", "/api/session", {"username": username, "password": password})
        check(status == 200, "fixture authentication succeeds")
        check(any(cookie.name == "sessionid" and cookie.has_nonstandard_attr("HttpOnly") for cookie in self.jar), "session cookie is HttpOnly")
        check("no-store" in headers.get("Cache-Control", ""), "session response prevents caching")


CHECKS = 0


def check(condition, label):
    global CHECKS
    if not condition:
        raise AssertionError(label)
    CHECKS += 1
    print(f"PASS {label}")


def create(client, data, name=None, key=None):
    metadata = {"client_key": key or str(uuid.uuid4()), "name": name or f"acceptance-{uuid.uuid4()}.bin", "size_bytes": len(data)}
    status, upload, _ = client.request("POST", "/api/uploads", metadata)
    check(status == 201, "upload session created")
    return upload, metadata


def send(client, upload_id, data, attempt=None):
    return client.request("PUT", f"/api/uploads/{upload_id}/content", raw=data, headers={"X-Attempt-ID": attempt or str(uuid.uuid4())})


def complete(client, upload_id, data, attempt=None):
    status, upload, _ = send(client, upload_id, data, attempt)
    check(status == 200 and upload["state"] == "COMPLETE", "upload completes only with confirmed File")
    file = upload["file"]
    check(file["size_bytes"] == len(data), "stored size matches content")
    check(file["sha256"] == hashlib.sha256(data).hexdigest(), "stored SHA-256 matches original")
    status, body, headers = client.request("GET", f'/api/files/{file["id"]}/content')
    check(status == 200 and body == data, "private retrieval returns exact original bytes")
    check(headers.get("X-Content-Type-Options") == "nosniff", "download disallows content sniffing")
    check(headers.get("Content-Disposition", "").startswith("attachment"), "download uses attachment disposition")
    return upload


def main():
    base = os.environ.get("DRIVE_TEST_BASE_URL", "http://127.0.0.1:8000")
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise SystemExit("Acceptance tests only accept an HTTP loopback URL.")
    credentials = [(os.environ[f"DRIVE_TEST_USER_{suffix}"], os.environ[f"DRIVE_TEST_PASSWORD_{suffix}"]) for suffix in ("A", "B")]
    check(credentials[0][0] != credentials[1][0], "fixture identities are distinct")
    a, b, anonymous = Client(base), Client(base), Client(base)
    status, _, headers = anonymous.request("GET", "/api/files")
    check(status == 401 and headers.get_content_type() == "application/json", "anonymous file list denied with JSON")
    a.request("GET", "/api/session")
    status, _, _ = a.request("POST", "/api/session", {"username": credentials[0][0], "password": credentials[0][1]}, csrf=False)
    check(status == 403, "login requires CSRF")
    a.sign_in(*credentials[0])
    b.sign_in(*credentials[1])
    status, initial_files, _ = a.request("GET", "/api/files")
    check(status == 200, "initial storage accounting available")
    initial_used = initial_files["storage"]["used_bytes"]
    status, _, _ = a.request("POST", "/api/uploads", {"client_key": str(uuid.uuid4()), "name": "csrf.txt", "size_bytes": 1}, csrf=False)
    check(status == 403, "upload initiation requires CSRF")

    for name, size, expected in [("../escape.txt", 1, 400), ("bad\\name.txt", 1, 400), ("bad\nname.txt", 1, 400), ("\ud800", 1, 400), (".", 1, 400), ("empty.txt", 0, 400), ("negative.txt", -1, 400), ("boolean.txt", True, 400), ("large.bin", 100 * 1024 * 1024 + 1, 413)]:
        status, _, _ = a.request("POST", "/api/uploads", {"client_key": str(uuid.uuid4()), "name": name, "size_bytes": size})
        check(status == expected, f"metadata validation {name!r} / {size!r}")

    data = b"Private upload acceptance fixture\x00\xff\n"
    upload, metadata = create(a, data)
    status, replay, _ = a.request("POST", "/api/uploads", metadata)
    check(status == 200 and replay["id"] == upload["id"], "same client key returns same session")
    status, _, _ = a.request("POST", "/api/uploads", {**metadata, "name": "different.bin"})
    check(status == 409, "idempotency metadata mismatch conflicts")
    status, _, _ = a.request("POST", "/api/uploads", {**metadata, "client_key": str(uuid.uuid4())})
    check(status == 409, "one active upload enforced across requests")
    other_data = b"Other owner's independent upload"
    other_upload, _ = create(b, other_data)
    complete(b, other_upload["id"], other_data)
    status, original_active, _ = a.request("GET", f'/api/uploads/{upload["id"]}')
    check(status == 200 and original_active["state"] == "CREATED", "another owner's upload leaves first owner's active session intact")
    attempt = str(uuid.uuid4())
    saved = complete(a, upload["id"], data, attempt)
    status, replay, _ = send(a, upload["id"], data, attempt)
    check(status == 200 and replay["file"]["id"] == saved["file"]["id"], "repeated completed PUT returns same File")
    status, replay, _ = a.request("GET", f'/api/uploads/{upload["id"]}')
    check(status == 200 and replay["file"]["id"] == saved["file"]["id"], "status reconciles lost response to existing File")
    status, items, headers = a.request("GET", "/api/files")
    check(status == 200 and sum(item["id"] == saved["file"]["id"] for item in items["items"]) == 1, "completed retry produces exactly one list row")
    check(items["storage"]["used_bytes"] == initial_used + len(data) and items["storage"]["reserved_bytes"] == 0, "completed retry charges quota exactly once")
    check("no-store" in headers.get("Cache-Control", ""), "file metadata prevents caching")

    for method, path, raw in [("GET", f'/api/uploads/{upload["id"]}', None), ("GET", f'/api/files/{saved["file"]["id"]}/content', None), ("PUT", f'/api/uploads/{upload["id"]}/content', data)]:
        status, _, _ = b.request(method, path, raw=raw, headers={"X-Attempt-ID": str(uuid.uuid4())})
        check(status == 404, f"second owner denied {method} private object")
    status, items, _ = b.request("GET", "/api/files")
    check(status == 200 and saved["file"]["id"] not in {item["id"] for item in items["items"]}, "second owner cannot list first owner's file")

    retry_data = b"length-mismatch-then-retry"
    interrupted, _ = create(a, retry_data)
    spent_attempt = str(uuid.uuid4())
    status, _, _ = send(a, interrupted["id"], b"short", spent_attempt)
    check(status == 422, "short content is rejected")
    status, state, _ = a.request("GET", f'/api/uploads/{interrupted["id"]}')
    check(status == 200 and state["state"] == "RETRYABLE" and state["file"] is None, "confirmed failed upload exposes no File")
    status, accounting, _ = a.request("GET", "/api/files")
    check(status == 200 and accounting["storage"]["reserved_bytes"] == 0 and accounting["storage"]["used_bytes"] == initial_used + len(data), "failed attempt releases reservation without charging quota")
    status, _, _ = send(a, interrupted["id"], retry_data, spent_attempt)
    check(status == 409, "spent attempt cannot be reused")
    complete(a, interrupted["id"], retry_data)

    # Simultaneous initiation exercises the database-owned active-upload guard.
    clients = [Client(base), Client(base)]
    for client in clients:
        client.sign_in(*credentials[0])
    competing = [{"client_key": str(uuid.uuid4()), "name": f"race-{uuid.uuid4()}.txt", "size_bytes": 4} for _ in clients]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda pair: pair[0].request("POST", "/api/uploads", pair[1]), zip(clients, competing)))
    check(sorted(result[0] for result in results) == [201, 409], "concurrent initiation yields one winner")
    winner = next(result[1] for result in results if result[0] == 201)
    complete(a, winner["id"], b"race")
    status, accounting, _ = a.request("GET", "/api/files")
    check(status == 200 and accounting["storage"]["reserved_bytes"] == 0 and accounting["storage"]["used_bytes"] == initial_used + len(data) + len(retry_data) + 4, "retry and concurrent initiation leave exact final quota accounting")

    status, _, _ = a.request("DELETE", "/api/session")
    check(status == 204, "sign-out succeeds")
    status, _, _ = a.request("GET", "/api/files")
    check(status == 401, "signed-out session loses private access")
    print(f"\n{CHECKS} acceptance checks passed. Fixture files remain in the disposable test data directory.")


if __name__ == "__main__":
    main()
