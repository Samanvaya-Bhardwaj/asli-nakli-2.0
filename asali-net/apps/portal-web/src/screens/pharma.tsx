import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import QRCode from 'qrcode'
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router'
import { api } from '../api/client'
import { Button, EmptyState, Field, Input, Notice, PageHeader, ProblemMessage, Select, Skeleton, Status, Table, Td } from '../components/ui'
import { fmtExpiry } from '../lib/format'

interface Product { gtin: string; brand: string; generic: string; strength: string; form: string; pack_size: number }
interface Batch { gtin: string; lot: string; mfg_date: string; expiry_date: string; status: string }

export function Products() {
  const qc = useQueryClient()
  const list = useQuery({ queryKey: ['products'], queryFn: () => api<{ products: Product[] }>('/api/products') })
  const [f, setF] = useState({ brand: '', generic: '', strength: '', form: 'tablet', pack_size: '10', storage_min_c: '', storage_max_c: '' })
  const add = useMutation({
    mutationFn: () => api('/api/products', { method: 'POST', json: { ...f, pack_size: Number(f.pack_size), storage_min_c: f.storage_min_c === '' ? null : Number(f.storage_min_c), storage_max_c: f.storage_max_c === '' ? null : Number(f.storage_max_c) } }),
    onSuccess: () => { setF({ ...f, brand: '', generic: '', strength: '' }); void qc.invalidateQueries({ queryKey: ['products'] }) },
  })
  return (
    <div className="grid gap-6">
      <PageHeader title="Products" />
      {list.isPending ? <Skeleton /> : list.isError ? <ProblemMessage error={list.error} /> : list.data.products.length === 0 ? <EmptyState title="No products yet" text="Add a product below. Its product number is made from your company prefix." /> : (
        <Table head={['Product number', 'Brand', 'Generic name', 'Strength', 'Form', 'Pack size']}>
          {list.data.products.map((p) => (
            <tr key={p.gtin}><Td mono>{p.gtin}</Td><Td>{p.brand}</Td><Td>{p.generic}</Td><Td>{p.strength}</Td><Td>{p.form}</Td><Td>{p.pack_size}</Td></tr>
          ))}
        </Table>
      )}
      <form className="grid max-w-xl gap-3 border-t border-line pt-4" onSubmit={(e) => { e.preventDefault(); add.mutate() }}>
        <h2>Add a product</h2>
        <Field label="Brand name"><Input value={f.brand} onChange={(e) => setF({ ...f, brand: e.target.value })} required /></Field>
        <Field label="Generic name"><Input value={f.generic} onChange={(e) => setF({ ...f, generic: e.target.value })} required /></Field>
        <Field label="Strength" hint="For example 500 mg or 100 IU/ml"><Input value={f.strength} onChange={(e) => setF({ ...f, strength: e.target.value })} required /></Field>
        <Field label="Form"><Select value={f.form} onChange={(e) => setF({ ...f, form: e.target.value })}>{['tablet', 'capsule', 'injection', 'syrup', 'other'].map((x) => <option key={x}>{x}</option>)}</Select></Field>
        <Field label="Packs of"><Input inputMode="numeric" value={f.pack_size} onChange={(e) => setF({ ...f, pack_size: e.target.value })} required /></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Lowest storage temperature (°C)"><Input inputMode="decimal" value={f.storage_min_c} onChange={(e) => setF({ ...f, storage_min_c: e.target.value })} /></Field>
          <Field label="Highest storage temperature (°C)"><Input inputMode="decimal" value={f.storage_max_c} onChange={(e) => setF({ ...f, storage_max_c: e.target.value })} /></Field>
        </div>
        <ProblemMessage error={add.error} />
        <div><Button kind="primary" type="submit" disabled={add.isPending}>Add product</Button></div>
      </form>
    </div>
  )
}

export function Batches() {
  const qc = useQueryClient()
  const products = useQuery({ queryKey: ['products'], queryFn: () => api<{ products: Product[] }>('/api/products') })
  const batches = useQuery({ queryKey: ['batches'], queryFn: () => api<{ batches: Batch[] }>('/api/batches') })
  const [f, setF] = useState({ gtin: '', mfg_date: '', expiry_date: '', quantity: '40' })
  const [packs, setPacks] = useState<Record<string, string>>({})
  const create = useMutation({ mutationFn: () => api<Batch>('/api/batches', { method: 'POST', json: { ...f, quantity: Number(f.quantity) } }), onSuccess: () => void qc.invalidateQueries({ queryKey: ['batches'] }) })
  const make = useMutation({ mutationFn: (lot: string) => api(`/api/batches/${lot}/packs`, { method: 'POST', json: { count: Number(packs[lot] ?? 0) } }), onSuccess: () => void qc.invalidateQueries({ queryKey: ['stock'] }) })
  const name = (g: string) => products.data?.products.find((p) => p.gtin === g)
  return (
    <div className="grid gap-6">
      <PageHeader title="Batches" />
      {batches.isPending ? <Skeleton /> : batches.isError ? <ProblemMessage error={batches.error} /> : batches.data.batches.length === 0 ? <EmptyState title="No batches yet" text="Create a batch below, then make its packs." /> : (
        <Table head={['Batch', 'Product', 'Made', 'Expires', 'Status', 'Make packs', '']}>
          {batches.data.batches.map((b) => (
            <tr key={b.lot}>
              <Td mono>{b.lot}</Td>
              <Td>{name(b.gtin)?.brand ?? b.gtin} {name(b.gtin)?.strength}</Td>
              <Td>{b.mfg_date}</Td><Td>{fmtExpiry(b.expiry_date)}</Td>
              <Td>{b.status === 'recalled' ? <Status tone="bad">Recalled</Status> : <Status tone="ok">Released</Status>}</Td>
              <Td><div className="flex gap-2"><Input aria-label={`Packs to make in ${b.lot}`} className="!w-24" inputMode="numeric" value={packs[b.lot] ?? ''} onChange={(e) => setPacks({ ...packs, [b.lot]: e.target.value })} /><Button disabled={!packs[b.lot] || b.status === 'recalled'} onClick={() => make.mutate(b.lot)}>Make packs</Button></div></Td>
              <Td><Link className="underline" to={`/labels/${b.lot}`}>Print labels</Link></Td>
            </tr>
          ))}
        </Table>
      )}
      <ProblemMessage error={make.error} />
      {make.isSuccess && <Notice tone="ok">Packs made. They are in your stock, ready to print labels and dispatch.</Notice>}
      <form className="grid max-w-xl gap-3 border-t border-line pt-4" onSubmit={(e) => { e.preventDefault(); create.mutate() }}>
        <h2>Create a batch</h2>
        <Field label="Product"><Select value={f.gtin} onChange={(e) => setF({ ...f, gtin: e.target.value })} required><option value="">Choose a product</option>{products.data?.products.map((p) => <option key={p.gtin} value={p.gtin}>{p.brand} {p.strength}</option>)}</Select></Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Manufacturing date"><Input type="date" value={f.mfg_date} onChange={(e) => setF({ ...f, mfg_date: e.target.value })} required /></Field>
          <Field label="Expiry date"><Input type="date" value={f.expiry_date} onChange={(e) => setF({ ...f, expiry_date: e.target.value })} required /></Field>
        </div>
        <Field label="Planned quantity" hint="The batch number is made in your company's style."><Input inputMode="numeric" value={f.quantity} onChange={(e) => setF({ ...f, quantity: e.target.value })} required /></Field>
        <ProblemMessage error={create.error} />
        <div><Button kind="primary" type="submit" disabled={create.isPending}>Create batch</Button></div>
      </form>
    </div>
  )
}

interface Label { serial: string; line: string; digital_link: string }
export function Labels() {
  const { '*': lot = '' } = useParams()
  const q = useQuery({ queryKey: ['labels', lot], queryFn: () => api<{ labels: Label[] }>(`/api/batches/${lot}/labels`) })
  const [svgs, setSvgs] = useState<Record<string, string>>({})
  useEffect(() => {
    if (!q.data) return
    void Promise.all(q.data.labels.map(async (l) => [l.serial, await QRCode.toString(l.digital_link, { type: 'svg', margin: 0, width: 72 })] as const)).then((e) => setSvgs(Object.fromEntries(e)))
  }, [q.data])
  if (q.isPending) return <Skeleton label="Preparing labels…" />
  if (q.isError) return <ProblemMessage error={q.error} />
  return (
    <div className="grid gap-4">
      <div className="no-print"><PageHeader title={`Labels for batch ${lot}`}><Button kind="primary" onClick={() => window.print()}>Print labels</Button></PageHeader>
        {q.data.labels.length === 0 && <EmptyState title="No packs to label" text="Packs that have not been dispatched appear here. Make packs for this batch first." />}</div>
      <div className="print-area grid grid-cols-3 gap-x-4 gap-y-3">
        {q.data.labels.slice(0, 24).map((l) => (
          <div key={l.serial} className="flex items-center gap-2 border border-line p-2" style={{ breakInside: 'avoid' }}>
            <div aria-hidden dangerouslySetInnerHTML={{ __html: svgs[l.serial] ?? '' }} />
            <p className="font-mono text-[11px] leading-tight print:text-[9pt]">{l.line}</p>
          </div>
        ))}
      </div>
    </div>
  )
}

export function Recalls() {
  const qc = useQueryClient()
  const batches = useQuery({ queryKey: ['batches'], queryFn: () => api<{ batches: Batch[] }>('/api/batches') })
  const [f, setF] = useState({ key: '', reason: '', level: 'class II' })
  const recall = useMutation({ mutationFn: () => { const b = batches.data?.batches.find((x) => x.lot === f.key); return api('/api/recalls', { method: 'POST', json: { gtin: b?.gtin, lot: f.key, reason: f.reason, level: f.level } }) }, onSuccess: () => void qc.invalidateQueries({ queryKey: ['batches'] }) })
  const recalled = batches.data?.batches.filter((b) => b.status === 'recalled') ?? []
  return (
    <div className="grid gap-6">
      <PageHeader title="Recalls" />
      {recalled.length > 0 && <Table head={['Batch', 'Status']}>{recalled.map((b) => <tr key={b.lot}><Td mono>{b.lot}</Td><Td><Status tone="bad">Recalled</Status></Td></tr>)}</Table>}
      <form className="grid max-w-xl gap-3" onSubmit={(e) => { e.preventDefault(); if (window.confirm(`Recall batch ${f.key}? Every organisation that holds packs from it will see this.`)) recall.mutate() }}>
        <h2>Recall a batch</h2>
        <Field label="Batch"><Select value={f.key} onChange={(e) => setF({ ...f, key: e.target.value })} required><option value="">Choose a batch</option>{batches.data?.batches.filter((b) => b.status !== 'recalled').map((b) => <option key={b.lot}>{b.lot}</option>)}</Select></Field>
        <Field label="Reason"><Input value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} required minLength={3} /></Field>
        <Field label="Level"><Select value={f.level} onChange={(e) => setF({ ...f, level: e.target.value })}>{['class I', 'class II', 'class III'].map((x) => <option key={x}>{x}</option>)}</Select></Field>
        <ProblemMessage error={recall.error} />
        {recall.isSuccess && <Notice tone="ok">Batch recalled. A recall notice was written to your documents.</Notice>}
        <div><Button kind="danger" type="submit" disabled={recall.isPending}>Recall batch</Button></div>
      </form>
    </div>
  )
}
