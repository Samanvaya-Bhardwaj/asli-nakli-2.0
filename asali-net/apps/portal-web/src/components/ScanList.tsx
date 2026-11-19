import { Check, TriangleAlert, X } from 'lucide-react'
import { motion } from 'motion/react'
import type { ScanRow } from '../api/types'
import { fmtExpiry, groupSerial } from '../lib/format'
import { Code } from './Code'
import { Button, EmptyState } from './ui'

const TONE: Record<string, string> = { ok: 'text-ok', corrected: 'text-warn', duplicate: 'text-meta', not_expected: 'text-bad', unreadable: 'text-bad', needs_choice: 'text-warn' }

function Mark({ status }: { status: string }) {
  const p = { size: 20, strokeWidth: 1.75, 'aria-hidden': true }
  const word = { ok: 'Read', corrected: 'Corrected', not_expected: 'Rejected', unreadable: 'Rejected', needs_choice: 'Choose', duplicate: 'Duplicate' }[status] ?? status
  return (
    <span className={`inline-flex items-center gap-1 font-semibold ${TONE[status] ?? ''}`}>
      {status === 'ok' ? <Check {...p} /> : status === 'corrected' || status === 'needs_choice' ? <TriangleAlert {...p} /> : <X {...p} />}
      <span className="sr-only">{word}</span>
    </span>
  )
}

export function ScanList({ rows, product, onUndo, onChoose }: { rows: ScanRow[]; product?: (gtin: string) => string; onUndo: (id: number) => void; onChoose: (id: number, serial: string) => void }) {
  if (rows.length === 0) return <EmptyState title="Nothing scanned yet" text="Scanned packs appear here." />
  return (
    <ul aria-live="polite" className="divide-y divide-line border-y border-line">
      {rows.map((r) => (
        <motion.li key={r.row_id} initial={{ opacity: 0, y: -4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.14, ease: 'easeOut' }} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-1 py-3">
          <Mark status={r.status} />
          <div className="min-w-0 flex-1">
            {r.status === 'ok' && r.serial && (
              <div className="flex flex-wrap items-center gap-x-3">
                <Code value={r.serial} />
                <span className="text-muted">
                  {[r.gtin && product?.(r.gtin), r.lot, r.expiry && `exp ${fmtExpiry(r.expiry)}`].filter(Boolean).join(' · ')}
                </span>
              </div>
            )}
            {r.status === 'corrected' && r.serial && (
              <p>
                Read as <span className="font-mono">{r.corrected_from ? shortRaw(r.corrected_from) : ''}</span>, corrected to <Code value={r.serial} />
              </p>
            )}
            {(r.status === 'not_expected' || r.status === 'unreadable') && (
              <p>
                {r.serial && <Code value={r.serial} />} <span className="text-bad-fg">{r.message}</span>
              </p>
            )}
            {r.status === 'needs_choice' && (
              <div>
                <p className="mb-1">{r.message}</p>
                <div className="flex flex-wrap gap-2">
                  {r.choices.map((c) => (
                    <Button key={c} onClick={() => onChoose(r.row_id, c)}>
                      <span className="font-mono">{groupSerial(c)}</span>
                    </Button>
                  ))}
                </div>
              </div>
            )}
          </div>
          {r.status !== 'duplicate' && (
            <Button kind="quiet" onClick={() => onUndo(r.row_id)} aria-label={`${r.status === 'ok' || r.status === 'corrected' ? 'Undo' : 'Remove'} ${r.raw}`}>
              {r.status === 'ok' || r.status === 'corrected' ? 'Undo' : 'Remove'}
            </Button>
          )}
        </motion.li>
      ))}
    </ul>
  )
}

function shortRaw(raw: string): string {
  const m = /\(21\)([^()\s]+)/.exec(raw)
  return m?.[1] ? groupSerial(m[1]) : raw.slice(-14)
}
