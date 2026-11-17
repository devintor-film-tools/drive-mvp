import { useCallback, useEffect, useRef, useState } from 'react';
import { api, ApiError, errorCopy, sendFile, downloadFile } from './api';
import type { DriveFile, FileList, Session, Upload } from './api';
import { matchesSelection, readToken, recoveryFor, remember } from './recovery';

export type Phase = 'idle' | 'creating' | 'uploading' | 'finishing' | 'waiting' | 'unknown' | 'retryable' | 'reselect' | 'complete' | 'error' | 'expired';
export interface Panel { phase: Phase; name: string; sent: number; size: number; upload?: Upload; message?: string; title?: string }
const idle: Panel = { phase: 'idle', name: '', sent: 0, size: 0 };

export function useDrive() {
  const [location, setLocation] = useState<'drive' | 'trash'>('drive');
  const locationRef = useRef<'drive' | 'trash'>('drive');
  const listRequest = useRef(0);
  const actionLock = useRef(false);
  const [actionBusy, setActionBusy] = useState(false);
  const [actionMessage, setActionMessage] = useState('');
  const [actionError, setActionError] = useState('');
  const [session, setSession] = useState<Session | null>(null);
  const [authState, setAuthState] = useState<'loading' | 'signed-out' | 'ready' | 'unavailable'>('loading');
  const [authError, setAuthError] = useState('');
  const [files, setFiles] = useState<DriveFile[]>([]);
  const [listState, setListState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [cursor, setCursor] = useState<string | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [panel, setPanel] = useState<Panel>(idle);
  const current = useRef<Session | null>(null);
  const picked = useRef<File | null>(null);
  const pendingKey = useRef<string | null>(null);
  const locked = useRef(false);
  const identityEpoch = useRef(0);

  function expireSession() {
    identityEpoch.current++;
    current.current = null;
    picked.current = null;
    pendingKey.current = null;
    locked.current = false;
    setSession(null);
    setFiles([]);
    setActionMessage('');
    setActionError('');
    setPanel(idle);
    setAuthState('signed-out');
    setAuthError('Your session ended. Sign in to continue.');
  }

  const loadFiles = useCallback(async (next?: string) => {
    const epoch = identityEpoch.current;
    const request = ++listRequest.current;
    if (!next) setListState('loading'); else setLoadingMore(true);
    try {
      const result = await api<FileList>(`/files?location=${locationRef.current}${next ? `&cursor=${encodeURIComponent(next)}` : ''}`);
      if (epoch !== identityEpoch.current || request !== listRequest.current) return;
      setFiles((previous) => next ? [...previous, ...result.items.filter((file) => !previous.some((old) => old.id === file.id))] : result.items);
      setCursor(result.next_cursor);
      setListState('ready');
      if (current.current && result.storage) {
        current.current = { ...current.current, storage: result.storage };
        setSession(current.current);
      }
    } catch (error) {
      if (epoch !== identityEpoch.current || request !== listRequest.current) return;
      if (error instanceof ApiError && error.status === 401) expireSession();
      else setListState('error');
    } finally { if (epoch === identityEpoch.current && request === listRequest.current) setLoadingMore(false); }
  }, []);

  function applyUpload(upload: Upload) {
    const hasFile = !!picked.current && matchesSelection(upload, picked.current);
    const recovery = recoveryFor(upload, hasFile);
    const failureStatus: Record<string, number> = { quota_exceeded: 507, device_full: 507, storage_unavailable: 503, size_mismatch: 422 };
    const message = upload.error_code && upload.error_code in failureStatus ? errorCopy(new ApiError(failureStatus[upload.error_code], upload.error_code)) : undefined;
    const base = { name: upload.name, size: upload.expected_bytes, sent: upload.received_bytes, upload, message };
    if (recovery === 'complete') {
      remember(null);
      picked.current = null;
      pendingKey.current = null;
      setPanel({ ...base, phase: 'complete' });
      void loadFiles();
    } else if (recovery === 'expired') {
      remember(null);
      setPanel({ ...base, phase: 'expired' });
    } else {
      if (current.current) remember({ owner: current.current.user.id, id: upload.id });
      setPanel({ ...base, phase: recovery === 'retry' ? 'retryable' : recovery === 'reselect' ? 'reselect' : 'waiting' });
    }
  }

  async function reconcile(id: string, transferError?: unknown) {
    const epoch = identityEpoch.current;
    try {
      const upload = await api<Upload>(`/uploads/${encodeURIComponent(id)}`);
      if (epoch === identityEpoch.current) {
        applyUpload(upload);
        if (['CREATED', 'RETRYABLE'].includes(upload.state) && transferError instanceof ApiError && [403, 413, 422, 507].includes(transferError.status)) {
          setPanel((old) => ({ ...old, message: errorCopy(transferError) }));
        }
      }
    } catch (error) {
      if (epoch !== identityEpoch.current) return;
      if (error instanceof ApiError && error.status === 401) expireSession();
      else if (error instanceof ApiError && (error.status === 404 || error.status === 410)) {
        remember(null);
        setPanel({ ...idle, phase: 'expired' });
      } else setPanel((old) => ({ ...old, phase: 'unknown' }));
    }
  }

  async function restore(loaded: Session) {
    identityEpoch.current++;
    const epoch = identityEpoch.current;
    current.current = loaded;
    picked.current = null;
    setSession(loaded);
    setFiles([]);
    setActionMessage('');
    setActionError('');
    setPanel(idle);
    setAuthError('');
    setAuthState('ready');
    const token = readToken(loaded.user.id);
    pendingKey.current = token?.key ?? null;
    try {
      const active = await api<{ upload: Upload | null }>('/uploads/active');
      if (epoch !== identityEpoch.current) return;
      if (active.upload) applyUpload(active.upload);
      else if (token?.id) await reconcile(token.id);
      else if (token?.key) setPanel({ ...idle, phase: 'reselect', message: 'Choose the same file you selected before refresh to check this upload.' });
    } catch (error) {
      if (epoch !== identityEpoch.current) return;
      if (error instanceof ApiError && error.status === 401) { expireSession(); return; }
      setPanel({ ...idle, phase: 'unknown', message: 'Checking whether another upload is in progress…' });
    }
    if (epoch === identityEpoch.current) await loadFiles();
  }

  async function initialize() {
    const epoch = ++identityEpoch.current;
    setAuthState('loading');
    try {
      const loaded = await api<Session>('/session');
      if (epoch === identityEpoch.current) await restore(loaded);
    }
    catch (error) {
      if (epoch === identityEpoch.current) setAuthState(error instanceof ApiError && error.status === 401 ? 'signed-out' : 'unavailable');
    }
  }

  useEffect(() => { void initialize(); }, []);
  useEffect(() => {
    if (panel.phase !== 'waiting' || !panel.upload) return;
    const delay = Math.max(1000, Math.min(10_000, panel.upload.retry_after_ms || 2000));
    const timer = window.setTimeout(() => void reconcile(panel.upload!.id), delay);
    return () => window.clearTimeout(timer);
  }, [panel]);
  useEffect(() => {
    if (!['creating', 'uploading', 'finishing', 'waiting', 'unknown'].includes(panel.phase)) return;
    const beforeUnload = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', beforeUnload);
    return () => window.removeEventListener('beforeunload', beforeUnload);
  }, [panel.phase]);

  async function signIn(username: string, password: string) {
    const epoch = ++identityEpoch.current;
    setAuthError('');
    try {
      // Refresh CSRF even when recovering from an expired session.
      await api<Session>('/session').catch((error) => { if (!(error instanceof ApiError && error.status === 401)) throw error; });
      if (epoch !== identityEpoch.current) return;
      const loaded = await api<Session>('/session', 'POST', { username, password });
      if (epoch === identityEpoch.current) await restore(loaded);
    } catch (error) { if (epoch === identityEpoch.current) setAuthError(errorCopy(error)); }
  }

  async function signOut() {
    const epoch = identityEpoch.current;
    try {
      await api('/session', 'DELETE');
      if (epoch !== identityEpoch.current) return;
      identityEpoch.current++;
      current.current = null;
      picked.current = null;
      pendingKey.current = null;
      locked.current = false;
      setSession(null); setFiles([]); setPanel(idle); setAuthError(''); setAuthState('signed-out');
    } catch (error) { if (epoch === identityEpoch.current) setAuthError(errorCopy(error)); }
  }

  async function transfer(upload: Upload, file: File) {
    const epoch = identityEpoch.current;
    setPanel({ phase: 'uploading', name: file.name, size: file.size, sent: 0, upload });
    try {
      const result = await sendFile(upload.id, file, (sent) => {
        if (epoch === identityEpoch.current) setPanel((old) => ({ ...old, sent, phase: sent >= file.size ? 'finishing' : 'uploading' }));
      });
      if (epoch === identityEpoch.current) applyUpload(result);
    } catch (error) {
      if (epoch !== identityEpoch.current) return;
      if (error instanceof ApiError && error.status === 401) { expireSession(); return; }
      setPanel((old) => ({ ...old, phase: 'unknown' }));
      await reconcile(error instanceof ApiError && error.uploadId ? error.uploadId : upload.id, error);
    }
  }

  async function createAndTransfer(file: File, key: string) {
    const epoch = identityEpoch.current;
    const owner = current.current?.user.id;
    if (!owner) return;
    pendingKey.current = key;
    remember({ owner, key });
    setPanel({ phase: 'creating', name: file.name, size: file.size, sent: 0 });
    let upload: Upload;
    try {
      upload = await api<Upload>('/uploads', 'POST', { client_key: key, name: file.name, size_bytes: file.size });
    } catch (error) {
      if (epoch !== identityEpoch.current) return;
      if (error instanceof ApiError && error.status === 401) { expireSession(); return; }
      if (error instanceof ApiError && error.uploadId) { await reconcile(error.uploadId); return; }
      if (!(error instanceof ApiError) || (error.status >= 500 && error.status !== 507) || error.status === 0) {
        setPanel({ phase: 'unknown', name: file.name, size: file.size, sent: 0 });
      } else {
        setPanel({ phase: 'error', name: file.name, size: file.size, sent: 0, message: errorCopy(error), title: error.status === 413 ? 'File too large' : 'Upload couldn’t start' });
      }
      return;
    }
    if (epoch !== identityEpoch.current) return;
    remember({ owner, id: upload.id });
    if (upload.state === 'CREATED' || upload.state === 'RETRYABLE') await transfer(upload, file);
    else applyUpload(upload);
  }

  async function selectFile(file: File, retry = false) {
    if (locked.current || !current.current) return;
    const epoch = identityEpoch.current;
    if (file.size === 0 || file.size > current.current.limits.max_file_bytes) {
      setPanel({ phase: 'error', name: file.name, sent: 0, size: file.size, title: file.size === 0 ? 'This file is empty' : 'File too large', message: file.size === 0 ? 'Choose a file with content to upload.' : `Choose a file up to ${current.current.limits.max_file_bytes / 1024 ** 2} MiB.` });
      return;
    }
    if (retry && panel.upload && !matchesSelection(panel.upload, file)) {
      setPanel((old) => ({ ...old, phase: 'reselect', message: `Choose ${old.name} with the original file size to retry this upload.` }));
      return;
    }
    locked.current = true;
    picked.current = file;
    try {
      if (retry && panel.upload) {
        // A retry always rechecks current server status before it can send bytes.
        const latest = await api<Upload>(`/uploads/${panel.upload.id}`);
        if (epoch !== identityEpoch.current) return;
        if (latest.state === 'CREATED' || latest.state === 'RETRYABLE') await transfer(latest, file);
        else applyUpload(latest);
      } else await createAndTransfer(file, retry && pendingKey.current ? pendingKey.current : crypto.randomUUID());
    } catch (error) {
      if (epoch !== identityEpoch.current) return;
      if (error instanceof ApiError && error.status === 401) expireSession();
      else setPanel((old) => ({ ...old, phase: 'unknown' }));
    } finally { if (epoch === identityEpoch.current) locked.current = false; }
  }

  async function checkAgain() {
    if (locked.current) return;
    const epoch = identityEpoch.current;
    if (panel.upload) { await reconcile(panel.upload.id); return; }
    if (picked.current && pendingKey.current) {
      locked.current = true;
      try { await createAndTransfer(picked.current, pendingKey.current); } finally { if (epoch === identityEpoch.current) locked.current = false; }
      return;
    }
    if (current.current) await restore(current.current);
  }

  function retryHeldFile(): boolean {
    if (!picked.current) return false;
    void selectFile(picked.current, true);
    return true;
  }

  function changeLocation(value: 'drive' | 'trash') {
    locationRef.current = value;
    setLocation(value);
    setFiles([]);
    setCursor(null);
    setActionMessage(''); setActionError('');
    void loadFiles();
  }

  async function fileAction(file: DriveFile, action: 'download' | 'rename' | 'trash' | 'restore', name?: string): Promise<boolean> {
    if (actionLock.current) return false;
    actionLock.current = true; setActionBusy(true);
    setActionMessage(''); setActionError('');
    const epoch = identityEpoch.current;
    try {
      if (action === 'download') {
        setActionMessage('Preparing download…');
        await downloadFile(file);
        if (epoch === identityEpoch.current) setActionMessage('Download sent to your browser. Check your downloads.');
      } else {
        await api<DriveFile>(`/files/${file.id}`, 'PATCH', { revision: file.revision, ...(action === 'rename' ? { name } : { trashed: action === 'trash' }) });
        if (epoch !== identityEpoch.current) return false;
        setActionMessage(action === 'rename' ? 'File renamed.' : action === 'trash' ? 'File moved to Trash. You can restore it from Trash.' : 'File restored to My Drive.');
        await loadFiles();
      }
      return epoch === identityEpoch.current;
    } catch (error) {
      if (epoch !== identityEpoch.current) return false;
      setActionMessage('');
      if (error instanceof ApiError && error.status === 401) expireSession();
      else {
        const message = error instanceof ApiError ? errorCopy(error) : 'We couldn’t confirm the action. Refresh the list to check before trying again.';
        setActionError(message);
      }
      return false;
    } finally { actionLock.current = false; setActionBusy(false); }
  }

  const busy = actionBusy || ['creating', 'uploading', 'finishing', 'waiting', 'unknown'].includes(panel.phase);
  return { location, changeLocation, actionBusy, actionMessage, actionError, fileAction, session, authState, authError, files, listState, cursor, loadingMore, panel, busy, signIn, signOut, initialize, loadFiles, selectFile, checkAgain, retryHeldFile, dismiss: () => setPanel(idle) };
}
