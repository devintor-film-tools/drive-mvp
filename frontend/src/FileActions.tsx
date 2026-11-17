import { useEffect, useRef, useState } from 'react';
import type { DriveFile } from './api';

type Action = 'download' | 'rename' | 'trash' | 'restore';
export function FileActions({ file, busy, error, onAction }: {
  file: DriveFile; busy: boolean; error: string;
  onAction: (file: DriveFile, action: Action, name?: string) => Promise<boolean>;
}) {
  const [open, setOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [name, setName] = useState(file.name);
  const control = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const input = useRef<HTMLInputElement>(null);
  const [submitted, setSubmitted] = useState(false);
  const actions: [Action, string][] = file.trashed_at ? [['restore', 'Restore']] : [['download', 'Download'], ['rename', 'Rename…'], ['trash', 'Move to trash']];
  useEffect(() => {
    if (!open) return;
    menu.current?.querySelector('button')?.focus();
    const close = (event: PointerEvent) => { if (!control.current?.contains(event.target as Node)) setOpen(false); };
    document.addEventListener('pointerdown', close);
    return () => document.removeEventListener('pointerdown', close);
  }, [open]);
  useEffect(() => {
    if (renaming) { dialog.current?.showModal(); input.current?.focus(); input.current?.select(); }
  }, [renaming]);
  function closeDialog() { dialog.current?.close(); setRenaming(false); trigger.current?.focus(); }
  async function choose(action: Action) {
    setOpen(false);
    trigger.current?.focus();
    if (action === 'rename') { setName(file.name); setSubmitted(false); setRenaming(true); }
    else await onAction(file, action);
  }
  return <div className="file-actions" ref={control}>
    <button ref={trigger} className="text-button" disabled={busy} aria-label={`Actions for ${file.name}`} aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen(!open)} onKeyDown={event => {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); setOpen(true); }
    }}>Actions</button>
    {open && <div className="file-menu" role="menu" aria-label={`Actions for ${file.name}`} ref={menu} onKeyDown={event => {
      const items = Array.from(menu.current?.querySelectorAll('button') ?? []);
      const index = items.indexOf(document.activeElement as HTMLButtonElement);
      if (event.key === 'Escape') { event.preventDefault(); setOpen(false); trigger.current?.focus(); }
      if (event.key === 'Tab') setOpen(false);
      if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
        event.preventDefault();
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? items.length - 1 : (index + (event.key === 'ArrowDown' ? 1 : -1) + items.length) % items.length;
        items[next]?.focus();
      }
    }}>{actions.map(([action, label]) => <button key={action} role="menuitem" tabIndex={-1} onClick={() => void choose(action)}>{label}</button>)}</div>}
    {renaming && <dialog ref={dialog} className="rename-dialog" aria-labelledby={`rename-${file.id}`} onCancel={event => { event.preventDefault(); if (!busy) closeDialog(); }}>
      <form onSubmit={async event => { event.preventDefault(); setSubmitted(true); if (await onAction(file, 'rename', name)) closeDialog(); }}>
        <h2 id={`rename-${file.id}`}>Rename file</h2>
        <label htmlFor={`name-${file.id}`}>File name</label>
        <input ref={input} id={`name-${file.id}`} value={name} required disabled={busy} onChange={event => setName(event.target.value)} aria-describedby={`rename-help-${file.id}`} />
        <p id={`rename-help-${file.id}`} className="caption">Changing the name keeps the contents unchanged.</p>
        {submitted && error && <p className="form-error" role="alert">{error}</p>}
        <div className="dialog-buttons"><button type="button" className="text-button" disabled={busy} onClick={closeDialog}>Cancel</button><button className="primary-button" disabled={busy || !name.trim()}>{busy ? 'Saving…' : 'Save'}</button></div>
      </form>
    </dialog>}
  </div>;
}
