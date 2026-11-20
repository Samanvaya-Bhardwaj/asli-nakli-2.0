import { Ban, Check, CircleHelp, TriangleAlert } from 'lucide-react'
import { motion } from 'motion/react'
import { useEffect, useRef } from 'react'
import type { VerifyResult } from '../api/types'
import { fmtExpiry } from '../lib/format'

const LOOK = {
  genuine: { icon: Check, box: 'border-ok-line bg-ok-bg text-ok-fg' },
  caution: { icon: TriangleAlert, box: 'border-warn-line bg-warn-bg text-warn-fg' },
  do_not_use: { icon: Ban, box: 'border-bad-line bg-bad-bg text-bad-fg' },
  cannot_check: { icon: CircleHelp, box: 'border-unk-line bg-unk-bg text-unk-fg' },
} as const

// The answer first: a word, one sentence, what to do, then the product line. Never a score.
export function VerdictBlock({ result }: { result: VerifyResult }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => ref.current?.focus(), [result])
  const look = LOOK[result.verdict]
  const Icon = look.icon
  const p = result.pack.product
  return (
    <motion.div ref={ref} role="status" tabIndex={-1} initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.16 }} className={`rounded-panel border px-4 py-4 ${look.box}`}>
      <div className="flex items-center gap-2 text-[28px] font-bold leading-tight md:text-4xl">
        <Icon size={28} strokeWidth={1.75} aria-hidden />
        <span>{result.word}</span>
      </div>
      <p className="mt-2 max-w-[60ch] text-lg">{result.headline.replace(/^(Genuine|Do not use this pack|We could not check this pack|Be careful with this pack)\.\s*/, '') || result.headline}</p>
      {result.action && <p className="mt-2 max-w-[60ch] font-semibold">{result.action}</p>}
      {(p || result.pack.lot) && (
        <p className="mt-3 text-base">
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
    <div role="status" aria-live="polite" className="rounded-panel border border-unk-line bg-unk-bg px-4 py-4 text-unk-fg">
      <p className="text-lg font-semibold">{total > 0 ? `Asked ${asked} of ${total} organisations…` : 'Reading the code…'}</p>
      <div className="mt-3 grid gap-2">
        <div className="h-5 w-2/3 rounded-control bg-sunken" />
        <div className="h-5 w-1/2 rounded-control bg-sunken" />
      </div>
    </div>
  )
}
