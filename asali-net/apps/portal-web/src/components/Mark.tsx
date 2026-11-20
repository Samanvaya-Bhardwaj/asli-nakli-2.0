import type { ReactNode } from 'react'

// The Asali mark from the project's dashboard: one pack, two readings. The solid half is the record that
// checks out, the hatched half is the copy that cannot be accounted for. Decorative wherever a name sits beside it.
export function Mark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden focusable="false" className="shrink-0">
      <rect width="32" height="32" rx="9" fill="var(--accent)" />
      <path d="M16 7.5a8.5 8.5 0 0 0 0 17z" fill="var(--on-accent)" />
      <circle cx="16" cy="16" r="8.5" fill="none" stroke="var(--on-accent)" strokeWidth="1.8" />
      <g stroke="var(--on-accent)" strokeWidth="1.5" strokeLinecap="round">
        <path d="M17.8 10.4 L21.6 14.2" />
        <path d="M17.8 14.2 L22.4 18.8" />
        <path d="M17.8 18 L20.6 20.8" />
      </g>
    </svg>
  )
}

// "Asali" in the dashboard's poster face. The text that follows keeps its own words; only the look changes.
// compact: on a phone the wordmark steps aside and the mark alone identifies the site, as on the dashboard.
export function Brand({ children, compact = false }: { children?: ReactNode; compact?: boolean }) {
  return (
    <span className="inline-flex min-w-0 items-center gap-2.5">
      <Mark />
      <span className={`font-display text-[1.25rem] uppercase leading-none tracking-[0.01em] ${compact ? 'hidden sm:inline' : ''}`}>Asali</span>
      {children && (
        <span className="min-w-0 truncate text-[15px] font-semibold text-muted">
          <span className={`text-ghost ${compact ? 'hidden sm:inline' : ''}`}> · </span>
          {children}
        </span>
      )}
    </span>
  )
}
