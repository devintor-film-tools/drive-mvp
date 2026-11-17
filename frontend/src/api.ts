export interface User { id: string; username: string; display_name: string }
export interface Storage { used_bytes: number; reserved_bytes: number; quota_bytes: number }
export interface Session { user: User; storage: Storage; limits: { max_file_bytes: number }; csrf_token: string }
export interface DriveFile { id: string; name: string; size_bytes: number; sha256: string; created_at: string; trashed_at: string | null; revision: number }
export interface Upload {
  id: string;
  name: string;
  state: 'CREATED' | 'RECEIVING' | 'VERIFYING' | 'RETRYABLE' | 'COMPLETE' | 'EXPIRED';
  expected_bytes: number;
  received_bytes: number;
  expires_at: string;
  retry_after_ms: number;
  can_retry: boolean;
  file: DriveFile | null;
  error_code?: string;
}
export interface FileList { items: DriveFile[]; next_cursor: string | null; storage: Storage }

interface ErrorBody { error?: { code?: string; message?: string; request_id?: string; upload_id?: string }; csrf_token?: string }
let csrfToken = '';

export class ApiError extends Error {
  constructor(public status: number, public code: string, public uploadId?: string) {
    super(code);
  }
}

function parseResponse(response: { status: number; ok: boolean }, body: unknown) {
  const parsed = body as ErrorBody;
  if (parsed?.csrf_token) csrfToken = parsed.csrf_token;
  if (!response.ok) throw new ApiError(response.status, parsed?.error?.code ?? 'unavailable', parsed?.error?.upload_id);
  return body;
}

export async function api<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const response = await fetch(`/api${path}`, {
    method,
    credentials: 'same-origin',
    cache: 'no-store',
    headers: { ...(body === undefined ? {} : { 'Content-Type': 'application/json' }), ...(method === 'GET' ? {} : { 'X-CSRFToken': csrfToken }) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = response.status === 204 ? null : await response.json().catch(() => null);
  return parseResponse(response, data) as T;
}

/** Upload progress measures transport only. The returned COMPLETE result is the durability boundary. */
export function sendFile(id: string, file: File, onProgress: (loaded: number) => void): Promise<Upload> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('PUT', `/api/uploads/${encodeURIComponent(id)}/content`);
    xhr.withCredentials = true;
    xhr.timeout = 15 * 60 * 1000;
    xhr.setRequestHeader('Content-Type', 'application/octet-stream');
    xhr.setRequestHeader('X-CSRFToken', csrfToken);
    xhr.setRequestHeader('X-Attempt-ID', crypto.randomUUID());
    xhr.upload.onprogress = (event) => onProgress(Math.min(event.loaded, file.size));
    xhr.upload.onload = () => onProgress(file.size);
    xhr.onerror = xhr.ontimeout = xhr.onabort = () => reject(new ApiError(0, 'unknown_outcome'));
    xhr.onload = () => {
      try {
        const data: unknown = JSON.parse(xhr.responseText);
        resolve(parseResponse({ status: xhr.status, ok: xhr.status >= 200 && xhr.status < 300 }, data) as Upload);
      } catch (error) { reject(error); }
    };
    xhr.send(file);
  });
}

export function errorCopy(error: unknown): string {
  if (!(error instanceof ApiError)) return 'We couldn’t reach your drive. Please try again.';
  switch (error.code.toLowerCase()) {
    case 'file_changed': return 'This file changed in another tab. Refresh the list before trying again.';
    case 'file_trashed': return 'This file is in Trash. Restore it before renaming or downloading.';
    case 'not_found': return 'This file is no longer available here. Refresh the list.';
    case 'file_unavailable': return 'The file couldn’t be downloaded. Please try again.';
    case 'quota_exceeded': case 'quota_full': return 'Storage limit reached. Choose a smaller file.';
    case 'disk_full': case 'device_full': case 'storage_full': return 'This device is out of space. Free some space, then try again.';
    case 'invalid_credentials': return 'The username or password is incorrect.';
    case 'invalid_filename': case 'invalid_name': return 'This filename isn’t supported. Rename the file and try again.';
    case 'upload_expired': return 'This upload has expired. Choose your file again to start a new upload.';
    case 'idempotency_conflict': case 'idempotency_mismatch': case 'metadata_conflict': return 'Choose the same file as before to recover this upload.';
    default:
      if (error.status === 413) return 'File too large. Choose a file up to 100 MiB.';
      if (error.status === 401) return 'Your session ended. Sign in to continue.';
      if (error.status === 403) return 'Your session needs to be refreshed. Reload this page and sign in again.';
      if (error.status === 429) return 'Too many attempts. Please wait a moment and try again.';
      if (error.status === 409) return 'Another upload may be in progress. Check its status before trying again.';
      if (error.status === 507) return 'There isn’t enough space for this file. Choose a smaller file or free some space.';
      if (error.status === 400 || error.status === 422) return 'This file couldn’t be accepted. Check the file and try again.';
      return 'We couldn’t reach your drive. Please try again.';
  }
}

export async function downloadFile(file: DriveFile): Promise<void> {
  const response = await fetch(`/api/files/${encodeURIComponent(file.id)}/content`, { credentials: 'same-origin', cache: 'no-store' });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, body?.error?.code ?? 'file_unavailable');
  }
  const blob = await response.blob();
  if (blob.size !== file.size_bytes) throw new ApiError(503, 'file_unavailable');
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  // Prefer the server's current filename if another tab has renamed the file.
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const encoded = disposition.match(/filename\*=utf-8''([^;]+)/i);
  const quoted = disposition.match(/filename="((?:[^"\\]|\\.)*)"/i);
  let name = file.name;
  if (encoded) { try { name = decodeURIComponent(encoded[1]); } catch { /* keep known name */ } }
  else if (quoted) name = quoted[1].replace(/\\(.)/g, '$1');
  link.download = name;
  document.body.appendChild(link); link.click(); link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
}
