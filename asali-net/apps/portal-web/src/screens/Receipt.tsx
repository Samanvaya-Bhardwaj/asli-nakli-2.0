import { useQuery } from '@tanstack/react-query'
import QRCode from 'qrcode'
import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { Config } from '../api/types'
import { Button } from '../components/ui'
import en from '../i18n/receipt.en.json'
import hi from '../i18n/receipt.hi.json'
import kn from '../i18n/receipt.kn.json'
import mr from '../i18n/receipt.mr.json'
import { fmtDate, money } from '../lib/format'

export interface SaleSummary {
  bill_no: string
  total_paise: number
  lines: { serial: string; gtin: string; lot: string | null; price_paise: number }[]
}

const WORDS = { en, hi, mr, kn }

// Printed in the shop's receipt language; the QR leads to the consumer portal of the shop's city.
// The Hindi, Marathi and Kannada strings are marked "needs review" until a speaker confirms them.
export function Receipt({ config, sale }: { config: Config; sale: SaleSummary }) {
  const lang = config.shop?.receipt_language ?? 'en'
  const w = WORDS[lang]
  const consumers = useQuery({ queryKey: ['parties', 'consumer'], queryFn: () => api<{ parties: { city: string; base_url: string }[] }>('/api/parties?type=consumer') })
  const base = consumers.data?.parties.find((p) => p.city === config.city)?.base_url ?? ''
  const [qr, setQr] = useState('')
  useEffect(() => {
    if (base) void QRCode.toString(base, { type: 'svg', margin: 0, width: 96 }).then(setQr)
  }, [base])
  return (
    <section className="grid gap-3">
      <div className="print-area prose-narrow border border-line-strong p-4" lang={lang === 'en' ? 'en-IN' : lang}>
        <h2>{config.name}</h2>
        <p>{config.shop?.area}, {config.city}</p>
        <p className="text-sm">{w.licence}: {config.shop?.drug_licence_no} · {w.gstin}: {config.shop?.gstin}</p>
        <p className="mt-2">{w.receipt} · {w.bill} {sale.bill_no} · {fmtDate(new Date().toISOString(), true)}</p>
        <ul className="my-2 divide-y divide-line">
          {sale.lines.map((l) => (
            <li key={l.serial} className="flex justify-between py-1 font-mono text-sm">
              <span>{l.serial.slice(0, 4)}-{l.serial.slice(4, 8)}-{l.serial.slice(8)}</span>
              <span>{money(l.price_paise)}</span>
            </li>
          ))}
        </ul>
        <p className="font-semibold">{w.total}: {money(sale.total_paise)} ({sale.lines.length} {w.packs})</p>
        <div className="mt-3 flex items-center gap-3">
          {qr && <div role="img" aria-label="QR code that opens the consumer portal" dangerouslySetInnerHTML={{ __html: qr }} />}
          <p className="text-sm">{w.check}</p>
        </div>
        <p className="mt-2 text-sm">{w.helpline}: {config.shop?.helpline}</p>
        <p className="text-sm">{w.thanks}</p>
      </div>
      <div className="no-print">
        <Button onClick={() => window.print()}>Print receipt</Button>
        {w._status !== 'reviewed' && <span className="ml-3 text-sm text-meta">This language is awaiting review by a speaker.</span>}
      </div>
    </section>
  )
}
