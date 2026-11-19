import { Check, Copy } from 'lucide-react'
import { useState } from 'react'
import { groupSerial } from '../lib/format'

// Every code in the interface goes through this: mono, grouped 4-4-3, separators quieter, a copy button.
export function Code({ value, kind = 'serial', diffAgainst }: { value: string; kind?: 'serial' | 'gtin' | 'lot'; diffAgainst?: string }) {
  const [copied, setCopied] = useState(false)
  const shown = kind === 'serial' ? groupSerial(value) : value
  const other = diffAgainst && kind === 'serial' ? groupSerial(diffAgainst) : null
  const parts = shown.split('-')
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard blocked: the code is still on screen */
    }
  }
  let i = 0
  return (
    <span className="group inline-flex items-center gap-1 font-mono font-medium tracking-[0.02em]">
      <span translate="no">
        {parts.map((part, pi) => (
          <span key={pi}>
            {pi > 0 && <span className="text-meta">-</span>}
            {[...part].map((ch) => {
              const differs = other !== null && other.replace(/-/g, '')[i++] !== ch
              return differs ? (
                <u key={i} className="decoration-2 underline-offset-2">
                  {ch}
                </u>
              ) : (
                ch
              )
            })}
          </span>
        ))}
      </span>
      <button type="button" onClick={copy} aria-label={`Copy code ${value}`} className="rounded-control p-1 text-meta opacity-0 hover:bg-sunken focus:opacity-100 group-hover:opacity-100">
        {copied ? <Check size={16} strokeWidth={1.75} /> : <Copy size={16} strokeWidth={1.75} />}
      </button>
    </span>
  )
}
