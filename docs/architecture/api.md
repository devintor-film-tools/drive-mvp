# First-upload HTTP contract

Date: 2026-11-16 · Status: implemented contract; runtime validation pending
Owner: engineering lead

Same-origin JSON API, authenticated Django session, CSRF token on mutations. UUIDs are opaque identifiers, not credentials. UTC timestamps use RFC 3339. All integer sizes are bytes. Server returns `Cache-Control: no-store` for private metadata/status. Use request IDs for diagnosis.

| Method/path | Request | Successful result |
| --- | --- | --- |
| GET /api/session | — | 200 user UUID and CSRF initialization; 401 if signed out |
| POST /api/session | username, password; CSRF required | 200 authenticated user; rotate session |
| DELETE /api/session | CSRF required | 204, invalidate session |
| GET /api/files?cursor=… | Optional opaque cursor; limit capped at 100 | 200 `{items: File[], next_cursor: string|null}` sorted by created_at then UUID descending |
| POST /api/uploads | `{client_key: UUID, name: string, size_bytes: integer}` | 201 new Upload; 200 existing Upload for same key and identical metadata |
| PUT /api/uploads/{id}/content | Raw application/octet-stream; X-Attempt-ID UUID; declared length checked while streaming | 200 COMPLETE Upload with File after finalization |
| GET /api/uploads/{id} | — | 200 Upload with current state and recovery instructions |
| GET /api/uploads/active | — | 200 `{upload: Upload|null}` for initial reconciliation; route resolves before UUID route |
| GET /api/files/{id}/content | — | 200 authorized attachment; internal integrity probe initially, user-facing download deferred |
| GET /api/health | — | 200 `{status: "ok"}` after database and storage readiness checks; no user data |

`File = {id, name, size_bytes, sha256, created_at}`. Owner and blob paths are never client-selected. `Upload = {id, name, state, expected_bytes, received_bytes, expires_at, retry_after_ms, can_retry, error_code, file: File|null}`. `error_code` preserves a confirmed attempt failure for actionable recovery after refresh. RECEIVING status bytes are last persisted telemetry, not a durable completion guarantee. Browser send progress is local transport progress. Only COMPLETE returns a non-null File.

Authenticated session payload: `{user: {id, username, display_name}, storage: {used_bytes, reserved_bytes, quota_bytes}, limits: {max_file_bytes}, csrf_token}`. The signed-out 401 also contains `csrf_token` for protected sign-in. File-list responses include current `storage` accounting alongside `items` and `next_cursor`.

`Error = {error: {code, message, request_id, retry_after_ms?, upload_id?}}`. The UI maps stable codes to approved copy; it does not display raw exceptions. 400 invalid metadata; 401 session expired; 403 CSRF rejected; 404 absent/not owned; 409 active upload, metadata/idempotency mismatch, spent attempt or stale generation; 410 upload expired; 413 file too large; 422 content length mismatch; 429 rate limit; 507 quota/full disk; 503 temporary storage/database failure. Distinguish quota from device-full using error.code.

On unknown PUT outcome, GET status before retransmission. COMPLETE returns its existing result; RECEIVING/VERIFYING waits; RETRYABLE permits a new attempt UUID; EXPIRED requires a fresh upload key and file reselection. If reconciliation is unavailable, show “Checking whether your file was saved…” and a Check again action. Never assert “not saved” until the server confirms RETRYABLE/EXPIRED. A concurrent replay of the same attempt returns 409 with its current state, not another stream.

Post-refresh the browser fetches active status, then files. A browser cannot promise access to the previously selected local file after refresh; require reselection for retry and verify name/size against the session before accepting it. Failure after session expiry requires sign-in and reconciliation before any retry. Retain only opaque upload IDs in browser storage, never credentials or file bytes.

API authentication needs an ordinary local sign-in screen for the seeded user. This is an implementation prerequisite; the detailed prototype starts in an already authenticated workspace. No external identity provider or email service is required.
