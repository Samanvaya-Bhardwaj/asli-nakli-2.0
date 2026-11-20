import { Ban, Check, CircleHelp, TriangleAlert } from 'lucide-react'
import { motion } from 'motion/react'
import { useEffect, useRef } from 'react'
import type { VerifyResult } from '../api/types'
import { fmtExpiry } from '../lib/format'

// A verdict-tinted console card: the wash fades from the top-left corner into the surface, the chip carries the
// status colour solid, and the word is set in the poster face. "Cannot check" wears the hatch of the unknown.
const LOOK = {
  genuine: { icon: Check, box: 'tint-ok', word: 'text-ok-fg', chip: 'bg-ok text-on-ok' },
  caution: { icon: TriangleAlert, box: 'tint-warn', word: 'text-warn-fg', chip: 'bg-warn text-on-warn' },
  do_not_use: { icon: Ban, box: 'tint-bad', word: 'text-bad-fg', chip: 'bg-bad text-on-bad' },
  cannot_check: { icon: CircleHelp, box: 'tint-unknown hatch', word: 'text-unk-fg', chip: 'bg-unk text-on-unk' },
} as const

// The answer first: a word, one sentence, what to do, then the product line. Never a score.
export function VerdictBlock({ result }: { result: VerifyResult }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => ref.current?.focus(), [result])
  const look = LOOK[result.verdict]
  const Icon = look.icon
  const p = result.pack.product
  return (
    <motion.div ref={ref} role="status" tabIndex={-1} initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.28, ease: [0.22, 0.61, 0.36, 1] }} className={`rounded-panel px-5 py-6 text-ink outline-none md:px-7 md:py-7 ${look.box}`}>
      <div className="flex items-center gap-4">
        <span className={`grid size-12 shrink-0 place-items-center rounded-full md:size-14 ${look.chip}`}>
          <Icon size={26} strokeWidth={2} aria-hidden />
        </span>
        <span className={`font-display text-[clamp(2.4rem,7vw,3.5rem)] uppercase leading-[0.95] tracking-[0.005em] ${look.word}`}>{result.word}</span>
      </div>
      <p className="mt-4 max-w-[60ch] text-lg leading-snug">{result.headline.replace(/^(Genuine|Do not use this pack|We could not check this pack|Be careful with this pack)\.\s*/, '') || result.headline}</p>
      {result.action && <p className="mt-2 max-w-[60ch] font-semibold">{result.action}</p>}
      {(p || result.pack.lot) && (
        <p className="mt-5 border-t border-dashed border-line-strong pt-4 text-[15px] text-muted">
          {p && `${p.brand} ${p.strength}`}
          {result.pack.lot && ` · Batch ${result.pack.lot}`}
          {result.pack.expiry && ` · Expires ${fmtExpiry(result.pack.expiry)}`}
        </p>
      )}
    </motion.div>
  )
}

export function VerdictLoading({ asked, total }: { asked: number; total: number }) {
  return (
    <div role="status" aria-live="polite" className="card hatch px-5 py-6 md:px-7">
      <p className="text-lg font-semibold">{total > 0 ? `Asked ${asked} of ${total} organisations…` : 'Reading the code…'}</p>
      {total > 0 && (
        <div aria-hidden className="mt-4 h-2 overflow-hidden rounded-full bg-sunken">
          <div className="h-full rounded-full bg-accent transition-[width] duration-500 ease-console" style={{ width: `${Math.round((asked / total) * 100)}%` }} />
        </div>
      )}
      <div className="mt-4 grid gap-2">
        <div className="h-5 w-2/3 animate-pulse rounded-full bg-sunken motion-reduce:animate-none" />
        <div className="h-5 w-1/2 animate-pulse rounded-full bg-sunken motion-reduce:animate-none" />
      </div>
    </div>
  )
}
