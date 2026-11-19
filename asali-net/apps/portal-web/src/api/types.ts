// Shapes the node API returns. Written by hand against the routes in services/node (see CHANGES.md D17).

export type OrgType = 'pharma' | 'distributor' | 'shop' | 'consumer' | 'regulator'
export type Verdict = 'genuine' | 'caution' | 'do_not_use' | 'cannot_check'

export interface ShopSettings {
  area: string
  state_code: string
  receipt_language: 'en' | 'hi' | 'mr' | 'kn'
  drug_licence_no: string
  gstin: string
  helpline: string
}

export interface Config {
  org_id: string
  org_type: OrgType
  name: string
  city: string
  state: string
  mode: 'network' | 'simulation'
  host_name: string
  issuer_code: string | null
  shop: ShopSettings | null
}

export interface Me {
  username: string
  role: string
  display_name: string
  org_id: string
  org_type: OrgType
}

export type RowStatus = 'ok' | 'corrected' | 'duplicate' | 'not_expected' | 'needs_choice' | 'unreadable' | 'removed'

export interface ScanRow {
  row_id: number
  raw: string
  status: RowStatus
  message: string
  gtin: string | null
  serial: string | null
  lot: string | null
  expiry: string | null
  corrected_from: string | null
  choices: string[]
}

export interface Counts {
  scanned: number
  needs_attention: number
  expected: number
}

export interface Reason {
  code: string
  strength: 'do_not_use' | 'caution' | 'cannot_check'
  text: string
  evidence: Record<string, unknown>[]
}

export interface HistoryEvent {
  event_id: string
  org_id: string
  event_type: string
  at: string
  city: string
  from_org: string | null
  to_org: string | null
  ref: string | null
}

export interface HistoryHop {
  org_id: string
  org_name: string
  city: string
  unavailable: string | null
  events: HistoryEvent[]
  served_by: { org_id: string; host_name: string; at: string } | null
}

export interface DocHit {
  doc_id: string
  org_id: string
  org_name: string
  doc_type: string
  kind: 'official' | 'operational' | 'allegation'
  title: string
  created_at: string
  snippet: { text: string }
  linked_to: { entity: string; confidence: number; because: string[] }[]
  claims: { name: string; value: unknown; check: string; against: string }[]
  issue_labels: string[]
  label: string
}

export interface Source {
  org_id: string
  status: 'answered' | 'unreachable' | 'skipped'
  ms: number
  host_name: string | null
  reason: string
}

export interface VerifyResult {
  verdict: Verdict
  word: string
  headline: string
  action: string
  reasons: Reason[]
  pack: {
    gtin: string | null
    serial: string
    lot: string | null
    expiry: string | null
    product: { brand: string; generic: string; strength: string } | null
    found: boolean
  }
  read: { raw: string; decision: string; corrections: { field: string; from: string; to: string; cost: number }[]; confirmed?: boolean } | null
  history: HistoryHop[]
  documents: DocHit[]
  sources: Source[]
  mode: 'network' | 'simulation'
  checked_at: string
}

export type CheckReply =
  | { status: 'done'; result: VerifyResult }
  | { status: 'needs_confirmation'; message: string; check_id: string; serial: string; serial_shown: string }
  | { status: 'needs_choice' | 'unreadable'; message: string; choices: string[] }

export interface NetworkOrg {
  org_id: string
  org_type: OrgType
  name: string
  city: string
  state: string
  host_name: string
  online: boolean
  latency_ms: number | null
  engine: string | null
  vault: string | null
  last_seen: string | null
}

export interface Network {
  orgs: NetworkOrg[]
  online: number
  total: number
  mode: 'network' | 'simulation'
  self: string
}

export interface Party {
  org_id: string
  org_type: OrgType
  name: string
  city: string
  state: string
  host_name: string
  serves_here: boolean
}

export interface Problem404 {
  code: string
}
