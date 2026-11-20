import type { DocHit, HistoryHop, Reason, Source } from '../api/types'
import { DOC_TYPE_WORD, EVENT_WORD, fmtDate } from '../lib/format'
import { Status, Table, Td } from './ui'

const STRENGTH: Record<Reason['strength'], { tone: 'bad' | 'warn' | 'unknown'; word: string }> = {
  do_not_use: { tone: 'bad', word: 'Do not use' },
  caution: { tone: 'warn', word: 'Caution' },
  cannot_check: { tone: 'unknown', word: 'Cannot check' },
}

export function ReasonList({ reasons }: { reasons: Reason[] }) {
  if (reasons.length === 0) return null
  return (
    <section aria-labelledby="why">
      <h2 id="why">Why</h2>
      <ul className="mt-2 grid gap-3">
        {reasons.map((r) => (
          <li key={r.code} className="prose-narrow flex gap-3">
            <Status tone={STRENGTH[r.strength].tone}>{STRENGTH[r.strength].word}</Status>
            <span>{r.text}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

export function PackHistory({ history, simulation }: { history: HistoryHop[]; simulation: boolean }) {
  return (
    <section aria-labelledby="where">
      <h2 id="where">Where this pack has been</h2>
      <div className="mt-2">
        <Table head={['Date', 'What happened', 'Organisation', simulation ? 'Computer (simulation)' : 'Computer']}>
          {history.flatMap((h) =>
            h.unavailable ? (
              <tr key={h.org_id}>
                <Td />
                <Td className="text-unk-fg">Did not answer</Td>
                <Td>{h.org_name}, {h.city}</Td>
                <Td mono>{h.served_by?.host_name ?? 'not reached'}</Td>
              </tr>
            ) : (
              h.events.map((e) => (
                <tr key={e.event_id}>
                  <Td><span className="whitespace-nowrap">{fmtDate(e.at)}</span></Td>
                  <Td>{EVENT_WORD[e.event_type] ?? e.event_type}</Td>
                  <Td>{h.org_name}, {h.city}</Td>
                  <Td mono>{h.served_by?.host_name}</Td>
                </tr>
              ))
            ),
          )}
        </Table>
      </div>
    </section>
  )
}

const SHOWN_FIRST = 3

function DocItem({ d }: { d: DocHit }) {
  return (
    <li className="prose-narrow border-t border-line pt-3">
      <p className="font-semibold">
        {DOC_TYPE_WORD[d.doc_type] ?? d.doc_type} · {d.org_name} · {fmtDate(d.created_at)}
      </p>
      <p className="text-sm text-meta">{d.label}</p>
      <blockquote className="mt-1 border-l-2 border-line-strong pl-3">{d.snippet.text}</blockquote>
      {d.linked_to[0] && (
        <p className="mt-1 text-sm text-muted">
          Linked because: {d.linked_to[0].because.join(', ') || 'weak match'}. Confidence {(d.linked_to[0].confidence * 100).toFixed(0)}%.
        </p>
      )}
      {d.claims
        .filter((c) => c.check === 'contradicts' && c.against)
        .map((c) => (
          <p key={c.name} className="mt-1 text-warn-fg">
            Says {String(c.value)}. Records: {c.against}.
          </p>
        ))}
    </li>
  )
}

// The server puts documents that raised a finding first, so the first few are the ones that matter; the rest are one click away.
export function EvidenceList({ documents }: { documents: DocHit[] }) {
  const first = documents.slice(0, SHOWN_FIRST)
  const rest = documents.slice(SHOWN_FIRST)
  return (
    <section aria-labelledby="docs">
      <h2 id="docs">Documents about this pack ({documents.length})</h2>
      {documents.length === 0 ? (
        <p className="mt-2 text-muted">No documents are linked to this pack or its batch.</p>
      ) : (
        <>
          <ul className="mt-2 grid gap-5">{first.map((d) => <DocItem key={d.doc_id} d={d} />)}</ul>
          {rest.length > 0 && (
            <details className="mt-5">
              <summary className="min-h-11 cursor-pointer py-2 underline">Show {rest.length} more {rest.length === 1 ? 'document' : 'documents'}</summary>
              <ul className="mt-2 grid gap-5">{rest.map((d) => <DocItem key={d.doc_id} d={d} />)}</ul>
            </details>
          )}
        </>
      )}
    </section>
  )
}

export function SourcesLine({ sources }: { sources: Source[] }) {
  const ok = sources.filter((s) => s.status === 'answered').length
  const gone = sources.filter((s) => s.status !== 'answered').map((s) => s.org_id)
  return (
    <p className="text-sm text-meta">
      Checked with {ok} of {sources.length} organisations{gone.length > 0 ? `. Did not answer: ${gone.join(', ')}.` : '.'}
    </p>
  )
}
