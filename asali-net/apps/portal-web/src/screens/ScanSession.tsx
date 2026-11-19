
import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router'
import { api } from '../api/client'
import type { Config, Counts, ScanRow } from '../api/types'
import { PartyPicker } from '../components/PartyPicker'
import { ScanBox } from '../components/ScanBox'
import { ScanList } from '../components/ScanList'
import { Button, EmptyState, Field, Input, Notice, PageHeader, ProblemMessage, Select } from '../components/ui'
import { feedback, soundEnabled } from '../lib/feedback'
import { money, plural } from '../lib/format'
import { Receipt, type SaleSummary } from './Receipt'

type Kind = 'dispatch' | 'receive' | 'sell' | 'return'
interface SessionState { id: string; rows: ScanRow[]; counts: Counts; missing: { serial: string }[] }
const TITLE: Record<Kind, string> = { dispatch: 'Dispatch', receive: 'Receive', sell: 'Sell', return: 'Returns' }
const RETURN_REASONS = ['Wrong strength supplied', 'Pack damaged', 'Customer says it did not work', 'Looks different from before', 'Other']

export function ScanSession({ kind, config }: { kind: Kind; config: Config }) {
  const { from, ref } = useParams()
  const nav = useNavigate()
  const [party, setParty] = useState('')
  const [session, setSession] = useState<SessionState | null>(null)
  const [error, setError] = useState<unknown>(null)
  const [done, setDone] = useState<string>('')
  const [notice, setNotice] = useState('')
  const [sale, setSale] = useState<SaleSummary | null>(null)
  const [reason, setReason] = useState(RETURN_REASONS[0] ?? '')
  const [last4, setLast4] = useState('')
  const [prices, setPrices] = useState<Record<string, string>>({})
  const sound = soundEnabled(true)
  const wanted = kind === 'dispatch' ? (config.org_type === 'pharma' ? 'distributor' : 'shop') : ''
  const started = useRef(false)

  const start = useCallback(async () => {
    setError(null)
    try {
      const body = kind === 'dispatch' ? { kind, to_org: party } : kind === 'receive' ? { kind, from_org: from, source_ref: ref } : { kind }
      const r = await api<{ session_id: string; expected_count: number }>('/api/scan/sessions', { method: 'POST', json: body })
      setSession({ id: r.session_id, rows: [], counts: { scanned: 0, needs_attention: 0, expected: r.expected_count }, missing: [] })
    } catch (e) {
      setError(e)
    }
  }, [kind, party, from, ref])

  useEffect(() => {
    if (started.current || kind === 'dispatch') return
    started.current = true
    void start()
  }, [kind, start])


  const onRead = async (raw: string, source: 'wedge' | 'camera' | 'typed') => {
    if (!session) return
    try {
      const r = await api<{ row: ScanRow } & Counts>(`/api/scan/sessions/${session.id}/read`, { method: 'POST', json: { raw, source } })
      feedback(r.row.status === 'ok' ? 'ok' : r.row.status === 'corrected' ? 'corrected' : 'rejected', sound)
      setSession((s) => (s && r.row.status !== 'duplicate' ? { ...s, rows: [r.row, ...s.rows], counts: { scanned: r.scanned, needs_attention: r.needs_attention, expected: r.expected } } : s))
      setNotice(r.row.status === 'duplicate' ? r.row.message : '')
    } catch (e) {
      setError(e)
    }
  }
  const refresh = async () => {
    if (!session) return
    const r = await api<{ rows: ScanRow[]; missing: { serial: string }[] } & Counts>(`/api/scan/sessions/${session.id}`)
    setSession({ id: session.id, rows: r.rows, counts: { scanned: r.scanned, needs_attention: r.needs_attention, expected: r.expected }, missing: r.missing })
  }
  const undo = async (id: number) => {
    if (!session) return
    await api(`/api/scan/sessions/${session.id}/rows/${id}/undo`, { method: 'POST' })
    await refresh()
  }
  const choose = async (id: number, serial: string) => {
    if (!session) return
    try {
      await api(`/api/scan/sessions/${session.id}/rows/${id}/choose`, { method: 'POST', json: { serial } })
      await refresh()
    } catch (e) {
      setError(e)
    }
  }
  const gtins = [...new Set(session?.rows.filter((r) => r.gtin && (r.status === 'ok' || r.status === 'corrected')).map((r) => r.gtin as string))]

  const finish = async () => {
    if (!session) return
    setError(null)
    const body: Record<string, unknown> = {}
    if (kind === 'sell') {
      body.prices = Object.fromEntries(gtins.map((g) => [g, Math.round(Number(prices[g] ?? 0) * 100)]))
      if (last4) body.customer_last4 = last4
    }
    if (kind === 'return') body.reason = reason
    try {
      const r = await api<Record<string, unknown>>(`/api/scan/sessions/${session.id}/finish`, { method: 'POST', json: body })
      if (kind === 'sell') {
        setSale({ bill_no: String(r.bill_no), total_paise: Number(r.total_paise), lines: session.rows.filter((x) => x.status === 'ok' || x.status === 'corrected').map((x) => ({ serial: x.serial ?? '', gtin: x.gtin ?? '', lot: x.lot, price_paise: Math.round(Number(prices[x.gtin ?? ''] ?? 0) * 100) })) })
      }
      const missing = (r.missing as string[] | undefined)?.length ?? 0
      setDone(
        kind === 'dispatch' ? `Recorded dispatch of ${plural(Number(r.units), 'pack', 'packs')}.` : kind === 'receive' ? `Received ${plural(Number(r.received), 'pack', 'packs')}.${missing ? ` ${missing} missing, noted in a discrepancy document.` : ''}` : kind === 'sell' ? `Recorded sale ${String(r.bill_no)}, ${money(Number(r.total_paise))}.` : `Recorded the return of ${plural(Number(r.units), 'pack', 'packs')}.`,
      )
      setSession(null)
    } catch (e) {
      setError(e)
    }
  }
  const discard = async () => {
    if (session && window.confirm('Discard this scan session? The packs scanned so far will not be recorded.')) {
      await api(`/api/scan/sessions/${session.id}`, { method: 'DELETE' })
      setSession(null)
      if (kind === 'receive') nav('/receive')
    }
  }

  if (done) {
    return (
      <div className="grid gap-4">
        <PageHeader title={TITLE[kind]} />
        <Notice tone="ok">{done}</Notice>
        {sale && <Receipt config={config} sale={sale} />}
        <div>
          <Button kind="primary" onClick={() => { setDone(''); setSale(null); setPrices({}); started.current = false; if (kind !== 'dispatch') void start(); else setParty('') }}>
            Start another {TITLE[kind].toLowerCase()}
          </Button>
        </div>
      </div>
    )
  }

  if (kind === 'dispatch' && !session) {
    return (
      <div className="grid max-w-xl gap-4">
        <PageHeader title="Dispatch" />
        <PartyPicker type={wanted} value={party} onChange={setParty} />
        <ProblemMessage error={error} />
        <div>
          <Button kind="primary" disabled={!party} onClick={start}>
            Start dispatch
          </Button>
        </div>
      </div>
    )
  }
  if (!session) return error ? <ProblemMessage error={error} /> : <EmptyState title="Starting…" text="Opening a scan session." />

  const unresolved = session.counts.needs_attention > 0
  const missing = kind === 'receive' ? Math.max(0, session.counts.expected - session.counts.scanned) : 0
  const label = { dispatch: `Record dispatch of ${session.counts.scanned}`, receive: `Record receipt of ${session.counts.scanned}`, sell: `Record sale of ${session.counts.scanned}`, return: `Record return of ${session.counts.scanned}` }[kind]
  return (
    <div className="grid gap-6">
      <PageHeader title={kind === 'dispatch' ? `Dispatch to ${party}` : kind === 'receive' ? `Receive ${ref ?? ''}` : TITLE[kind]} />
      <div className="grid gap-6 md:grid-cols-[1fr_320px]">
        <div className="grid gap-4">
          <ScanBox onRead={onRead} />
          <ProblemMessage error={error} />
          {notice && <p className="text-meta">{notice}</p>}
          <ScanList rows={session.rows} onUndo={undo} onChoose={choose} />
        </div>
        <aside className="grid content-start gap-4">
          <p>
            <span className="text-2xl font-semibold tabular-nums">{session.counts.scanned}</span>
            {kind === 'receive' ? ` of ${session.counts.expected} packs scanned` : ' packs scanned'}
          </p>
          {unresolved && <p className="text-warn-fg">{plural(session.counts.needs_attention, 'row needs', 'rows need')} a look</p>}
          {kind === 'receive' && missing > 0 && (
            <Button onClick={refresh}>
              Show the {missing} missing
            </Button>
          )}
          {session.missing.length > 0 && (
            <ul className="font-mono text-sm">
              {session.missing.map((m) => (
                <li key={m.serial}>{m.serial}</li>
              ))}
            </ul>
          )}
          {kind === 'sell' && gtins.length > 0 && (
            <fieldset className="grid gap-2">
              <legend className="font-semibold">Price per pack (₹)</legend>
              {gtins.map((g) => (
                <Field key={g} label={g}>
                  <Input inputMode="decimal" value={prices[g] ?? ''} onChange={(e) => setPrices({ ...prices, [g]: e.target.value })} />
                </Field>
              ))}
              <Field label="Last 4 digits of phone (optional)" hint="Stored as a one-way code, never the number.">
                <Input inputMode="numeric" maxLength={4} value={last4} onChange={(e) => setLast4(e.target.value)} />
              </Field>
            </fieldset>
          )}
          {kind === 'return' && (
            <Field label="Reason">
              <Select value={reason} onChange={(e) => setReason(e.target.value)}>
                {RETURN_REASONS.map((r) => (
                  <option key={r}>{r}</option>
                ))}
              </Select>
            </Field>
          )}
          <Button kind="primary" disabled={unresolved || session.counts.scanned === 0 || (kind === 'sell' && gtins.some((g) => !Number(prices[g])))} onClick={finish}>
            {label}
          </Button>
          <Button kind="quiet" onClick={discard}>
            Discard session
          </Button>
        </aside>
      </div>
    </div>
  )
}

