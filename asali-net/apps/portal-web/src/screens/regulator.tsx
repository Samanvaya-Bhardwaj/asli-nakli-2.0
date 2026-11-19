import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import type { CheckReply } from '../api/types'
import { EvidenceList, PackHistory, ReasonList, SourcesLine } from '../components/Evidence'
import { VerdictBlock, VerdictLoading } from '../components/VerdictBlock'
import { Button, EmptyState, Field, Input, Notice, PageHeader, ProblemMessage, Select, Skeleton, Status, Table, Td } from '../components/ui'
import { fmtDate } from '../lib/format'

interface Alert { alert_id: string; kind: string; gtin: string; lot: string | null; manufacturer_org: string; issued_at: string; reason: string; states: string[] | null }

export function AlertsRegulator() {
  const qc = useQueryClient()
  const list = useQuery({ queryKey: ['alerts-reg'], queryFn: () => api<{ alerts: Alert[] }>('/api/alerts') })
  const [f, setF] = useState({ kind: 'nsq', gtin: '', lot: '', manufacturer_org: '', reason: '', states: '' })
  const issue = useMutation({
    mutationFn: () => api('/api/alerts', { method: 'POST', json: { ...f, lot: f.lot || null, states: f.states ? f.states.split(',').map((s) => s.trim().toUpperCase()) : null } }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['alerts-reg'] }),
  })
  return (
    <div className="grid gap-6">
      <PageHeader title="Alerts" />
      {list.isPending ? <Skeleton /> : list.isError ? <ProblemMessage error={list.error} /> : list.data.alerts.length === 0 ? <EmptyState title="No alerts issued" text="Alerts you issue appear here and in every shop in the states they cover." /> : (
        <Table head={['Issued', 'Kind', 'Product number', 'Batch', 'Maker', 'Reason', 'Where']}>
          {list.data.alerts.map((a) => <tr key={a.alert_id}><Td>{fmtDate(a.issued_at)}</Td><Td>{a.kind}</Td><Td mono>{a.gtin}</Td><Td mono>{a.lot ?? 'all batches'}</Td><Td>{a.manufacturer_org}</Td><Td>{a.reason}</Td><Td>{a.states?.join(', ') ?? 'National'}</Td></tr>)}
        </Table>
      )}
      <form className="grid max-w-xl gap-3 border-t border-line pt-4" onSubmit={(e) => { e.preventDefault(); issue.mutate() }}>
        <h2>Issue an alert</h2>
        <Field label="Kind"><Select value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}><option value="nsq">Not of standard quality</option><option value="recall">Recall</option><option value="ban">Ban</option></Select></Field>
        <Field label="Product number"><Input value={f.gtin} onChange={(e) => setF({ ...f, gtin: e.target.value })} required /></Field>
        <Field label="Batch" hint="Leave empty to cover every batch of the product"><Input value={f.lot} onChange={(e) => setF({ ...f, lot: e.target.value })} /></Field>
        <Field label="Maker (organisation id)"><Input value={f.manufacturer_org} onChange={(e) => setF({ ...f, manufacturer_org: e.target.value })} required /></Field>
        <Field label="Reason"><Input value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} required minLength={3} /></Field>
        <Field label="States" hint="Comma separated, like DL, MH. Leave empty for a national alert."><Input value={f.states} onChange={(e) => setF({ ...f, states: e.target.value })} /></Field>
        <ProblemMessage error={issue.error} />
        {issue.isSuccess && <Notice tone="ok">Alert issued. The notice text was written to your documents.</Notice>}
        <div><Button kind="primary" type="submit" disabled={issue.isPending}>Issue alert</Button></div>
      </form>
    </div>
  )
}

export function AlertsShop() {
  const q = useQuery({ queryKey: ['alerts-shop'], queryFn: () => api<{ alerts: Alert[]; sources: { org_id: string; status: string }[] }>('/api/alerts') })
  if (q.isPending) return <Skeleton label="Asking the regulator…" />
  if (q.isError) return <ProblemMessage error={q.error} />
  return (
    <div className="grid gap-4">
      <PageHeader title="Alerts" />
      {q.data.sources.some((s) => s.status !== 'answered') && <Notice tone="warn">The regulator did not answer. Alerts may be missing.</Notice>}
      {q.data.alerts.length === 0 ? <EmptyState title="No alerts for your state" text="Recalls and quality alerts for your state and national ones appear here, newest first." /> : (
        <Table head={['Issued', 'Kind', 'Product number', 'Batch', 'Reason']}>
          {q.data.alerts.map((a) => <tr key={a.alert_id}><Td>{fmtDate(a.issued_at)}</Td><Td><Status tone="bad">{a.kind}</Status></Td><Td mono>{a.gtin}</Td><Td mono>{a.lot ?? 'all batches'}</Td><Td>{a.reason}</Td></tr>)}
        </Table>
      )}
    </div>
  )
}

interface Licence { org_id: string; licence_no: string; licence_type: string; valid_from: string; valid_to: string; status: string }
export function Licences() {
  const qc = useQueryClient()
  const list = useQuery({ queryKey: ['licences'], queryFn: () => api<{ licences: Licence[] }>('/api/licences') })
  const [f, setF] = useState({ org_id: '', licence_no: '', licence_type: 'retail', valid_from: '', valid_to: '', status: 'active' })
  const save = useMutation({ mutationFn: () => api('/api/licences', { method: 'POST', json: f }), onSuccess: () => void qc.invalidateQueries({ queryKey: ['licences'] }) })
  return (
    <div className="grid gap-6">
      <PageHeader title="Licences" />
      {list.isPending ? <Skeleton /> : list.isError ? <ProblemMessage error={list.error} /> : list.data.licences.length === 0 ? <EmptyState title="No licences recorded" text="Record the licence of each distributor and shop. Packs handled under a suspended or expired licence are flagged." /> : (
        <Table head={['Organisation', 'Licence', 'Type', 'Valid until', 'Status']}>
          {list.data.licences.map((l) => <tr key={l.org_id}><Td>{l.org_id}</Td><Td mono>{l.licence_no}</Td><Td>{l.licence_type}</Td><Td>{fmtDate(l.valid_to)}</Td><Td>{l.status === 'active' ? <Status tone="ok">Active</Status> : <Status tone="bad">{l.status}</Status>}</Td></tr>)}
        </Table>
      )}
      <form className="grid max-w-xl gap-3 border-t border-line pt-4" onSubmit={(e) => { e.preventDefault(); save.mutate() }}>
        <h2>Record a licence</h2>
        <Field label="Organisation id"><Input value={f.org_id} onChange={(e) => setF({ ...f, org_id: e.target.value })} required /></Field>
        <Field label="Licence number"><Input value={f.licence_no} onChange={(e) => setF({ ...f, licence_no: e.target.value })} required /></Field>
        <Field label="Type"><Select value={f.licence_type} onChange={(e) => setF({ ...f, licence_type: e.target.value })}><option>retail</option><option>wholesale</option></Select></Field>
        <div className="grid grid-cols-2 gap-3"><Field label="Valid from"><Input type="date" value={f.valid_from} onChange={(e) => setF({ ...f, valid_from: e.target.value })} required /></Field><Field label="Valid until"><Input type="date" value={f.valid_to} onChange={(e) => setF({ ...f, valid_to: e.target.value })} required /></Field></div>
        <Field label="Status"><Select value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option>active</option><option>suspended</option><option>cancelled</option></Select></Field>
        <ProblemMessage error={save.error} />
        <div><Button kind="primary" type="submit" disabled={save.isPending}>Save licence</Button></div>
      </form>
    </div>
  )
}

export function Investigate() {
  const [raw, setRaw] = useState('')
  const check = useMutation({ mutationFn: () => api<CheckReply>('/api/investigate', { method: 'POST', json: { raw } }) })
  const r = check.data
  return (
    <div className="grid gap-6">
      <PageHeader title="Investigate" />
      <form className="grid max-w-xl gap-3" onSubmit={(e) => { e.preventDefault(); check.mutate() }}>
        <Field label="Code of the pack" hint="Type the code printed after SN, or paste a scanned code."><Input value={raw} onChange={(e) => setRaw(e.target.value)} required className="font-mono" /></Field>
        <div><Button kind="primary" type="submit" disabled={check.isPending || raw.length < 3}>Trace pack</Button></div>
      </form>
      <ProblemMessage error={check.error} />
      {check.isPending && <VerdictLoading asked={0} total={0} />}
      {r?.status === 'done' && <div className="grid gap-6"><VerdictBlock result={r.result} /><ReasonList reasons={r.result.reasons} /><PackHistory history={r.result.history} simulation={r.result.mode === 'simulation'} /><EvidenceList documents={r.result.documents} /><SourcesLine sources={r.result.sources} /></div>}
      {r && r.status !== 'done' && <Notice tone="warn">{r.message}</Notice>}
    </div>
  )
}

interface Group { batch: string; product: string; count: number; cities: string[]; labels: string[]; unusual: boolean; status: string }
export function Complaints() {
  const q = useQuery({ queryKey: ['complaints'], queryFn: () => api<{ groups: Group[]; unusual: number; total: number }>('/api/complaints') })
  if (q.isPending) return <Skeleton label="Reading complaints from the consumer portals…" />
  if (q.isError) return <ProblemMessage error={q.error} />
  return (
    <div className="grid gap-4">
      <PageHeader title="Complaints" />
      <p>{q.data.unusual} {q.data.unusual === 1 ? 'batch has' : 'batches have'} unusually many complaints. {q.data.total} complaints are linked to a batch.</p>
      {q.data.groups.length === 0 ? <EmptyState title="No complaints linked to a batch" text="Customer complaints that could be linked to a batch are grouped here." /> : (
        <Table head={['Batch', 'Product', 'Complaints', 'Cities', 'Most common issues', 'Unusual', 'Batch status']}>
          {q.data.groups.map((g) => <tr key={g.batch}><Td mono>{g.batch}</Td><Td>{g.product}</Td><Td>{g.count}</Td><Td>{g.cities.join(', ')}</Td><Td>{g.labels.join(', ')}</Td><Td>{g.unusual ? <Status tone="warn">Unusual</Status> : ''}</Td><Td>{g.status}</Td></tr>)}
        </Table>
      )}
    </div>
  )
}
