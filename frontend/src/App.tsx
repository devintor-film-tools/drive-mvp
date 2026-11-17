import { useEffect, useRef, useState } from 'react';
import type { FormEvent, KeyboardEvent } from 'react';
import { FileActions } from './FileActions';
import { useDrive } from './useDrive';
import { formatBytes, formatLimit } from './recovery';
import type { Panel } from './useDrive';

function Attachment() { return <span className="attachment" aria-hidden="true"><img src="/assets/attach.svg" alt="" /></span>; }
function UploadIcon() { return <span className="upload-icon" aria-hidden="true"><img src="/assets/upload.svg" alt="" /></span>; }

function panelTitle(panel: Panel) {
  switch (panel.phase) {
    case 'creating': return 'Preparing upload…';
    case 'uploading': return 'Uploading 1 item';
    case 'finishing': return 'Finishing upload…';
    case 'waiting': case 'unknown': return 'Checking upload…';
    case 'retryable': return 'Upload interrupted';
    case 'reselect': return 'Choose your file again';
    case 'complete': return '1 upload complete';
    case 'expired': return 'Upload expired';
    default: return panel.title ?? 'Upload couldn’t start';
  }
}

function UploadPanel({ panel, retry, choose, check, dismiss }: { panel: Panel; retry: () => void; choose: () => void; check: () => void; dismiss: () => void }) {
  if (panel.phase === 'idle') return null;
  const percent = panel.size ? Math.min(100, Math.floor(panel.sent / panel.size * 100)) : 0;
  const failed = ['retryable', 'error', 'expired'].includes(panel.phase);
  return <section className="upload-panel" aria-labelledby="upload-heading">
    <h2 id="upload-heading" className={failed ? 'error-color' : ''}><span role={failed ? 'alert' : undefined}>{panelTitle(panel)}</span></h2>
    {panel.name && <div className="upload-file"><Attachment /><span title={panel.name}>{panel.name}</span></div>}
    {panel.phase === 'uploading' && <>
      <p className="caption">{formatBytes(panel.sent)} of {formatBytes(panel.size)} · {percent}%</p>
      <progress aria-label={`Uploading ${panel.name}`} max={panel.size} value={panel.sent} />
      <p className="caption">Keep this tab open until the upload finishes.</p>
    </>}
    {panel.phase === 'creating' && <p className="caption">Checking space for your file.</p>}
    {panel.phase === 'finishing' && <><p className="caption">All bytes sent</p><p className="caption">Confirming that your file is safely stored.</p></>}
    {(panel.phase === 'waiting' || panel.phase === 'unknown') && <>
      <p className="caption">{panel.message ?? 'Checking whether your file was saved…'}</p>
      <p className="caption">Wait for confirmation before uploading again.</p>
      {panel.phase === 'unknown' && <button className="text-button" onClick={check}>Check again</button>}
    </>}
    {panel.phase === 'complete' && <><p className="caption">Saved to My Drive</p><p className="caption">Your file is ready.</p><button className="text-button" onClick={dismiss}>Dismiss</button></>}
    {panel.phase === 'retryable' && <><p className="caption">Your file was not saved.</p><p className="caption">{panel.message ?? 'Retry will restart this upload. No duplicate will be created.'}</p><button className="text-button" onClick={retry}>Retry</button></>}
    {panel.phase === 'reselect' && <><p className="caption">{panel.message ?? 'Select the same file again to retry this upload.'}</p><button className="text-button" onClick={retry}>Choose file</button></>}
    {panel.phase === 'expired' && <><p className="caption">Choose your file again to start a new upload.</p><button className="text-button" onClick={choose}>Choose file</button></>}
    {panel.phase === 'error' && <><p className="caption" role="alert">{panel.message}</p><button className="text-button" onClick={choose}>Choose another file</button></>}
  </section>;
}

export default function App() {
  const drive = useDrive();
  const [menu, setMenu] = useState(false);
  const [signingIn, setSigningIn] = useState(false);
  const picker = useRef<HTMLInputElement>(null);
  const newButton = useRef<HTMLButtonElement>(null);
  const menuItem = useRef<HTMLButtonElement>(null);
  const newControl = useRef<HTMLDivElement>(null);
  const heading = useRef<HTMLHeadingElement>(null);
  const retrySelection = useRef(false);

  useEffect(() => {
    const input = picker.current;
    const restoreFocus = () => newButton.current?.focus();
    input?.addEventListener('cancel', restoreFocus);
    return () => input?.removeEventListener('cancel', restoreFocus);
  }, [drive.authState]);

  useEffect(() => {
    if (!menu) return;
    menuItem.current?.focus();
    const close = (event: PointerEvent) => { if (!newControl.current?.contains(event.target as Node)) setMenu(false); };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [menu]);

  function openPicker(retry = false) {
    retrySelection.current = retry;
    setMenu(false);
    picker.current?.click();
  }
  function menuKey(event: KeyboardEvent) {
    if (event.key === 'Escape') { event.preventDefault(); setMenu(false); newButton.current?.focus(); }
    if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) { event.preventDefault(); menuItem.current?.focus(); }
    if (event.key === 'Tab') setMenu(false);
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setSigningIn(true);
    try { await drive.signIn(String(data.get('username')), String(data.get('password'))); }
    finally { setSigningIn(false); }
  }

  if (drive.authState === 'loading') return <main className="entry-shell"><div className="entry-card" role="status"><h1>Drive</h1><p>Opening your drive…</p></div></main>;
  if (drive.authState === 'unavailable') return <main className="entry-shell"><div className="entry-card"><h1>Drive is unavailable</h1><p>We couldn’t connect. Please try again.</p><button className="primary-button" onClick={() => void drive.initialize()}>Try again</button></div></main>;
  if (!drive.session) return <main className="entry-shell"><form className="entry-card" onSubmit={submit}>
    <div className="wordmark">Drive</div><h1>Sign in</h1><p>Your files, stored privately on this device.</p>
    <label htmlFor="username">Username</label><input id="username" name="username" autoComplete="username" required autoFocus disabled={signingIn} />
    <label htmlFor="password">Password</label><input id="password" name="password" type="password" autoComplete="current-password" required disabled={signingIn} />
    {drive.authError && <p className="form-error" role="alert">{drive.authError}</p>}
    <button className="primary-button" disabled={signingIn}>{signingIn ? 'Signing in…' : 'Sign in'}</button>
  </form></main>;

  const { session, panel } = drive;
  const hasPanel = panel.phase !== 'idle';
  const inFlight = ['creating', 'uploading', 'finishing'].includes(panel.phase);
  const checking = panel.phase === 'waiting' || panel.phase === 'unknown';
  const liveMessage = ['idle', 'retryable', 'error', 'expired'].includes(panel.phase) ? '' : panelTitle(panel);

  return <div className="app">
    <a className="skip-link" href="#drive-heading">Skip to files</a>
    <header className="app-header"><span className="wordmark">Drive</span><div className="account"><span>{session.user.display_name || session.user.username}</span><button className="text-button sign-out" disabled={drive.busy} onClick={() => void drive.signOut()}>Sign out</button></div></header>
    <div className="workspace">
      <aside className="sidebar" aria-label="Drive navigation">
        <div className="new-control" ref={newControl} onKeyDown={menuKey}>
          <button className="new-button" ref={newButton} aria-haspopup="menu" aria-expanded={menu} aria-controls={menu ? 'new-menu' : undefined} disabled={drive.busy} onClick={() => setMenu((old) => !old)} onKeyDown={(event) => { if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); setMenu(true); } }}><img src="/assets/add.svg" alt="" />New</button>
          {menu && <div className="new-menu" role="menu" id="new-menu" aria-label="New"><button ref={menuItem} role="menuitem" onClick={() => openPicker()}>File upload</button></div>}
        </div>
        <nav aria-label="File locations">{(['drive', 'trash'] as const).map(location => <button key={location} className={drive.location === location ? 'selected-nav' : 'plain-nav'} aria-current={drive.location === location ? 'page' : undefined} disabled={drive.actionBusy} onClick={() => { drive.changeLocation(location); heading.current?.focus(); }}>{location === 'drive' ? 'My Drive' : 'Trash'}</button>)}</nav>
        <p className="storage-label">Storage</p><p className="caption storage-value">{formatBytes(session.storage.used_bytes)} of {formatLimit(session.storage.quota_bytes)} used</p><p className="caption storage-limit">Up to {formatLimit(session.limits.max_file_bytes)} per file</p>
      </aside>
      <main className={`drive-content${hasPanel ? ' with-panel' : ''}`}>
        <h1 id="drive-heading" ref={heading} tabIndex={-1}>{drive.location === 'drive' ? 'My Drive' : 'Trash'}</h1>
        {drive.location === 'trash' && <p className="caption">Files stay here until restored and still use storage.</p>}
        <p role="status" aria-live="polite">{drive.actionMessage}</p>
        {drive.actionError && <div role="alert" className="form-error">{drive.actionError} <button className="text-button" onClick={() => void drive.loadFiles()}>Refresh list</button></div>}
        {drive.authError && <p role="alert" className="form-error">{drive.authError}</p>}
        {drive.listState === 'loading' && <div className="empty-state"><h2>Loading your files…</h2><p>Your files will appear here.</p></div>}
        {drive.listState === 'error' && <div className="empty-state"><UploadIcon /><h2>Your files couldn’t load</h2><p>Please try again in a moment.</p><button className="text-button" onClick={() => void drive.loadFiles()}>Try again</button></div>}
        {drive.listState === 'ready' && drive.files.length === 0 && <div className="empty-state">{drive.location === 'drive' && <UploadIcon />}<h2>{drive.location === 'trash' ? 'Trash is empty' : checking ? 'Checking your upload' : inFlight ? 'Your first file is on its way' : 'A place for your files'}</h2><p>{drive.location === 'trash' ? 'Files you move to Trash will appear here.' : checking ? 'Your file may already be saved. We’re checking.' : inFlight ? 'You can follow its progress below.' : 'Use New → File upload to add your first file.'}</p></div>}
        {drive.listState === 'ready' && drive.files.length > 0 && <div className="files-list"><table><caption className="sr-only">Files in {drive.location === 'drive' ? 'My Drive' : 'Trash'}</caption><thead><tr><th scope="col">Name</th><th scope="col" className="owner-column">Owner</th><th scope="col" className="size-column">File size</th><th scope="col" className="actions-column"><span className="sr-only">Actions</span></th></tr></thead><tbody>{drive.files.map((file) => <tr key={file.id}><td><span className="file-name"><Attachment /><span title={file.name}>{file.name}</span></span><span className="mobile-size">{formatBytes(file.size_bytes)}</span></td><td className="owner-column">me</td><td className="size-column">{formatBytes(file.size_bytes)}</td><td className="actions-column"><FileActions file={file} busy={drive.busy} error={drive.actionError} onAction={async (...args) => { const result = await drive.fileAction(...args); if (result && args[1] !== 'download') heading.current?.focus(); return result; }} /></td></tr>)}</tbody></table>{drive.cursor && <button className="text-button" disabled={drive.loadingMore} onClick={() => void drive.loadFiles(drive.cursor!)}>{drive.loadingMore ? 'Loading…' : 'Load more'}</button>}</div>}
      </main>
    </div>
    <input ref={picker} type="file" tabIndex={-1} className="native-picker" aria-label="Choose a file to upload" onChange={(event) => { const file = event.currentTarget.files?.[0]; event.currentTarget.value = ''; newButton.current?.focus(); if (file) void drive.selectFile(file, retrySelection.current); }} />
    <UploadPanel panel={panel} check={() => void drive.checkAgain()} choose={() => openPicker()} retry={() => { if (!drive.retryHeldFile()) openPicker(true); }} dismiss={() => { drive.dismiss(); heading.current?.focus(); }} />
    <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">{liveMessage}</div>
  </div>;
}
