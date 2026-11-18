# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Staff portals are the main design priority. One UI codebase serves every portal; what it shows depends on the organisation type.

| User | Situation | Job |
|---|---|---|
| Distributor warehouse operator | Standing, with a handheld scanner, often in poor light | Receive cartons from pharma companies and dispatch them to shops |
| Shop counter staff | A queue of customers, with a USB scanner or a phone | Receive stock, sell packs, handle returns |
| Pharma dispatch or QA officer | At a desk | Create batches, print pack labels, ship to distributors, issue recalls |
| Regulator or drug inspector | At a desk | Trace any pack, review consumer complaints, issue alerts |

Public portal:

| User | Situation | Job |
|---|---|---|
| Consumer (patient or buyer) | On a phone, often inside the shop | Type or scan a pack's code and get one clear answer |

The project's evaluators, a professor and examiners, see it in a live demo on four PCs.

## Product Purpose

Asali tells a person whether a medicine pack is genuine. Every pharma company, distributor and shop keeps its own records in its own database, structured its own way. Each one lets the others read its data and never write to it. Each organisation's portal records what that organisation did with a pack: made it, shipped it, received it, sold it.

To check a pack, the system follows its route across the organisations' records. It adds text evidence, such as complaints, temperature reports and quality notices, which ML models have linked to the pack. The answer comes back in plain words.

Success means:
- staff record every movement by scanning, quickly and without mistakes;
- consumers get an answer they can act on;
- the evaluators can see the system really running across four separate machines.

## Positioning

There is no central database. The answer is assembled at the moment of asking, from the records of the organisations that actually handled the pack, and each fact names the organisation and machine it came from. Text evidence is linked to structured records and checked against them. A complaint saying "bought in Mumbai" for a pack recorded as sold in Delhi is a signal of a copied code.

## Operating Context

- **Twelve organisations on four PCs:** 3 pharma, 3 distributors, 3 shops (Delhi, Mumbai, Bengaluru), 2 consumer portals and 1 regulator, plus a directory service.
- **Location matters for shops.** A shop's portal reflects its city and state: local alerts, receipt language, the distributors that serve it.
- **Packs carry a GS1 QR code** (Digital Link) and a human-readable line. Codes reach the system through USB keyboard-wedge scanners, phone cameras and typing, and each path produces misread characters that the system must correct or flag.
- **The portals run on a local network,** with no internet dependency.

## Capabilities and Constraints

- **Verdicts:** Genuine, Caution, Do not use, Cannot check. Each comes with reasons and evidence. There are no numeric trust scores.
- **Misread codes** are corrected against what the organisation expects. A consumer must confirm a corrected code before seeing Genuine.
- **Text never condemns a pack on its own.** An unverified complaint is shown as an allegation. Official notices and corroborated patterns count only under fixed rules.
- **Simulation mode** (all organisations on one computer) must always be labelled as simulation.
- **Read-only sharing:** an organisation writes only to its own database. Other organisations' data is read through a read-only API.
- **Full specification:** `asali-net/docs/plan/` (`PLAN.md`, `TEXT_ML.md`, `DESIGN.md`).

## Brand Commitments

- **Product name:** Asali.
- **Verdict words:** plain English (Genuine, Caution, Do not use, Cannot check), with an optional Hindi line under the verdict on the consumer portal. "Nakali" and "trust score" are not used.
- **Organisation names** are fictional; no real company names.
- **Voice:** plain, specific, calm. The conclusion first, then the reason, then what to do.

## Evidence on Hand

- **No real customers, testimonials or field data exist.** All organisations, packs and documents are generated for the demonstration and must be presented as such.
- **The ML evaluation reports only what the evaluation script produced.** A hand-written test set is to be written by the team, not generated.
- **A measured baseline of the previous dashboard exists:** 70 findings from the Impeccable detector, recorded in `asali-net/docs/plan/DESIGN.md` section 1. Its look is an anti-reference.

## Product Principles

1. **The answer first, the reasons next, the evidence last.**
2. **Say what we don't know.** A missing organisation, an unconfirmed correction or an allegation is named as such, never smoothed over.
3. **Scanning is the core act.** Staff flows are built around the scan and work without a mouse.
4. **Every fact shows where it came from.** The organisation and the machine.
5. **Quiet until something is wrong.**

## Accessibility & Inclusion

- WCAG 2.2 AA.
- Every staff flow works with the keyboard and a keyboard-wedge scanner alone.
- Status is never shown by colour alone.
- Touch targets are at least 44 px for phone use.
- `prefers-reduced-motion` is respected.
- Receipts may be printed in Hindi, Marathi or Kannada, with the right `lang` attribute.
