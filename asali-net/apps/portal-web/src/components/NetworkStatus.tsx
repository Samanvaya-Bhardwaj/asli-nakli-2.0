import { useQuery } from '@tanstack/react-query'
import { Network as NetworkIcon } from 'lucide-react'
import { useState } from 'react'
import { api } from '../api/client'
import type { Network } from '../api/types'
import { fmtDate } from '../lib/format'

// "11 of 12 online", polled every 15 s; the popover names who is unreachable (DESIGN.md 5.1).
export function NetworkStatus() {
  const [open, setOpen] = useState(false)
  const q = useQuery({ queryKey: ['network'], queryFn: () => api<Network>('/api/network'), refetchInterval: 15000 })
  if (q.isPending) return <span className="text-sm text-meta">Asking the network…</span>
  if (q.isError || !q.data) return <span className="text-sm text-warn-fg">Network status unavailable</span>
  const down = q.data.orgs.filter((o) => !o.online)
  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="inline-flex min-h-11 items-center gap-2 rounded-control px-3 text-sm hover:bg-sunken">
        <NetworkIcon size={16} strokeWidth={1.75} aria-hidden />
        {q.data.online} of {q.data.total} online
      </button>
      {open && (
        <div role="dialog" aria-label="Organisations not answering" className="absolute right-0 z-10 mt-1 w-72 rounded-panel border border-line-strong bg-surface p-3 text-sm" style={{ boxShadow: 'var(--shadow-float)' }}>
          {down.length === 0 ? (
            <p>Every organisation answered.</p>
          ) : (
            <>
              <p className="font-semibold">Not answering</p>
              <ul className="mt-1 grid gap-1">
                {down.map((o) => (
                  <li key={o.org_id}>
                    {o.name}, {o.city}
                    {o.last_seen && <span className="text-meta"> · last seen {fmtDate(o.last_seen, true)}</span>}
                  </li>
                ))}
              </ul>
            </>
          )}
          <a href="/network" className="mt-2 inline-block underline">
            See every organisation
          </a>
        </div>
      )}
    </div>
  )
}
