# Portal design

Part of the plan in `PLAN.md`. It covers the look, the screens, the components, motion, writing, and how the Impeccable and Humanizer skills are used to keep the UI from looking machine-made.

## 1. What was wrong with the old dashboard

Measured, not guessed. `npx impeccable detect` on `dashboard/*.html` and `style.css` found 70 problems and 16 advisory notes:

| Rule | Count | Where |
|---|---|---|
| low-contrast | 33 | Grey metadata text at 2.5–3:1; placeholders at 1.7:1 |
| cramped-padding | 27 | Tables and sub-navigation with text flush against borders |
| tiny-text | 14 | Body text at 11.5 px |
| dark-glow | 5 | Lime `#D8FF3E` glow shadows |
| repeating-stripes-gradient | 4 | Hatched decorative tracks |
| em-dash-overuse | 2 | 74 em dashes on `verify.html` alone |
| broken-image | 1 | An `<img>` with no `src` |

What the detector doesn't measure, but a person sees at once:
- **A marketing site, not a tool.** The home page opens with a hero ("Is this medicine *genuine or fake?*"), then a row of vanity numbers ("4 Databases", "2 PCs", "2 Project phases"), sticker chips and a product render.
- **A label on every section.** 58 `eyebrow` labels: small capitals above every heading, saying what the heading already says.
- **Cards everywhere.** 91 `card` uses, often nested (card → card-inset → kv). The page is a wall of boxes.
- **A design system with a story.** The stylesheet opens with "Forensic Console Design System… instrument-panel language… squircle capped bars + arc gauge with a knob… highlighter/sticker text spans." It was styled to look like something, not to help someone do something.
- **A score dial for a yes/no question.** The verify page centres on a 0–100 trust-score gauge. The number has no calibrated meaning, so it adds noise and borrowed authority.
- **Everything shown at once.** One page carries the code input, examples, data-source notes, corrections, did-you-mean, score, verdict, findings, the product card, the journey, combined details, every database's answer and the ledger entry. Nothing is ranked.
- **Three display fonts** (Anton, IBM Plex Sans Condensed, Iosevka), neon lime on near-black, and a self-hosted subset font. Effort was spent on texture instead of hierarchy.

The new portal starts from what each person is trying to do.

## 2. Who uses it, and where

| Portal | Person | Situation | What they need from the screen |
|---|---|---|---|
| Pharma | Dispatch or QA officer | Desk, mouse and keyboard, sometimes a USB scanner | Create batches, print labels, scan cartons out, see what left and where it went |
| Distributor | Warehouse operator | Standing, handheld scanner, poor light, gloves | A big scan target, loud clear feedback, a count against the expected total, one button to finish |
| Shop | Counter staff | Queue of customers, USB scanner or phone | Sell in two actions; receive stock quickly; see alerts that affect their stock |
| Consumer | Patient or buyer | Phone, one hand, maybe in the shop | Type or scan a code and get a clear answer in one sentence, then the why |
| Regulator | Drug inspector | Desk | Find patterns across complaints, trace any pack, issue alerts |

Design principles, in priority order:
1. **One job per screen.** Staff screens are built around one action: scan, sell, receive, dispatch.
2. **The answer first, then the reasons, then the evidence.** Never the other way round.
3. **Words, not scores.** A verdict is a sentence. Numbers appear only where they are measurements: counts, temperatures, dates, link confidence.
4. **Quiet until something is wrong.** Normal states are calm and neutral; colour and sound are kept for problems and confirmations.
5. **Every state is designed:** empty, loading, partial (some organisations didn't answer), error, offline, corrected input.
6. **Scanner and keyboard first.** Every staff flow works without a mouse.

## 3. Visual system

### 3.1 Colour tokens

Defined as CSS variables in `apps/portal-web/src/styles/tokens.css` and mapped into Tailwind v4 with `@theme`. Light is the default theme (warehouses and shop counters are bright); dark follows `prefers-color-scheme` and can be toggled.

```css
:root {
  /* neutrals */
  --bg: #F7F7F5;  --surface: #FFFFFF;  --sunken: #EFEFEC;
  --border: #DADAD5;  --border-strong: #B9B9B2;
  --text: #1B1B19;  --text-muted: #55554E;  --text-meta: #66665E;   /* meta: 13px+ only */

  /* verdict and row status: never used for anything else */
  --ok-fg: #14532D;      --ok-bg: #E7F4EA;      --ok-line: #9BD3A9;      --ok-solid: #1F7A3A;
  --warn-fg: #7A4A00;    --warn-bg: #FDF2DC;    --warn-line: #F0C77A;    --warn-solid: #9A5B00;
  --bad-fg: #8A1C12;     --bad-bg: #FBE7E4;     --bad-line: #F0A79D;     --bad-solid: #B42318;
  --unknown-fg: #3F4651; --unknown-bg: #ECEEF1; --unknown-line: #C3C8D0; --unknown-solid: #5B6573;

  /* one accent per portal type: top band, primary button, focus ring, active nav item */
  --accent: var(--accent-pharma);
  --accent-pharma: #24569E;  --accent-distributor: #6A3D9A;  --accent-shop: #0B6A80;
  --accent-consumer: #1B1B19;  --accent-regulator: #2F3E5C;
  --on-accent: #FFFFFF;
}
:root[data-theme="dark"] { /* and @media (prefers-color-scheme: dark) on :root:not([data-theme="light"]) */
  --bg: #141413;  --surface: #1C1C1A;  --sunken: #111110;  --border: #34342F;  --border-strong: #4A4A43;
  --text: #EDEDE8;  --text-muted: #B4B4AC;  --text-meta: #A2A29A;
  --ok-fg: #9FDCB0; --ok-bg: #12301D; --ok-line: #2E6B41; --ok-solid: #3FA35E;
  --warn-fg: #F3CB80; --warn-bg: #33250C; --warn-line: #7A5A1E; --warn-solid: #D08A1C;
  --bad-fg: #F5A99F; --bad-bg: #3A1512; --bad-line: #7E2E25; --bad-solid: #E0523F;
  --unknown-fg: #C3C8D0; --unknown-bg: #22262C; --unknown-line: #454C56; --unknown-solid: #8A93A0;
  --accent-pharma: #7FA6E0; --accent-distributor: #B593DB; --accent-shop: #5DB3C7;
  --accent-consumer: #EDEDE8; --accent-regulator: #9DAED0; --on-accent: #111110;
}
```

The app sets `data-portal="<org_type>"` on `<html>`, and a rule per type sets `--accent`.

Rules:
- Every text and background pair passes WCAG AA: 4.5:1 for body text, 3:1 for text 18 px and up and for UI parts. `scripts/check_contrast.mjs` checks every token pair and runs in CI.
- Status colours appear only as a status (verdict panel, row status, badge), always with an icon and a word.
- No gradients anywhere, no glows, no transparency effects (glass), no coloured shadows.

### 3.2 Type

- **UI: Atkinson Hyperlegible Next.** **Codes and numbers in tables: Atkinson Hyperlegible Mono.**
  - The Braille Institute designed both so that confusable characters (0/O, 1/l/I, 5/S, 8/B) look different.
  - Misread characters are this product's central problem, so the typeface is part of the solution, not decoration.
  - Self-hosted through the `@fontsource` packages; confirm the package names on npm in M8. If they are missing, download the font files from Google Fonts into `src/assets/fonts/` under the SIL OFL licence. The portals work with no internet access.
- **Scale (px):**

  | Size | Use |
  |---|---|
  | 13 | metadata only |
  | 14 | dense tables |
  | 16 | body |
  | 18 | lead text, section headings |
  | 22 | page headings |
  | 28 | consumer verdict on mobile |
  | 36 | consumer verdict on desktop |

  Line height 1.5 for body and 1.25 for headings. Weights: 400 body, 600 headings, 700 verdict headline only.
- **Numbers:** `font-variant-numeric: tabular-nums` in tables and counters.
- **Codes:** always through the `<Code>` component: mono, 500 weight, `letter-spacing: 0.02em`, serial shown in 4-4-3 groups with the separators in `--text-meta`, and a copy button on hover or focus.
- **Minimum size 13 px.** The old 11.5 px text is gone.

### 3.3 Space, shape, depth

- **Spacing:** 4 px base, scale 4, 8, 12, 16, 24, 32, 48, 64. Inside any bordered or filled container, padding is at least 12 px; table cells are 10 px × 12 px.
- **Radius:** 6 px for controls, 10 px for panels and sheets, full for pills. Don't mix radii in one component.
- **Borders over boxes.** Sections are separated by space and a 1 px `--border` rule, not by putting each section in a card.
- **Cards:** at most one level of bordered container; nothing nested inside another bordered container.
- **Shadows** only on things that float: menus, popovers, dialogs, sheets. `0 8px 24px rgb(0 0 0 / 0.12)` in light, none in dark (use `--border-strong`).

### 3.4 Icons

`lucide-react`, 20 px in navigation and buttons, 16 px inline, stroke 1.75. An icon goes with a label; an icon-only button gets an `aria-label` and a tooltip. No decorative icons above headings.

## 4. Banned patterns (machine-made tells)

The implementing agent must not produce any of these. The review in M10 checks the list, alongside `npx impeccable detect`.

1. Inter, Roboto, Space Grotesk, Poppins or the system UI font as the chosen font.
2. Gradients of any kind, especially purple-to-blue; gradient text.
3. Glow or coloured shadows; glassmorphism (frosted panels); neon accents on black.
4. Cards inside cards; a bordered box around every section.
5. A rounded-square icon tile above headings or in front of every list item.
6. Small-caps labels above headings ("eyebrows").
7. Stat tiles with vanity numbers ("12 organisations", "4 PCs", "99.9% uptime").
8. Hero sections, landing pages, slogans or marketing copy inside the portals.
9. Score gauges, dials, radial progress for verdicts, or number count-up animations.
10. Emoji anywhere in the UI.
11. Decorative stripes, hatching, noise textures, blobs or illustrations.
12. Grey text on coloured backgrounds; text below 13 px; placeholder text used as the label.
13. More than one primary (filled accent) button visible in a view.
14. A spinner alone for anything over one second. Show what is happening ("Asking 9 of 12 organisations…") with skeleton rows.
15. Centred body text, or text blocks wider than 72 characters.
16. Toasts for anything the person must act on. Use inline messages; toasts only confirm.
17. Tabs to hide a flow's steps; modals for multi-step work. Use a page or a sheet.
18. Bouncy springs, parallax, scroll-triggered reveals, page-load stagger animations.
19. Default shadcn look left as-is: zinc greys, `shadow-sm` cards on everything, `rounded-xl`. shadcn components are re-skinned with our tokens.

## 5. App structure

### 5.1 Shell

```
desktop (≥ 1024 px)
┌───────────┬──────────────────────────────────────────────────────────────┐
│ ▌Apna     │  Sell                                        11 of 12 online │
│  Chemist  │  ─────────────────────────────────────────────────────────── │
│  Shop ·   │                                                              │
│  Andheri, │   (screen content, max width 1120 px)                        │
│  Mumbai   │                                                              │
│           │                                                              │
│  Sell     │                                                              │
│  Receive  │                                                              │
│  Stock    │                                                              │
│  Returns  │                                                              │
│  Alerts 2 │                                                              │
│  Documents│                                                              │
│           │                                                              │
│  ──────── │                                                              │
│  R. Patil │                                                              │
│  Log out  │                                                              │
└───────────┴──────────────────────────────────────────────────────────────┘
 ▌ = 3 px band in --accent at the top of the sidebar
```

- **Sidebar:** 232 px wide. At most 7 items, in the order of how often they are used.
- **Mobile (< 768 px):** a top bar (org name and network status), a bottom bar with the 4 most used items, and "More" for the rest.
- **Consumer portal:** no sidebar. A single column, 560 px max. Header: "Asali · Check a medicine · Delhi".
- **Network status, top right:**
  - "11 of 12 online" as a button that opens a popover listing who is unreachable and since when;
  - in simulation mode, a grey full-width band above everything: "Simulation: all organisations are running on this computer".

### 5.2 Routes per portal type

Built from `/api/config`:

| Type | Routes (first is home) |
|---|---|
| pharma | `/dispatch`, `/batches`, `/batches/:lot`, `/batches/:lot/labels`, `/products`, `/recalls`, `/documents`, `/activity` |
| distributor | `/receive`, `/receive/:shipment`, `/dispatch`, `/stock`, `/documents`, `/activity` |
| shop | `/sell`, `/receive`, `/receive/:shipment`, `/stock`, `/returns`, `/alerts`, `/documents` |
| consumer | `/` (check), `/result/:checkId`, `/report`, `/history` |
| regulator | `/investigate`, `/complaints`, `/alerts`, `/licences`, `/network` |
| all | `/login` (staff), `/network` (read-only list for every portal) |

## 6. Key screens

### 6.1 Scan session (dispatch, receive, sell)

The most used screen in the system:

```
Dispatch to North Star Distributors, Delhi                    [Change]
───────────────────────────────────────────────────────────────────────
┌─────────────────────────────────────────────┐   18 packs scanned
│  Scan or type a code                        │    2 need a look
│  [                                    ]     │
│  Scanner ready · Camera                     │   [Record dispatch of 18]
└─────────────────────────────────────────────┘    Discard session
                                                                      
  ✓  TPM9-S346-Q37  Amoxil 500 mg · TP24A017 · exp 03/2027      Undo
  ✓  TPD2-5VT4-F5H  Amoxil 500 mg · TP24A017 · exp 03/2027      Undo
  !  Read as TPM0-S346-Q37, corrected to TPM9-S346-Q37            Undo
  ✕  MVV3-7E3S-3EW  Not in your stock. It was shipped on 2 Nov.  Remove
  ✕  Could not read this code. Scan again.                       Remove
```

- The input always has focus. Scanner bursts land there wherever focus is (`PLAN.md` section 10.3).
- **Feedback for each scan, within 150 ms:**
  - the row appears at the top;
  - a sound (section 8);
  - a vibration on phones;
  - the row status is announced politely by the live region.
- **Row states:**

  | State | Shown as |
  |---|---|
  | ok | ✓ in `--ok-solid` |
  | corrected | ! in `--warn-solid`, raw → fixed, with Undo |
  | rejected | ✕ in `--bad-solid`, with the reason in one sentence and what to do |
  | duplicate | "Already scanned in this session." Not added again. |

- **Receive mode** adds the count against expected ("18 of 20"), and the button "Show the 2 missing" lists them.
- **Finishing:** the primary button names the action and the count. It is disabled while any row is unresolved (needs a choice). Discard asks for confirmation.
- **Camera:** "Camera" opens the camera in a sheet over the list; each decoded code drops into the input. On HTTP the button reads "Camera needs HTTPS. Use the scanner or type the code." with a link to the runbook.

### 6.2 Consumer check

```
Check a medicine
Type the 11-character code printed after SN, or scan the QR code.
[ TPM9-S346-Q37                      ] [Check]
Scan with camera

──────────────────────── result ─────────────────────────
┃ Genuine
┃ Made by Tarang Pharma, sold by Sharma Medicos, Delhi on 12 Nov 2026.
┃ Amoxil 500 mg · Batch TP24A017 · Expires 31 Mar 2027

Where this pack has been
  1 Nov  Made           Tarang Pharma, Baddi             PC-B
  3 Nov  Received       North Star Distributors, Delhi   PC-C
  5 Nov  Received       Sharma Medicos, Delhi            PC-D
 12 Nov  Sold           Sharma Medicos, Delhi            PC-D

Documents about this pack (2)
  Certificate of analysis, batch TP24A017 · Tarang Pharma · 28 Oct
     "Assay 99.2%. Dissolution 92% at 30 min. Complies."  Linked: exact batch and product
  …

Checked with 11 of 12 organisations · Western Medilink did not answer (not on this pack's route)
Report a problem with this pack
```

- **Verdict block:** a 4 px left rule in the status colour, a status-tinted background, the verdict word at 28/36 px, one sentence, then the product line.
- **Do not use** adds one more line under the sentence: "Do not take this medicine. Show this result to the pharmacist or call the drug control helpline."
- **Cannot check** says who didn't answer and offers "Try again".
- **Corrected reading:** before any verdict, a confirmation block: "Does your pack show TPM9-S346-Q37?" with the differing characters underlined. "Yes, check it" / "No, scan again".
- **Documents:**
  - the label for an allegation is "Reported by a customer, not verified" in `--text-muted`;
  - official documents name the authority;
  - each document shows why it was linked, from `because`;
  - a contradiction is shown inline: "Says bought in Mumbai. Records show sold in Delhi."
- **The host name column** (PC-B, PC-C…) is visible in the history. It shows the distribution plainly, and stays in the final product.

### 6.3 Documents (staff)

- Paste or upload text, with an optional type.
- After saving, the "What we found" list shows:
  - the predicted type with its confidence;
  - links, each with confidence and reason, plus a "Not this" button that removes the link (stored as feedback);
  - extracted claims;
  - for complaints, the issue labels.
- The document list has filters for type, linked or unlinked, and date.

### 6.4 Regulator complaints

- A table grouped by batch. Columns: product and batch, complaints (independent count), cities, top issue labels, "unusual" flag from M5, status of the batch. A row opens the complaints with their links and claims.
- Above the table, one line: "3 batches have unusually many complaints this month."

### 6.5 Network page (every portal)

A table with these columns:
- organisation;
- type;
- city;
- host (PC name);
- online/offline with last-seen time;
- latency from this node;
- the database engine and vault it uses (from `/share/v1/org`).

This page is how a viewer sees the four machines and the different storage behind each organisation.

## 7. Components

Primitives come from shadcn/ui (Radix): Button, Input, Label, Select, Dialog, Sheet, Popover, Tooltip, Table, Badge, Separator, Skeleton, Toast (Sonner). They are re-skinned with our tokens. Custom components, each with a Vitest test and every state shown on a `/dev/components` route, which is available only in development:

| Component | Props (sketch) | States |
|---|---|---|
| `Code` | `value, kind: 'serial'\|'gtin'\|'lot', diffAgainst?` | normal, diff-highlight |
| `ScanBox` | `onRead(raw, source)`, `mode`, `disabled` | idle, listening, camera, camera-unavailable |
| `ScanList` | `rows: ScanRow[]`, `onUndo`, `onChoose` | empty ("Scanned packs appear here."), rows |
| `ScanRow` | `row` | ok, corrected, needs-choice, rejected, duplicate |
| `VerdictBlock` | `result` | genuine, caution, do_not_use, cannot_check, needs_confirmation, loading |
| `PackHistory` | `history` | full, with-gap, single-hop |
| `EvidenceList` | `documents` | empty, items, possible-only |
| `ReasonList` | `reasons` | n/a |
| `NetworkStatus` | from `/api/network` (polls every 15 s) | all-online, some-offline, directory-down, simulation |
| `PartyPicker` | `type, region?` | loading, list, empty, offline orgs disabled |
| `EmptyState` | `title, text, action?` | n/a |
| `ProblemMessage` | `problem` (problem JSON) | n/a |
| `PrintSheet` | label sheet and receipt | print stylesheet |

Loading: skeleton rows plus a sentence. For a verification it is live: "Asked 7 of 9 organisations…", updated as answers arrive. The backend streams progress with Server-Sent Events from `/api/verify/stream`, and the UI falls back to the plain POST if the stream fails.

## 8. Motion and sound

The library is Motion (`motion` package, `motion/react`). One library, used sparingly.

| Where | What | Duration, easing |
|---|---|---|
| New scan row | Fade in, plus a 4 px move down | 140 ms, ease-out |
| Row status change | Background colour change | 160 ms |
| Sheet and dialog | Slide 12 px and fade | 180 ms in, 140 ms out, ease-out |
| Verdict block | Fade in only, after the data is ready | 160 ms |
| Popover | Fade and scale from 0.98 | 120 ms |

- No animation on page load, on scroll, or on numbers.
- `prefers-reduced-motion: reduce` turns every transition into an instant change; `MotionConfig reducedMotion="user"` at the root.
- **Sound** (Web Audio, generated, no files): ok = one 880 Hz beep for 70 ms; corrected = two 660 Hz beeps; rejected = one 220 Hz tone for 180 ms. Off by default for consumers, on for staff, toggled in the user menu.
- **Vibration:** `navigator.vibrate(30)` for ok, `[40, 60, 40]` for rejected.

## 9. Accessibility and responsiveness

- WCAG 2.2 AA; checked with `@axe-core/playwright` in every Playwright test. Zero violations is the gate.
- Every flow works with the keyboard alone. Focus ring: 2 px `--accent` with a 2 px offset. Never remove outlines.
- Live regions:
  - scan results: `aria-live="polite"`;
  - the verdict: an `role="status"` region that is focused when it appears.
- Touch targets are at least 44 × 44 px.
- `lang` is set on receipts printed in Hindi, Marathi or Kannada.
- Layout breakpoints: 360, 768, 1024, 1280. No horizontal scrolling at 360 px except inside wide tables, which scroll in their own container with the first column sticky.

## 10. Writing in the UI

### 10.1 Voice

Plain, specific, calm. Write the way a capable pharmacist explains something to a customer: the conclusion first, the reason next, and what to do last.

### 10.2 Rules

1. **Sentence case** everywhere: "Record dispatch", not "Record Dispatch".
2. **Buttons say the action and its object:** "Record sale", "Check medicine", "Show the 2 missing". Never "Submit", "OK", "Continue" alone.
3. **Errors say what happened, then what to do:** "This code is not in your stock. It was shipped to Apna Chemist on 2 Nov. Remove it from this sale."
4. **No word that only sounds good:** seamless, robust, powerful, cutting-edge, leverage, empower, unlock, effortless, streamline, delve, journey, ecosystem, solution, revolutionary.
5. No exclamation marks. No emoji. No em dashes in UI text (use commas, colons, full stops).
6. **Formats:**

   | Kind | Format |
   |---|---|
   | dates | `12 Nov 2026`, `12 Nov 2026, 14:05` (IST); `3 Nov` within the current year |
   | money | `₹120.50` |
   | temperature | `14.2 °C` |
   | codes | grouped, in `<Code>` |
   | counts | digits |

7. **Name organisations, not database ids:** "Sharma Medicos, Delhi", not `shop-delhi`. Ids appear only on the Network page and in tooltips.
8. **Say when we don't know.** "We could not check this pack", "not verified", "possible link". Never fill a gap with a confident sentence.
9. **Empty states** say what will appear and how to make it appear: "No incoming shipments. Shipments sent to you by a pharma company appear here."
10. **Labels sit above fields.** Placeholders only show an example format.

### 10.3 Vocabulary

| Say | Don't say |
|---|---|
| pack | item, unit (in the UI) |
| batch | lot (UI); lot is fine in code |
| code | serial number (except in help text) |
| organisation | node, silo, source |
| record | log, persist, commit |
| Genuine / Caution / Do not use / Cannot check | Asali / Nakali / trust score |

The project name stays Asali. The verdict words are plain English, with an optional Hindi line under the verdict on the consumer portal.

## 11. Using the skills

| When | Skill command | What we expect |
|---|---|---|
| M0 | `npx impeccable install --providers=claude --scope=project`, then reload Claude Code, then `/impeccable init` | `PRODUCT.md` written, using sections 2–4 of this file as the answers |
| M8, before building the shell | `/impeccable shape the scan session screen`, and the same for the consumer check | A short UX plan per screen; compare it with section 6 and keep ours where they differ, noting why |
| End of M8 | `/impeccable critique`, `/impeccable audit` | Reports saved to `docs/evidence/ui/m8-critique.md` and `m8-audit.md`; P0 and P1 items fixed |
| During M9, per screen | `/impeccable layout <screen>`, `/impeccable typeset <screen>` | Spacing and hierarchy fixes |
| M10 | `/impeccable distill`, `/impeccable clarify`, `/impeccable harden`, `/impeccable adapt`, `/impeccable polish` | One pass each over all routes; reports saved |
| M10 gate | `npx impeccable detect --json apps/portal-web/dist` and `npx impeccable detect http://localhost:8202` | 0 findings. Save the JSON to `docs/evidence/ui/detect.json`. |
| M10 | `/impeccable document` | Writes the as-built design file; diff it against this file and explain the differences |
| M10, M12 | `/humanizer` on `README.md`, runbooks, help notes, empty-state texts, and the final report | Prose fixed; code and data untouched |

Don't use `/impeccable bolder`, `overdrive` or `delight`. This is a work tool; those push the other way. Use `/impeccable animate` only to check against section 8, not to add motion.

Impeccable telemetry: run `npx impeccable telemetry off` after installing.
