import type { Similar } from '../api/generated'
import { fmtDate } from '../lib/format'
import { Code } from './Code'
import { Status, Table, Td } from './ui'

function Fit({ fits }: { fits: boolean | null }) {
  if (fits === null) return <span className="text-meta">No lot on the label</span>
  return fits ? <Status tone="ok">Lot fits the label</Status> : <Status tone="warn">Lot does not fit the label</Status>
}

// Phase 2: every issued code that approximately matches a reading, and every reading recorded for an issued code.
export function NearMatches({ data }: { data: Similar }) {
  return (
    <div className="grid gap-6">
      <section aria-labelledby="near">
        <h2 id="near">Issued codes close to this reading</h2>
        <p className="mt-1 text-sm text-muted">Nothing here changes a record. Cost is how unlikely the slip is: look-alike characters cost little.</p>
        {data.matches.length === 0 ? (
          <p className="mt-2 text-muted">No issued code is close to this reading.</p>
        ) : (
          <div className="mt-3">
            <Table head={['Code', 'Cost', 'What changed', 'Product', 'Lot', 'Label']}>
              {data.matches.map((m) => (
                <tr key={m.serial}>
                  <Td mono><Code value={m.serial} diffAgainst={data.read.serial ?? undefined} /></Td>
                  <Td>{m.cost.toFixed(2)}</Td>
                  <Td>{m.edits.length > 0 ? m.edits.map((e) => <span key={e} className="block font-mono">{e}</span>) : 'Exact'}</Td>
                  <Td>{m.product ?? ''}</Td>
                  <Td mono>{m.lot ?? ''}</Td>
                  <Td><Fit fits={m.fits_label} /></Td>
                </tr>
              ))}
            </Table>
          </div>
        )}
      </section>
      {data.seen_as.length > 0 && (
        <section aria-labelledby="seen">
          <h2 id="seen">Readings recorded for this code</h2>
          <p className="mt-1 text-sm text-muted">Other ways this code was typed or scanned in the consumer portals.</p>
          <div className="mt-3">
            <Table head={['Reading', 'Cost', 'What changed', 'City', 'When']}>
              {data.seen_as.map((s, i) => (
                <tr key={`${s.raw_input}-${i}`}>
                  <Td mono>{s.serial_read}</Td>
                  <Td>{s.cost.toFixed(2)}</Td>
                  <Td>{s.edits.map((e) => <span key={e} className="block font-mono">{e}</span>)}</Td>
                  <Td>{s.city}</Td>
                  <Td>{fmtDate(s.at, true)}</Td>
                </tr>
              ))}
            </Table>
          </div>
        </section>
      )}
    </div>
  )
}
