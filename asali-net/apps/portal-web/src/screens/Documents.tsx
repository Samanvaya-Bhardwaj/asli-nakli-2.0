import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { api } from '../api/client'
import { Button, EmptyState, Field, Notice, PageHeader, ProblemMessage, Select, Skeleton, Status, Table, Td, Textarea } from '../components/ui'
import { DOC_TYPE_WORD, fmtDate } from '../lib/format'

interface Summary { id: string; doc_type: string; kind: string; title: string; created_at: number; issue_labels: string[]; links: number }
interface Found { doc_id: string; doc_type: string; type_confidence: number; type_note: string; links: { entity_key: string; confidence: number; because: string[]; state: string; implied: boolean }[]; claims: { name: string; value: unknown }[]; issue_labels: string[]; removed: string[] }

export function Documents() {
  const qc = useQueryClient()
  const [text, setText] = useState('')
  const [type, setType] = useState('')
  const [found, setFound] = useState<Found | null>(null)
  const [filter, setFilter] = useState('')
  const list = useQuery({ queryKey: ['documents', filter], queryFn: () => api<{ documents: Summary[] }>(`/api/documents${filter ? `?type=${filter}` : ''}`) })
  const add = useMutation({
    mutationFn: () => api<Found>('/api/documents', { method: 'POST', json: { text, declared_type: type || null } }),
    onSuccess: (r) => { setFound(r); setText(''); void qc.invalidateQueries({ queryKey: ['documents'] }) },
  })
  const reject = useMutation({
    mutationFn: ({ id, key }: { id: string; key: string }) => api(`/api/documents/${id}/links/${key}/reject`, { method: 'POST' }),
    onSuccess: (_r, v) => setFound((f) => f && { ...f, links: f.links.filter((l) => l.entity_key !== v.key) }),
  })
  const upload = async (file: File | undefined) => { if (file) setText(await file.text()) }
  return (
    <div className="grid gap-6">
      <PageHeader title="Documents" />
      <form className="grid max-w-3xl gap-3" onSubmit={(e) => { e.preventDefault(); add.mutate() }}>
        <Field label="Paste the text, or choose a .txt or .md file below"><Textarea value={text} onChange={(e) => setText(e.target.value)} required minLength={10} /></Field>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Document type (optional, the system predicts it)"><Select value={type} onChange={(e) => setType(e.target.value)}><option value="">Let the system decide</option>{Object.entries(DOC_TYPE_WORD).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select></Field>
          <Field label="Or upload a file"><input type="file" accept=".txt,.md,text/plain" onChange={(e) => void upload(e.target.files?.[0])} className="min-h-11" /></Field>
        </div>
        <ProblemMessage error={add.error} />
        <div><Button kind="primary" type="submit" disabled={add.isPending || text.length < 10}>Save document</Button></div>
      </form>
      {found && (
        <section aria-labelledby="found" className="prose-narrow grid gap-2 border-t border-line pt-4">
          <h2 id="found">What we found</h2>
          <p>This looks like <strong>{(DOC_TYPE_WORD[found.doc_type] ?? found.doc_type).toLowerCase()}</strong> ({Math.round(found.type_confidence * 100)}% sure).</p>
          {found.type_note && <Notice tone="warn">{found.type_note}</Notice>}
          {found.removed.length > 0 && <p className="text-muted">Personal details removed before saving: {found.removed.join(', ')}.</p>}
          {found.issue_labels.length > 0 && <p>About: {found.issue_labels.map((l) => l.replace(/_/g, ' ')).join(', ')}.</p>}
          {found.links.filter((l) => !l.implied).length === 0 ? <p className="text-muted">No pack, batch or shipment was linked yet. It is tried again every 10 minutes.</p> : (
            <ul className="grid gap-2">
              {found.links.filter((l) => !l.implied).map((l) => (
                <li key={l.entity_key} className="flex flex-wrap items-center gap-x-3 gap-y-1">
                  <span className="font-mono">{l.entity_key}</span>
                  <Status tone={l.state === 'linked' ? 'ok' : 'warn'}>{l.state === 'linked' ? 'Linked' : 'Possible link'} {Math.round(l.confidence * 100)}%</Status>
                  <span className="text-sm text-muted">Because: {l.because.join(', ')}</span>
                  <Button kind="quiet" onClick={() => reject.mutate({ id: found.doc_id, key: l.entity_key })}>Not this</Button>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
      <section aria-labelledby="all" className="grid gap-3 border-t border-line pt-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h2 id="all">Saved documents</h2>
          <Select aria-label="Filter by type" className="!w-64" value={filter} onChange={(e) => setFilter(e.target.value)}><option value="">All types</option>{Object.entries(DOC_TYPE_WORD).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</Select>
        </div>
        {list.isPending ? <Skeleton /> : list.isError ? <ProblemMessage error={list.error} /> : list.data.documents.length === 0 ? <EmptyState title="No documents" text="Documents you save, and notices the system writes, appear here." /> : (
          <Table head={['Added', 'Title', 'Kind', 'Links']}>
            {list.data.documents.map((d) => <tr key={d.id}><Td>{fmtDate(new Date(d.created_at * 1000).toISOString())}</Td><Td>{d.title}</Td><Td>{d.kind}</Td><Td>{d.links}</Td></tr>)}
          </Table>
        )}
      </section>
    </div>
  )
}
