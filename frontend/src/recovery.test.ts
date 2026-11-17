import { describe, expect, it } from 'vitest';
import { matchesSelection, recoveryFor } from './recovery';
import type { Upload } from './api';

const pending: Upload = { id: 'upload', name: 'notes.txt', state: 'RECEIVING', expected_bytes: 16, received_bytes: 16, expires_at: '', retry_after_ms: 2000, can_retry: false, file: null };

describe('uncertain upload recovery', () => {
  it('does not equate all bytes sent with a saved file or permission to retry', () => {
    expect(recoveryFor(pending, true)).toBe('wait');
    expect(recoveryFor({ ...pending, state: 'VERIFYING' }, true)).toBe('wait');
  });
  it('requires a final File before announcing completion', () => {
    expect(recoveryFor({ ...pending, state: 'COMPLETE' }, true)).toBe('wait');
    expect(recoveryFor({ ...pending, state: 'COMPLETE', file: { id: 'file', name: 'notes.txt', size_bytes: 16, sha256: 'hash', created_at: '', trashed_at: null, revision: 1 } }, false)).toBe('complete');
  });
  it('requires reselection after reload, while allowing a held file to retry', () => {
    expect(recoveryFor({ ...pending, state: 'RETRYABLE' }, false)).toBe('reselect');
    expect(recoveryFor({ ...pending, state: 'RETRYABLE' }, true)).toBe('retry');
  });
  it('does not reuse an expired session or a mismatched selection', () => {
    expect(recoveryFor({ ...pending, state: 'EXPIRED' }, true)).toBe('expired');
    expect(matchesSelection(pending, { name: 'different.txt', size: 16 })).toBe(false);
    expect(matchesSelection(pending, { name: 'notes.txt', size: 17 })).toBe(false);
  });
});
