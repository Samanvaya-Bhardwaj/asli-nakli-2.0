import { useMutation } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { api } from '../api/client'
import type { CheckReply, Config, VerifyResult } from '../api/types'
import { Code } from '../components/Code'
import { EvidenceList, PackHistory, ReasonList, SourcesLine } from '../components/Evidence'
import { ScanBox } from '../components/ScanBox'
import { VerdictBlock, VerdictLoading } from '../components/VerdictBlock'
import { Button, EmptyState, Field, Input, Notice, PageHeader, ProblemMessage, Textarea } from '../components/ui'
import { fmtDate } from '../lib/format'
import { recall, remember } from '../lib/history'

function Result({ result }: { result: VerifyResult }) {
  return (
    <div className="grid gap-8">
      <VerdictBlock result={result} />
      <ReasonList reasons={result.reasons} />
      <PackHistory history={result.history} simulation={result.mode === 'simulation'} />
      <EvidenceList documents={result.documents} />
      <SourcesLine sources={result.sources} />
      <p><Link className="underline" to={`/report?code=${result.pack.serial}`}>Report a problem with this pack</Link></p>
    </div>
  )
}

export function Check({ config }: { config: Config }) {
  const nav = useNavigate()
  const [raw, setRaw] = useState(() => new URLSearchParams(window.location.search).get('code') ?? '')
  const [progress, setProgress] = useState({ asked: 0, total: 0 })
  const [reply, setReply] = useState<CheckReply | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [busy, setBusy] = useState(false)
  const es = useRef<EventSource | null>(null)
  useEffect(() => () => es.current?.close(), [])

  const finish = (r: CheckReply) => {
    setReply(r)
    setBusy(false)
    if (r.status === 'done') nav(`/result/${remember(r.result)}`, { replace: false })
  }
  const run = (code: string) => {
    setBusy(true)
    setReply(null)
    setError(null)
    setProgress({ asked: 0, total: 0 })
    es.current?.close()
    const url = `/api/verify/stream?raw=${encodeURIComponent(code)}&city=${encodeURIComponent(config.city)}`
    const stream = new EventSource(url)
    es.current = stream
    stream.addEventListener('progress', (e) => setProgress(JSON.parse((e as MessageEvent<string>).data) as { asked: number; total: number }))
    stream.addEventListener('result', (e) => {
      stream.close()
      finish(JSON.parse((e as MessageEvent<string>).data) as CheckReply)
    })
    stream.onerror = () => {
      stream.close()
      void api<CheckReply>('/api/check', { method: 'POST', json: { raw: code, city: config.city } }).then(finish).catch((err) => { setError(err); setBusy(false) })
    }
  }
  const confirm = useMutation({
    mutationFn: (v: { check_id: string; serial: string }) => api<CheckReply>('/api/check/confirm', { method: 'POST', json: v }),
    onSuccess: finish,
    onError: (e) => { setError(e); setBusy(false) },
  })
  return (
    <div className="grid gap-6">
      <div>
        <h1>Check a medicine</h1>
        <p className="mt-1 max-w-[60ch] text-muted">Type the 11-character code printed after SN, or scan the QR code.</p>
      </div>
      <form className="grid gap-3" onSubmit={(e) => { e.preventDefault(); run(raw) }}>
        <Field label="Code on the pack"><Input value={raw} onChange={(e) => setRaw(e.target.value)} className="font-mono text-lg" autoComplete="off" spellCheck={false} placeholder="For example TPM9-S346-Q37" /></Field>
        <div className="flex flex-wrap items-center gap-3">
          <Button kind="primary" type="submit" disabled={busy || raw.trim().length < 3}>Check medicine</Button>
        </div>
      </form>
      <ScanBox onRead={(code) => { setRaw(code); run(code) }} disabled={busy} />
      <ProblemMessage error={error} />
      {busy && !reply && <VerdictLoading asked={progress.asked} total={progress.total} />}
      {reply?.status === 'needs_confirmation' && (
        <div role="status" className="prose-narrow grid gap-3 rounded-r-control border-l-4 border-warn bg-warn-bg px-4 py-4 text-warn-fg">
          <p className="text-lg font-semibold">Does your pack show <Code value={reply.serial} />?</p>
          <p>We read a slightly different code and found one close match. Check it against the pack before we go on.</p>
          <div className="flex gap-3">
            <Button kind="primary" onClick={() => { setBusy(true); confirm.mutate({ check_id: reply.check_id, serial: reply.serial }) }}>Yes, check it</Button>
            <Button onClick={() => { setReply(null); setRaw('') }}>No, scan again</Button>
          </div>
        </div>
      )}
      {(reply?.status === 'unreadable' || reply?.status === 'needs_choice') && <Notice tone="warn">{reply.message}{reply.status === 'needs_choice' && <span> Options: {reply.choices.join(', ')}.</span>}</Notice>}
    </div>
  )
}

export function ResultPage() {
  const { id } = useParams()
  const item = recall().find((r) => r.id === id)
  if (!item) return <EmptyState title="This result is no longer saved" text="Results are kept in this browser only. Check the code again." action={<Link className="underline" to="/">Check a medicine</Link>} />
  return <div className="grid gap-4"><PageHeader title="Result" /><Result result={item.result} /></div>
}

export function History() {
  const items = recall()
  return (
    <div className="grid gap-4">
      <PageHeader title="My checks" />
      <p className="max-w-[60ch] text-muted">These are kept in this browser only. Nobody else can see them.</p>
      {items.length === 0 ? <EmptyState title="No checks yet" text="Medicines you check on this device appear here." action={<Link className="underline" to="/">Check a medicine</Link>} /> : (
        <ul className="divide-y divide-line border-y border-line">
          {items.map((i) => <li key={i.id} className="py-3"><Link to={`/result/${i.id}`} className="grid gap-0.5"><span className="font-semibold">{i.word}</span><span>{i.text}</span><span className="text-sm text-meta">{fmtDate(i.at, true)}</span></Link></li>)}
        </ul>
      )}
    </div>
  )
}

export function Report({ config }: { config: Config }) {
  const params = new URLSearchParams(window.location.search)
  const [f, setF] = useState({ text: '', city: config.city, purchase_date: '', shop_name: '', serial: params.get('code') ?? '' })
  const send = useMutation({ mutationFn: () => api<{ removed: string[] }>('/api/report', { method: 'POST', json: { text: f.text, city: f.city, shop_name: f.shop_name || null, purchase_date: f.purchase_date || null, serial: f.serial || null } }) })
  if (send.isSuccess) return <div className="grid gap-4"><PageHeader title="Report a problem" /><Notice tone="ok">Thank you. Your report was saved.{send.data.removed.length > 0 ? ` We removed your ${send.data.removed.join(' and ')} before saving it.` : ''}</Notice><Link className="underline" to="/">Check another medicine</Link></div>
  return (
    <div className="grid max-w-xl gap-4">
      <PageHeader title="Report a problem" />
      <form className="grid gap-4" onSubmit={(e) => { e.preventDefault(); send.mutate() }}>
        <Field label="What is wrong with the pack or the medicine?" hint="Phone numbers and e-mail addresses are removed before saving."><Textarea value={f.text} onChange={(e) => setF({ ...f, text: e.target.value })} required minLength={10} /></Field>
        <Field label="City"><Input value={f.city} onChange={(e) => setF({ ...f, city: e.target.value })} required /></Field>
        <Field label="Code on the pack (optional)"><Input className="font-mono" value={f.serial} onChange={(e) => setF({ ...f, serial: e.target.value })} /></Field>
        <Field label="Date you bought it (optional)"><Input type="date" value={f.purchase_date} onChange={(e) => setF({ ...f, purchase_date: e.target.value })} /></Field>
        <Field label="Shop name (optional)"><Input value={f.shop_name} onChange={(e) => setF({ ...f, shop_name: e.target.value })} /></Field>
        <ProblemMessage error={send.error} />
        <div><Button kind="primary" type="submit" disabled={send.isPending}>Send report</Button></div>
      </form>
    </div>
  )
}
