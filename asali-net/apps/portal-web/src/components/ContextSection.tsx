import type { ContextBlock, ContextDocHit } from '../api/types'
import { DocItem } from './Evidence'

const SHOWN = 8

// What the organisations' own records say around this pack, found by following foreign keys in each database (Phase 3).
export function ContextSection({ context, related }: { context: ContextBlock | null; related: ContextDocHit[] }) {
  if (!context) return null
  const asked = context.organisations_asked.length
  const silent = context.organisations.filter((o) => o.status !== 'answered')
  const answered = context.organisations.filter((o) => o.status === 'answered')
  const names = new Map(context.organisations.map((o) => [o.org_id, o.name]))
  return (
    <div className="grid gap-6">
      <section aria-labelledby="ctx">
        <h2 id="ctx">Context found across organisations</h2>
        <p className="mt-1 text-sm text-muted">
          {asked} organisations asked, {context.organisations_contributing.length} found context.
          {silent.map((o) => ` ${o.name} did not answer.`)}
        </p>
        {context.terms.length === 0 ? (
          <p className="mt-2 text-muted">No organisation found context for this pack.</p>
        ) : (
          <ul className="mt-3 grid gap-3">
            {context.terms.slice(0, SHOWN).map((t) => {
              const where = t.provenance[0]
              return (
                <li key={t.key} className="prose-narrow border-t border-line pt-2">
                  <p className="font-semibold">{t.term}</p>
                  <p className="text-sm text-meta">
                    {where ? `${where.table}.${where.column} · ${names.get(where.organisation) ?? where.organisation}` : t.organisations.map((o) => names.get(o) ?? o).join(', ')}
                  </p>
                  <p className="text-sm text-muted">{t.why_relevant.join('. ')}.</p>
                </li>
              )
            })}
          </ul>
        )}
        {answered.length > 0 && (
          <details className="mt-4">
            <summary className="min-h-11 cursor-pointer py-2 underline">How each organisation found it</summary>
            <ul className="mt-2 grid gap-3 text-sm">
              {answered.map((o) => (
                <li key={o.org_id}>
                  <p className="font-semibold">{o.name}{o.engine ? ` (${o.engine})` : ''}</p>
                  <p className="text-muted">{o.explored_tables.length > 0 ? `Explored ${o.explored_tables.join(', ')}.` : 'No record there mentions this pack.'}</p>
                  {o.joins.map((j) => <p key={j} className="font-mono text-muted">{j}</p>)}
                  {o.stop_reason && <p className="text-meta">Stopped: {o.stop_reason}.</p>}
                </li>
              ))}
            </ul>
          </details>
        )}
      </section>
      {related.length > 0 && (
        <section aria-labelledby="ctxdocs">
          <h2 id="ctxdocs">Related documents found through the context</h2>
          <p className="mt-1 text-sm text-muted">The text models did not link these to this pack. They share words with its context. This does not change the result.</p>
          <ul className="mt-2 grid gap-5">
            {related.map((d) => <DocItem key={d.doc_id} d={d} extra={`Shared words: ${d.matched_terms.join(', ')}.`} />)}
          </ul>
        </section>
      )}
    </div>
  )
}
