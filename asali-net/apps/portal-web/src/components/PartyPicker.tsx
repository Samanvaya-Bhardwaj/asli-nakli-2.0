import { useQuery } from '@tanstack/react-query'
import { api } from '../api/client'
import type { Network, Party } from '../api/types'
import { EmptyState, ProblemMessage, Skeleton } from './ui'

// Who to send to: organisations of one type, those that serve this region first, offline ones disabled.
export function PartyPicker({ type, value, onChange }: { type: string; value: string; onChange: (org: string) => void }) {
  const parties = useQuery({ queryKey: ['parties', type], queryFn: () => api<{ parties: Party[] }>(`/api/parties?type=${type}`) })
  const net = useQuery({ queryKey: ['network'], queryFn: () => api<Network>('/api/network'), refetchInterval: 15000 })
  if (parties.isPending) return <Skeleton rows={3} label="Loading organisations…" />
  if (parties.isError) return <ProblemMessage error={parties.error} />
  const online = new Map(net.data?.orgs.map((o) => [o.org_id, o.online]))
  if (parties.data.parties.length === 0) return <EmptyState title="No organisations found" text="Organisations that join the network appear here." />
  return (
    <fieldset className="grid gap-1">
      <legend className="mb-1 text-base font-semibold">Send to</legend>
      {parties.data.parties.map((p) => {
        const up = online.get(p.org_id) ?? true
        return (
          <label key={p.org_id} className={`flex min-h-11 items-center gap-3 rounded-control border px-3 ${value === p.org_id ? 'border-accent bg-sunken' : 'border-line'} ${up ? '' : 'opacity-60'}`}>
            <input type="radio" name="party" checked={value === p.org_id} disabled={!up} onChange={() => onChange(p.org_id)} />
            <span>
              {p.name}, {p.city}
              {p.serves_here && <span className="text-meta"> · serves your region</span>}
              {!up && <span className="text-unk-fg"> · not answering</span>}
            </span>
          </label>
        )
      })}
    </fieldset>
  )
}
