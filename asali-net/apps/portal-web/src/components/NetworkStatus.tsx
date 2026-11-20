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
  if (q.isPending) return <span className="hatch inline-flex min-h-11 shrink-0 items-center whitespace-nowrap rounded-full bg-surface-2 px-4 text-sm text-meta shadow-[inset_0_0_0_1px_var(--border)]">Asking the network…</span>
  if (q.isError || !q.data) return <span className="text-sm text-warn-fg">Network status unavailable</span>
  const down = q.data.orgs.filter((o) => !o.online)
  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen(!open)} aria-expanded={open} className="inline-flex min-h-11 shrink-0 items-center gap-2.5 whitespace-nowrap rounded-full bg-surface-2 px-4 text-sm font-medium shadow-[inset_0_0_0_1px_var(--border)] transition-colors duration-150 hover:bg-sunken">
        <span aria-hidden className={`size-2 rounded-full ${down.length === 0 ? 'bg-ok shadow-[0_0_0_3px_var(--ok-wash)]' : 'bg-warn shadow-[0_0_0_3px_var(--warn-wash)]'}`} />
        <NetworkIcon size={16} strokeWidth={1.75} aria-hidden className="text-muted" />
        {q.data.online} of {q.data.total} online
      </button>
      {open && (
        <div role="dialog" aria-label="Organisations not answering" className="absolute right-0 z-20 mt-2 w-76 rounded-panel bg-surface p-4 text-sm shadow-pop">
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
