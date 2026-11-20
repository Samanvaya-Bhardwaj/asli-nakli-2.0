// Generated from services/node/asali_node/contract.py. Do not edit: run npm run gen:types.

export interface Contract {
CheckDone: CheckDone
CheckNeedsChoice: CheckNeedsChoice
CheckNeedsConfirmation: CheckNeedsConfirmation
Config: Config
Me: Me
Network: Network
Parties: Parties
VerifyResult: VerifyResult
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "CheckDone".
 */
export interface CheckDone {
result: VerifyResult
status: "done"
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "VerifyResult".
 */
export interface VerifyResult {
action: string
checked_at: string
documents: DocHit[]
headline: string
history: HistoryHop[]
mode: ("network" | "simulation")
pack: Pack
read: (CodeRead | null)
reasons: Reason[]
sources: Source[]
verdict: ("genuine" | "caution" | "do_not_use" | "cannot_check")
word: string
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "DocHit".
 */
export interface DocHit {
claims: ClaimRow[]
created_at: string
doc_id: string
doc_type: string
issue_labels: string[]
kind: ("official" | "operational" | "allegation")
label: string
linked_to: DocLink[]
org_id: string
org_name: string
snippet: Snippet
title: string
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "ClaimRow".
 */
export interface ClaimRow {
against: string
check: string
name: string
value: unknown
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "DocLink".
 */
export interface DocLink {
because: string[]
confidence: number
entity: string
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "Snippet".
 */
export interface Snippet {
text: string
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "HistoryHop".
 */
export interface HistoryHop {
city: string
events: HistoryEvent[]
org_id: string
org_name: string
served_by: (ServedBy | null)
unavailable: (string | null)
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "HistoryEvent".
 */
export interface HistoryEvent {
at: string
city: string
event_id: string
event_type: string
from_org: (string | null)
gtin: string
lot: (string | null)
org_id: string
ref: (string | null)
serial: string
to_org: (string | null)
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "ServedBy".
 */
export interface ServedBy {
at: string
host_name: string
org_id: string
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "Pack".
 */
export interface Pack {
expiry: (string | null)
found: boolean
gtin: (string | null)
lot: (string | null)
product: (Product | null)
serial: string
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "Product".
 */
export interface Product {
brand: string
generic: string
strength: string
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "CodeRead".
 */
export interface CodeRead {
confirmed?: (boolean | null)
corrections: {
[k: string]: unknown
}[]
decision: string
raw: string
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "Reason".
 */
export interface Reason {
code: string
evidence: {
[k: string]: unknown
}[]
strength: ("do_not_use" | "caution" | "cannot_check")
text: string
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "Source".
 */
export interface Source {
host_name: (string | null)
ms: number
org_id: string
reason: string
status: ("answered" | "unreachable" | "skipped")
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "CheckNeedsChoice".
 */
export interface CheckNeedsChoice {
choices: string[]
message: string
read?: (CodeRead | null)
status: ("needs_choice" | "unreadable")
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "CheckNeedsConfirmation".
 */
export interface CheckNeedsConfirmation {
check_id: string
choices: string[]
message: string
read: CodeRead
serial: string
serial_shown: string
status: "needs_confirmation"
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "Config".
 */
export interface Config {
city: string
gs1_prefix: (string | null)
host_name: string
issuer_code: (string | null)
mode: ("network" | "simulation")
name: string
org_id: string
org_type: ("pharma" | "distributor" | "shop" | "consumer" | "regulator")
shop: (ShopSettings | null)
state: string
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "ShopSettings".
 */
export interface ShopSettings {
area: string
drug_licence_no: string
gstin: string
helpline: string
receipt_language: ("en" | "hi" | "mr" | "kn")
state_code: string
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "Me".
 */
export interface Me {
display_name: string
org_id: string
org_type: ("pharma" | "distributor" | "shop" | "consumer" | "regulator")
role: string
username: string
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "Network".
 */
export interface Network {
directory_stale: unknown
mode: ("network" | "simulation")
online: number
orgs: NetworkOrg[]
self: string
total: number
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "NetworkOrg".
 */
export interface NetworkOrg {
city: string
engine: (string | null)
host_name: string
last_seen: (string | null)
latency_ms: (number | null)
name: string
online: boolean
org_id: string
org_type: ("pharma" | "distributor" | "shop" | "consumer" | "regulator")
reason?: (string | null)
state: string
vault: (string | null)
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "Parties".
 */
export interface Parties {
parties: Party[]
}
/**
 * This interface was referenced by `Contract`'s JSON-Schema
 * via the `definition` "Party".
 */
export interface Party {
base_url: string
city: string
host_name: string
name: string
org_id: string
org_type: ("pharma" | "distributor" | "shop" | "consumer" | "regulator")
serves_here: boolean
state: string
}
