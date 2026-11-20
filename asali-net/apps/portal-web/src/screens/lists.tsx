import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router'
import { api } from '../api/client'
import type { Network } from '../api/types'
import { EmptyState, Notice, PageHeader, ProblemMessage, Skeleton, Status, Table, Td } from '../components/ui'
import { fmtDate, fmtExpiry } from '../lib/format'

interface Incoming { from_org: string; shipment_id: string; at: string; count: number }

export function IncomingList() {
  const q = useQuery({ queryKey: ['incoming'], queryFn: () => api<{ incoming: Incoming[]; sources: { org_id: string; status: string }[] }>('/api/incoming') })
  if (q.isPending) return <Skeleton label="Asking the organisations that send to you…" />
  if (q.isError) return <ProblemMessage error={q.error} />
  const silent = q.data.sources.filter((s) => s.status !== 'answered')
  return (
    <div className="grid gap-4">
      <PageHeader title="Receive" />
      {silent.length > 0 && <Notice tone="warn">Did not answer: {silent.map((s) => s.org_id).join(', ')}. Shipments from them may be missing from this list.</Notice>}
      {q.data.incoming.length === 0 ? (
        <EmptyState title="No incoming shipments" text="Shipments sent to you by a pharma company or distributor appear here." />
      ) : (
        <Table head={['Sent', 'From', 'Shipment', 'Packs', '']}>
          {q.data.incoming.map((i) => (
            <tr key={`${i.from_org}/${i.shipment_id}`}>
              <Td>{fmtDate(i.at)}</Td>
              <Td>{i.from_org}</Td>
              <Td mono>{i.shipment_id}</Td>
              <Td>{i.count}</Td>
              <Td>
                <Link className="font-semibold underline" to={`/receive/${i.from_org}/${i.shipment_id}`}>
                  Receive these packs
                </Link>
              </Td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  )
}

export function StockList() {
  const [now] = useState(() => Date.now())
  const q = useQuery({ queryKey: ['stock'], queryFn: () => api<{ total: number; groups: { gtin: string; lot: string | null; expiry: string | null; count: number }[] }>('/api/stock') })
  if (q.isPending) return <Skeleton label="Counting stock…" />
  if (q.isError) return <ProblemMessage error={q.error} />
  const soon = now + 90 * 86400_000
  return (
    <div className="grid gap-4">
      <PageHeader title="Stock" />
      {q.data.groups.length === 0 ? (
        <EmptyState title="No stock" text="Packs you receive appear here until you dispatch or sell them." />
      ) : (
        <>
          <p>{q.data.total} packs in stock</p>
          <Table head={['Product', 'Batch', 'Expires', 'Packs']}>
            {q.data.groups.map((g) => {
              const near = g.expiry ? new Date(g.expiry).getTime() < soon : false
              return (
                <tr key={`${g.gtin}-${g.lot}`}>
                  <Td mono>{g.gtin}</Td>
                  <Td mono={g.lot != null} className={g.lot == null ? 'text-meta' : ''}>{g.lot ?? 'not recorded'}</Td>
                  <Td>{g.expiry ? fmtExpiry(g.expiry) : ''} {near && <Status tone="warn">Under 90 days</Status>}</Td>
                  <Td>{g.count}</Td>
                </tr>
              )
            })}
          </Table>
        </>
      )}
    </div>
  )
}

export function Activity() {
  const q = useQuery({ queryKey: ['activity'], queryFn: () => api<{ activity: { at: string; actor: string; action: string; detail: string }[] }>('/api/activity') })
  if (q.isPending) return <Skeleton />
  if (q.isError) return <ProblemMessage error={q.error} />
  return (
    <div className="grid gap-4">
      <PageHeader title="Activity" />
      {q.data.activity.length === 0 ? (
        <EmptyState title="No activity yet" text="Actions taken in this portal are listed here, newest first." />
      ) : (
        <Table head={['When', 'Who', 'What', 'Detail']}>
          {q.data.activity.map((a, i) => (
            <tr key={i}>
              <Td>{fmtDate(a.at, true)}</Td>
              <Td>{a.actor}</Td>
              <Td>{a.action}</Td>
              <Td>{a.detail}</Td>
            </tr>
          ))}
        </Table>
      )}
    </div>
  )
}

export function NetworkPage() {
  const q = useQuery({ queryKey: ['network'], queryFn: () => api<Network>('/api/network'), refetchInterval: 15000 })
  if (q.isPending) return <Skeleton label="Asking every organisation…" rows={8} />
  if (q.isError) return <ProblemMessage error={q.error} />
  return (
    <div className="grid gap-4">
      <PageHeader title="Network" />
      <p>{q.data.online} of {q.data.total} organisations answered{q.data.mode === 'simulation' ? ', all on this computer (simulation)' : ''}.</p>
      <Table head={['Organisation', 'Type', 'City', 'Computer', 'Status', 'Latency', 'Database', 'Text vault']}>
        {q.data.orgs.map((o) => (
          <tr key={o.org_id}>
            <Td>{o.name}{o.org_id === q.data.self && <span className="text-meta"> (this portal)</span>}</Td>
            <Td>{o.org_type}</Td>
            <Td>{o.city}</Td>
            <Td mono>{o.host_name}</Td>
            <Td>{o.online ? <Status tone="ok">Online</Status> : <Status tone="bad">Not answering</Status>}</Td>
            <Td>{o.latency_ms === null ? '' : `${o.latency_ms} ms`}</Td>
            <Td>{o.engine ?? ''}</Td>
            <Td>{o.vault ?? ''}</Td>
          </tr>
        ))}
      </Table>
    </div>
  )
}

