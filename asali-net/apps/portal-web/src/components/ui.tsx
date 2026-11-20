import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { ApiError } from '../api/client'

// Small, plain controls. Radii: 6 px for controls, 10 px for panels (DESIGN.md 3.3). One primary button per view.

type ButtonKind = 'primary' | 'secondary' | 'danger' | 'quiet'
const KIND: Record<ButtonKind, string> = {
  primary: 'bg-accent text-on-accent border border-accent',
  secondary: 'bg-surface text-ink border border-line-strong hover:bg-sunken',
  danger: 'bg-surface text-bad-fg border border-bad-line hover:bg-bad-bg',
  quiet: 'bg-transparent text-ink border border-transparent hover:bg-sunken',
}

export function Button({ kind = 'secondary', className = '', ...p }: ButtonHTMLAttributes<HTMLButtonElement> & { kind?: ButtonKind }) {
  return <button type="button" {...p} className={`min-h-11 rounded-control px-4 text-base font-semibold ${KIND[kind]} ${className}`} />
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="grid gap-1">
      <span className="text-base font-semibold">{label}</span>
      {children}
      {hint && <span className="text-[13px] text-meta">{hint}</span>}
    </label>
  )
}

const CONTROL = 'min-h-11 w-full rounded-control border border-line-strong bg-surface px-3 text-base text-ink'
export function Input(p: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...p} className={`${CONTROL} ${p.className ?? ''}`} />
}
export function Select(p: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...p} className={`${CONTROL} ${p.className ?? ''}`} />
}
export function Textarea(p: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...p} className={`${CONTROL} min-h-32 py-2 ${p.className ?? ''}`} />
}

export function PageHeader({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-3 border-b border-line pb-3">
      <h1>{title}</h1>
      {children}
    </div>
  )
}

export function EmptyState({ title, text, action }: { title: string; text: string; action?: ReactNode }) {
  return (
    <div className="prose-narrow py-8">
      <h2>{title}</h2>
      <p className="mt-1 text-muted">{text}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  )
}

export function ProblemMessage({ error }: { error: unknown }) {
  if (!error) return null
  const p = error instanceof ApiError ? error.problem : null
  return (
    <div role="alert" className="prose-narrow rounded-control border border-bad-line bg-bad-bg px-3 py-2 text-bad-fg">
      <strong>{p?.title ?? 'Something went wrong'}</strong>
      <p>{p?.detail || (error instanceof Error ? error.message : 'Try again in a moment.')}</p>
    </div>
  )
}

export function Notice({ tone = 'unknown', children }: { tone?: 'ok' | 'warn' | 'bad' | 'unknown'; children: ReactNode }) {
  const c = { ok: 'border-ok-line bg-ok-bg text-ok-fg', warn: 'border-warn-line bg-warn-bg text-warn-fg', bad: 'border-bad-line bg-bad-bg text-bad-fg', unknown: 'border-unk-line bg-unk-bg text-unk-fg' }[tone]
  return <div className={`prose-narrow rounded-control border px-3 py-2 ${c}`}>{children}</div>
}

export function Skeleton({ rows = 4, label }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-live="polite" className="grid gap-2">
      {label && <p className="text-muted">{label}</p>}
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="h-9 rounded-control bg-sunken" />
      ))}
    </div>
  )
}

export function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="overflow-x-auto" role="region" aria-label="Table, scrolls sideways" tabIndex={0}>
      <table className="w-full border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-line-strong">
            {head.map((h) => (
              <th key={h} scope="col" className="whitespace-nowrap px-3 py-2.5 font-semibold">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  )
}
export const Td = ({ children, mono = false, className = '' }: { children?: ReactNode; mono?: boolean; className?: string }) => (
  <td className={`border-b border-line px-3 py-2.5 align-top ${mono ? 'font-mono' : ''} ${className}`}>{children}</td>
)

export function Status({ tone, children }: { tone: 'ok' | 'warn' | 'bad' | 'unknown'; children: ReactNode }) {
  const c = { ok: 'text-ok-fg bg-ok-bg border-ok-line', warn: 'text-warn-fg bg-warn-bg border-warn-line', bad: 'text-bad-fg bg-bad-bg border-bad-line', unknown: 'text-unk-fg bg-unk-bg border-unk-line' }[tone]
  return <span className={`inline-block shrink-0 self-start whitespace-nowrap rounded-full border px-2.5 py-0.5 text-[13px] font-semibold ${c}`}>{children}</span>
}
