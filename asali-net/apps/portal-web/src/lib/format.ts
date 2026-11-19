// Dates in IST, money in rupees, codes in groups. One place, so every screen writes them the same way (DESIGN.md 10.2).

const IST = 'Asia/Kolkata'

export function fmtDate(iso: string, withTime = false): string {
  const d = new Date(iso)
  const sameYear = d.toLocaleString('en-IN', { year: 'numeric', timeZone: IST }) === new Date().toLocaleString('en-IN', { year: 'numeric', timeZone: IST })
  const day = d.toLocaleString('en-GB', { day: 'numeric', month: 'short', ...(sameYear && !withTime ? {} : { year: 'numeric' }), timeZone: IST })
  if (!withTime) return day
  const time = d.toLocaleString('en-GB', { hour: '2-digit', minute: '2-digit', hour12: false, timeZone: IST })
  return `${day}, ${time}`
}

export function fmtExpiry(iso: string | null): string {
  if (!iso) return ''
  const [y, m] = iso.split('-')
  return `${m}/${y}`
}

export function money(paise: number): string {
  return `₹${(paise / 100).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
}

export function groupSerial(serial: string): string {
  return serial.length === 11 ? `${serial.slice(0, 4)}-${serial.slice(4, 8)}-${serial.slice(8)}` : serial
}

export function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`
}

export const EVENT_WORD: Record<string, string> = {
  commission: 'Made',
  ship: 'Sent',
  receive: 'Received',
  sell: 'Sold',
  return: 'Returned',
  destroy: 'Destroyed',
}

export const DOC_TYPE_WORD: Record<string, string> = {
  coa: 'Certificate of analysis',
  batch_release_note: 'Batch release note',
  deviation_report: 'Deviation report',
  recall_notice: 'Recall notice',
  temperature_report: 'Temperature report',
  delivery_note: 'Delivery note',
  discrepancy_note: 'Discrepancy note',
  damage_report: 'Damage report',
  counter_note: 'Counter note',
  return_note: 'Return note',
  consumer_complaint: 'Customer complaint',
  nsq_alert: 'Not of standard quality list',
  ban_order: 'Ban order',
  inspection_report: 'Inspection report',
}
