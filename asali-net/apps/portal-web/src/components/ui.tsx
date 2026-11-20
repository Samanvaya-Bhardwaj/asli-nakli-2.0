import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { ApiError } from '../api/client'

// Console controls from the project's dashboard: pill buttons, inset fields, rimmed cards. One primary (lime) button per view.

type ButtonKind = 'primary' | 'secondary' | 'danger' | 'quiet'
const KIND: Record<ButtonKind, string> = {
  // Disabled lime at half opacity reads as mud; a disabled primary goes neutral and stays clearly a button.
  primary: 'bg-accent text-on-accent hover:bg-accent-hover disabled:bg-sunken disabled:text-meta disabled:opacity-100 disabled:shadow-none disabled:hover:bg-sunken',
  secondary: 'bg-transparent text-ink shadow-[inset_0_0_0_1px_var(--border-strong)] hover:bg-surface-2',
  danger: 'bg-bad-bg text-bad-fg shadow-[inset_0_0_0_1px_var(--bad-line)] hover:brightness-110',
  quiet: 'bg-transparent text-ink hover:bg-sunken',
}

export function Button({ kind = 'secondary', className = '', ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { kind?: ButtonKind }) {
  return (
    <button
      type="button"
      {...p}
      className={`inline-flex min-h-11 items-center justify-center gap-2 rounded-full px-5 text-[15px] font-semibold tracking-[-0.01em] whitespace-nowrap transition-[background-color,color,filter,translate] duration-150 ease-console active:translate-y-px disabled:active:translate-y-0 ${KIND[kind]} ${className}`}
    />
  )
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="grid gap-1.5">
      <span className="text-[15px] font-semibold">{label}</span>
      {children}
      {hint && <span className="text-[13px] text-meta">{hint}</span>}
    </label>
  )
}

const CONTROL =
  'min-h-11 w-full rounded-control border-0 bg-inset px-4 text-base text-ink shadow-[inset_0_0_0_1px_var(--border)] outline-none transition-shadow duration-150 placeholder:text-meta hover:shadow-[inset_0_0_0_1px_var(--border-strong)] focus:shadow-[inset_0_0_0_1px_var(--accent-ink)] disabled:opacity-60'
export function Input(p: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...p} className={`${CONTROL} ${p.className ?? ''}`} />
}
export function Select(p: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...p} className={`${CONTROL} ${p.className ?? ''}`} />
}
export function Textarea(p: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...p} className={`${CONTROL} min-h-32 py-3 ${p.className ?? ''}`} />
}

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
      <h1>{title}</h1>
      {children}
    </div>
  )
}

export function EmptyState({ title, text, action }: { title: string; text: string; action?: ReactNode }) {
  return (
    <div className="hatch prose-narrow rounded-panel px-6 py-8 shadow-[inset_0_0_0_1px_var(--border)]">
      <h2>{title}</h2>
      <p className="mt-1.5 text-muted">{text}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}

export function ProblemMessage({ error }: { error: unknown }) {
  if (!error) return null
  const p = error instanceof ApiError ? error.problem : null
  return (
    <div role="alert" className="prose-narrow rounded-control bg-bad-bg px-4 py-3 text-bad-fg shadow-[inset_0_0_0_1px_var(--bad-line)]">
      <strong>{p?.title ?? 'Something went wrong'}</strong>
      <p>{p?.detail || (error instanceof Error ? error.message : 'Try again in a moment.')}</p>
    </div>
  )
}

export function Notice({ tone = 'unknown', children }: { tone?: 'ok' | 'warn' | 'bad' | 'unknown'; children: ReactNode }) {
  const c = {
    ok: 'bg-ok-bg text-ok-fg shadow-[inset_0_0_0_1px_var(--ok-line)]',
    warn: 'bg-warn-bg text-warn-fg shadow-[inset_0_0_0_1px_var(--warn-line)]',
    bad: 'bg-bad-bg text-bad-fg shadow-[inset_0_0_0_1px_var(--bad-line)]',
    unknown: 'bg-unk-bg text-unk-fg shadow-[inset_0_0_0_1px_var(--unknown-line)]',
  }[tone]
  return <div className={`prose-narrow rounded-control px-4 py-3 ${c}`}>{children}</div>
}

export function Skeleton({ rows = 4, label }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-live="polite" className="grid gap-2">
      {label && <p className="text-muted">{label}</p>}
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="hatch h-10 animate-pulse rounded-control bg-surface-2 motion-reduce:animate-none" />
      ))}
    </div>
  )
}

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="card overflow-x-auto" role="region" aria-label="Table, scrolls sideways" tabIndex={0}>
      <table className="w-full border-collapse text-left text-[15px]">
        <thead>
          <tr>
            {head.map((h) => (
              <th key={h} scope="col" className="whitespace-nowrap bg-surface-2 px-4 py-3 text-[13px] font-medium text-meta first:rounded-tl-panel last:rounded-tr-panel">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="[&_tr:hover_td]:bg-surface-2">{children}</tbody>
      </table>
    </div>
  )
}
export const Td = ({ children, mono = false, className = '' }: { children?: ReactNode; mono?: boolean; className?: string }) => (
  <td className={`border-t border-line px-4 py-3 align-top transition-colors duration-150 ${mono ? 'font-mono text-[14px]' : ''} ${className}`}>{children}</td>
)

export function Status({ tone, children }: { tone: 'ok' | 'warn' | 'bad' | 'unknown'; children: ReactNode }) {
  const c = { ok: 'text-ok-fg bg-ok-bg', warn: 'text-warn-fg bg-warn-bg', bad: 'text-bad-fg bg-bad-bg', unknown: 'text-unk-fg bg-unk-bg' }[tone]
  return <span className={`inline-block shrink-0 self-start whitespace-nowrap rounded-full px-3 py-0.5 text-[13px] font-semibold ${c}`}>{children}</span>
}
