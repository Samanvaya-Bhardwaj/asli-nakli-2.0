// Shapes the node API returns. The ones in generated.ts come from services/node/asali_node/contract.py
// (npm run gen:types); the scan-session shapes below are still written by hand.
import type { CheckDone, CheckNeedsChoice, CheckNeedsConfirmation, Config } from './generated'

export type {
  CheckDone, CheckNeedsChoice, CheckNeedsConfirmation, Config, Me, Network, Pack, Parties, Party, Reason, ShopSettings, Source, VerifyResult,
} from './generated'
export type { DocHit, HistoryEvent, HistoryHop, NetworkOrg } from './generated'

export type CheckReply = CheckDone | CheckNeedsConfirmation | CheckNeedsChoice

export type OrgType = Config['org_type']
export type Verdict = import('./generated').VerifyResult['verdict']

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

export interface Problem404 {
  code: string
}
