import type { Upload } from './api';

export type Recovery = 'complete' | 'wait' | 'retry' | 'reselect' | 'expired';

/** No timeout or transport error is interpreted as proof of failure. */
export function recoveryFor(upload: Upload, hasFile: boolean): Recovery {
  switch (upload.state) {
    case 'COMPLETE': return upload.file ? 'complete' : 'wait';
    case 'CREATED': case 'RETRYABLE': return hasFile ? 'retry' : 'reselect';
    case 'EXPIRED': return 'expired';
    default: return 'wait';
  }
}

export function matchesSelection(upload: Upload, file: Pick<File, 'name' | 'size'>): boolean {
  return upload.name === file.name && upload.expected_bytes === file.size;
}

export interface RecoveryToken { owner: string; id?: string; key?: string }
const TOKEN_KEY = 'drive.pending-upload';
export function readToken(owner: string): RecoveryToken | null {
  try {
    const item: unknown = JSON.parse(sessionStorage.getItem(TOKEN_KEY) ?? 'null');
    if (!item || typeof item !== 'object') return null;
    const token = item as RecoveryToken;
    if (token.owner !== owner) return null;
    return typeof token.id === 'string' || typeof token.key === 'string' ? token : null;
  } catch { return null; }
}
export function remember(token: RecoveryToken | null) {
  try {
    if (token) sessionStorage.setItem(TOKEN_KEY, JSON.stringify(token));
    else sessionStorage.removeItem(TOKEN_KEY);
  } catch { /* Server reconciliation still works when browser storage is unavailable. */ }
}

export function formatBytes(bytes: number): string {
  if (bytes < 1000) return `${bytes} B`;
  if (bytes < 1_000_000) return `${(bytes / 1000).toFixed(1)} KB`;
  if (bytes < 1_000_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
}

export function formatLimit(bytes: number): string {
  return bytes >= 1024 ** 3 ? `${bytes / 1024 ** 3} GiB` : `${bytes / 1024 ** 2} MiB`;
}
