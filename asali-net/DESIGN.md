---
name: Asali
description: One portal UI for every organisation on the Asali network, set in the project's Forensic Console world.
colors:
  lime-signal: "#D8FF3E"
  lime-signal-hover: "#E4FF6B"
  olive-ink: "#4E6B00"
  on-lime: "#0A0B0D"
  console-ground: "#08090A"
  console-surface: "#111316"
  console-surface-raised: "#16181C"
  console-sunken: "#1C1F24"
  console-inset: "#0A0B0D"
  console-rim: "#24272B"
  console-rim-strong: "#36393D"
  console-text: "#F4F4F5"
  console-muted: "#9C9DA0"
  console-meta: "#8A8B8E"
  paper-ground: "#F1F0EC"
  paper-surface: "#FFFFFF"
  paper-surface-raised: "#FAFAF7"
  paper-sunken: "#EEEDE8"
  paper-inset: "#F4F3EF"
  paper-rim: "#E6E5E1"
  paper-rim-strong: "#CFCDC8"
  paper-ink: "#171614"
  paper-muted: "#55544F"
  paper-meta: "#686763"
  genuine-solid-paper: "#0F8B4C"
  genuine-ink-paper: "#0B6B3A"
  genuine-fill-paper: "#E0F0E8"
  genuine-solid-console: "#3DDC84"
  genuine-ink-console: "#6FE8A5"
  genuine-fill-console: "#172F25"
  caution-solid-paper: "#9A6100"
  caution-ink-paper: "#7A4D00"
  caution-fill-paper: "#F1E9DB"
  caution-solid-console: "#FFC53D"
  caution-ink-console: "#FFD67A"
  caution-fill-console: "#322C1C"
  danger-solid-paper: "#CF2A18"
  danger-ink-paper: "#A81F10"
  danger-fill-paper: "#FAE8E6"
  danger-solid-console: "#FF4D3D"
  danger-ink-console: "#FF9186"
  danger-fill-console: "#351C1C"
  unknown-solid-paper: "#5B6573"
  unknown-ink-paper: "#3F4651"
  unknown-fill-paper: "#ECEEF1"
  unknown-solid-console: "#8A93A0"
  unknown-ink-console: "#C3C8D0"
  unknown-fill-console: "#1E2229"
typography:
  wordmark:
    fontFamily: "Anton, 'Archivo Black', sans-serif"
    fontSize: "1.25rem"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "0.01em"
  verdict:
    fontFamily: "Anton, 'Archivo Black', sans-serif"
    fontSize: "clamp(2.4rem, 7vw, 3.5rem)"
    fontWeight: 400
    lineHeight: 0.95
    letterSpacing: "0.005em"
  headline:
    fontFamily: "'IBM Plex Sans Condensed', Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "clamp(1.75rem, 3.2vw, 2.4rem)"
    fontWeight: 700
    lineHeight: 1.1
    letterSpacing: "-0.03em"
  title:
    fontFamily: "'IBM Plex Sans Condensed', Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "1.3rem"
    fontWeight: 600
    lineHeight: 1.16
    letterSpacing: "-0.024em"
  title-small:
    fontFamily: "'IBM Plex Sans Condensed', Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "1.08rem"
    fontWeight: 600
    lineHeight: 1.16
    letterSpacing: "-0.024em"
  body:
    fontFamily: "'IBM Plex Sans Condensed', Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.55
    letterSpacing: "-0.006em"
  label:
    fontFamily: "'IBM Plex Sans Condensed', Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "15px"
    fontWeight: 600
    letterSpacing: "-0.01em"
  meta:
    fontFamily: "'IBM Plex Sans Condensed', Inter, -apple-system, BlinkMacSystemFont, sans-serif"
    fontSize: "13px"
    fontWeight: 500
  code:
    fontFamily: "'Iosevka Web', Iosevka, ui-monospace, SFMono-Regular, Menlo, monospace"
    fontSize: "1em"
    fontWeight: 500
    letterSpacing: "0.02em"
    fontFeature: "tnum"
rounded:
  mark: "9px"
  control: "16px"
  panel: "22px"
  pill: "9999px"
spacing:
  hairline: "4px"
  tight: "8px"
  control-x: "16px"
  button-x: "20px"
  card: "20px"
  card-wide: "28px"
  section: "32px"
  rail-width: "248px"
  content-max: "1180px"
  consumer-max: "640px"
components:
  button-primary:
    backgroundColor: "{colors.lime-signal}"
    textColor: "{colors.on-lime}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "44px"
  button-primary-hover:
    backgroundColor: "{colors.lime-signal-hover}"
    textColor: "{colors.on-lime}"
  button-primary-disabled:
    backgroundColor: "{colors.console-sunken}"
    textColor: "{colors.console-meta}"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.console-text}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "44px"
  button-secondary-hover:
    backgroundColor: "{colors.console-surface-raised}"
  button-danger:
    backgroundColor: "{colors.danger-fill-console}"
    textColor: "{colors.danger-ink-console}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "44px"
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.console-text}"
    rounded: "{rounded.pill}"
    padding: "0 20px"
    height: "44px"
  button-quiet-hover:
    backgroundColor: "{colors.console-sunken}"
  field:
    backgroundColor: "{colors.console-inset}"
    textColor: "{colors.console-text}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "44px"
  scan-field:
    backgroundColor: "{colors.console-inset}"
    textColor: "{colors.console-text}"
    typography: "{typography.code}"
    rounded: "{rounded.control}"
    padding: "0 16px"
    height: "56px"
  card:
    backgroundColor: "{colors.console-surface}"
    textColor: "{colors.console-text}"
    rounded: "{rounded.panel}"
    padding: "20px"
  verdict-card:
    backgroundColor: "{colors.console-surface}"
    textColor: "{colors.console-text}"
    typography: "{typography.verdict}"
    rounded: "{rounded.panel}"
    padding: "24px 20px"
  status-chip:
    backgroundColor: "{colors.genuine-fill-console}"
    textColor: "{colors.genuine-ink-console}"
    typography: "{typography.meta}"
    rounded: "{rounded.pill}"
    padding: "2px 12px"
  nav-item:
    backgroundColor: "transparent"
    textColor: "{colors.console-muted}"
    typography: "{typography.label}"
    rounded: "{rounded.pill}"
    padding: "0 16px"
    height: "44px"
  nav-item-active:
    backgroundColor: "{colors.console-sunken}"
    textColor: "{colors.console-text}"
  theme-switch:
    backgroundColor: "{colors.console-inset}"
    textColor: "{colors.console-muted}"
    rounded: "{rounded.pill}"
    padding: "4px"
---

# Design System: Asali

<!-- Scope: this file owns the visual system of the Asali portals (apps/portal-web). The functional and UX specification lives in docs/plan/DESIGN.md and is referenced by code comments as "DESIGN.md <section>"; those references mean that file, not this one. -->

## Overview

**Creative North Star: "The Forensic Console"**

Asali's portals are a lit instrument on a dark bench. The world comes from the project's own earlier dashboard (the "Forensic Console" stylesheet on the `main` branch), adopted for the portals so the network's working screens and its explainer read as one product. The default dark theme is a near-black console whose surfaces are raised by faint top-lit rims, not drawn with borders; a faint lime and blue overhead light sits on the page so the console reads as an object, not a void. When the system asks for light, the same console is printed on warm paper.

The world is quiet and dense in the way a working tool is quiet: one condensed sans carries every spoken word, one accent marks what you can act on, and the only loud thing on any screen is the verdict. A poster face appears in exactly two places, the "Asali" wordmark and the verdict word, so that when it appears it means the answer. What the system does not know yet (loading, empty, cannot check, simulation) wears one texture, a 45 degree hatch, so uncertainty has a look of its own and is never smoothed over.

The same UI serves all five portal types (consumer, pharma, distributor, shop, regulator) with the same accent and the same components; only navigation and content change. The portals run on a local network, so every font is self-hosted and nothing loads from a CDN. The restyle that produced this system changed only the visual layer: routes, features, copy and logic were left as they were, and future visual work keeps that boundary.

**Key Characteristics:**
- Near-black console (default in dark) and warm paper (light), switched by the system preference or a System / Light / Dark control.
- One accent, lime, identical in every portal; olive ink wherever the accent has to be read as text on paper.
- Depth by inset rims and soft drop shadows, never by hard outlines.
- Pills for buttons and navigation, 16px inset fields, 22px cards.
- Anton only for the wordmark and the verdict word; IBM Plex Sans Condensed for all UI; Iosevka only for codes.
- Hatch as the single texture of the unknown.
- Status always carried by a word and an icon as well as a colour.

## Colors

A near-black (or warm paper) neutral field, one acid-lime signal, and four status families that mean a status and nothing else. Every text and fill pair is gated by `scripts/check_contrast.mjs` (body text 4.5:1, UI parts 3:1) in both themes.

### Primary
- **Lime Signal** (lime-signal): the one accent, the same in every portal and both themes. Fill only: primary buttons, the Asali mark's squircle, text selection, the verification progress bar. Hover lightens it to **Lime Signal Hover** (lime-signal-hover). Text on lime is always **On Lime** (on-lime), near-black.
- **Olive Ink** (olive-ink): the accent when it must be read on paper (bright lime fails contrast there). In the dark theme the accent-ink token resolves to Lime Signal itself. Used for the focus outline, focused-field rim, caret, link hover underline, the active nav icon in the rail, the active tab in the phone bottom bar, and the selected-party rim in pickers.

### Neutral (console, dark)
- **Console Ground** (console-ground): page background under the overhead glow.
- **Console Surface** (console-surface): cards, the staff rail, popovers, sheets.
- **Console Surface Raised** (console-surface-raised): table header row, row hover, hover on quiet controls, the network-status pill.
- **Console Sunken** (console-sunken): active nav pill and active theme segment, skeleton bars, the disabled primary button, progress track.
- **Console Inset** (console-inset): the well inside fields and the theme switch, darker than the surface so inputs read as cut into it.
- **Console Rim / Rim Strong** (console-rim, console-rim-strong): drawn as 1px inset rims on cards, fields and pills; the strong rim marks hover, active nav and secondary buttons.
- **Console Text / Muted / Meta** (console-text, console-muted, console-meta): primary text, secondary text and inactive nav, timestamps and hints. A ghost tone (text-ghost token, 22% white) is used only for separators such as the dot in the brand line.

### Neutral (paper, light)
- **Paper Ground, Surface, Surface Raised, Sunken, Inset, Rim, Rim Strong, Ink, Muted, Meta** (paper-*): the same roles as the console tones, in the same order. Printing always uses paper values regardless of the active theme.

### Status
Each status has four tokens per theme: a solid (chips, dots), an ink (text on its fill), a fill (notices, status chips, danger buttons), and a line (the rim of tinted cards and notices; `--ok-line`, `--warn-line`, `--bad-line`, `--unknown-line`), plus a low-alpha wash used for the verdict gradient and the halo around status dots.
- **Genuine** (genuine-*): green. The Genuine verdict, healthy network, "Scanner ready".
- **Caution** (caution-*): amber. The Caution verdict, organisations not answering, scanner layout warnings, alert counts.
- **Danger** (danger-*): red. "Do not use", errors, destructive buttons.
- **Unknown** (unknown-*): slate. "Cannot check", "not answering", "Scanner paused", the simulation banner.

### Named Rules
**The One Lime Rule.** Lime is the only accent, in every portal and both themes. It is a fill; wherever the accent has to be read as a line or a letter, use the accent-ink token instead, which turns olive on paper.

**The Status Means Status Rule.** Green, amber, red and slate are reserved for verdicts and system state. They are never decoration, never a category colour, and never the only carrier of meaning: every status also has a word, and verdicts and chips have an icon.

## Typography

**Display Font:** Anton (self-hosted via @fontsource, fallback Archivo Black, sans-serif)
**Body Font:** IBM Plex Sans Condensed, weights 400 / 500 / 600 / 700 (self-hosted via @fontsource, fallback Inter, system sans)
**Label/Mono Font:** Iosevka Web (self-hosted subset woff2 at 400 / 500 / 600 in `src/assets/fonts`, SIL OFL; fallback ui-monospace)

**Character:** A condensed workhorse sans that keeps dense tables and long labels calm, against a poster face that is allowed to shout exactly once per screen. Iosevka gives codes the narrow, unambiguous letterforms a misread-character problem needs.

### Hierarchy
- **Verdict** (Anton 400, clamp 2.4rem to 3.5rem, line-height 0.95, uppercase): the verdict word on the verdict card only.
- **Wordmark** (Anton 400, 1.25rem, line-height 1, uppercase): "Asali" beside the mark. Hidden on phones in the staff header, where the mark alone identifies the site.
- **Headline** (Plex Condensed 700, clamp 1.75rem to 2.4rem, line-height 1.1, -0.03em): page titles (`h1`, via the PageHeader component).
- **Title** (Plex Condensed 600, 1.3rem / 1.08rem, line-height 1.16, -0.024em): section headings (`h2`, `h3`), empty-state and sheet titles.
- **Body** (Plex Condensed 400, 16px, line-height 1.55, -0.006em): all running text; prose blocks cap at 72ch, verdict sentences at 60ch. The verdict sentence steps up to 1.125rem.
- **Label** (Plex Condensed 600, 15px): field labels, buttons, organisation name in the rail (17px).
- **Meta** (Plex Condensed 500, 13px): table headers, hints, status chips, bottom-bar labels.
- **Code** (Iosevka 500, inherits size, +0.02em): serials, GTINs, lots, the scan field, mono table cells (14px). Serials are grouped 4-4-3 with quieter separators.

### Named Rules
**The Two Shouts Rule.** Anton appears only as the "Asali" wordmark and the verdict word. Page titles, numbers, headings and banners are Plex Condensed.

**The Codes Only Rule.** Iosevka is for characters a person must copy or compare: serials, GTINs, lots, scanned input. Never for words, labels, headings or placeholder sentences.

## Layout

Staff portals: a 248px sticky left rail (mark and wordmark, organisation name and type/place, navigation pills, account, theme switch) beside the work area, from the `md` breakpoint (768px) up. The work area has a 64px sticky header (blurred translucent ground, network status at right) and a centred main column at max 1180px with 40px side padding (16px on phones). Below `md` the rail disappears: the header carries the compact brand, and a fixed bottom bar holds the first four nav items plus "More", which opens a sheet with the rest, the theme switch and log out. Main content reserves 112px at the bottom on phones so the bar never covers it.

Consumer portal: a single 640px column. Sticky blurred top bar (sticky from `md`) with the brand line and two pill links; the check form in a card; the verdict below; the theme switch and network status in the footer.

Rhythm is Tailwind's 4px grid: 8px between stacked rows, 16px inside notices and fields, 20px (28px from `md`) inside cards, 32px under the page header. Every interactive target is at least 44px tall; the scan field is 56px.

## Elevation & Depth

Hybrid: tonal layering does most of the work (ground, surface, raised, sunken, inset), and every raised surface adds a 1px top-lit inset highlight plus a soft, far-dropped shadow. Edges are drawn with inset box-shadow rims, never with outer borders, so nothing shifts layout and the rim reads as light catching a lip.

### Shadow Vocabulary
- **Console card** (`--shadow-card`, dark: `inset 0 1px 0 rgba(255,255,255,0.07), 0 12px 32px -18px rgba(0,0,0,0.9)`; paper: white top highlight plus two soft warm-black drops): cards, tables, verdict cards, always combined with a 1px inset rim in the rim colour (or the status line for verdicts).
- **Float** (`--shadow-float`): anything above the page: network popover, the phone "More" sheet, the camera sheet.
- **Status halo** (`0 0 0 3px` in the status wash): the small status dots in the network pill and scanner line.
- **Overhead glow** (body background): two fixed radial gradients, lime at top centre and blue at top right, at 5 to 10% alpha.

### Named Rules
**The Rim Not Border Rule.** Containers are edged by a 1px inset rim and a top highlight, not an outline. Hairline rules are kept for dividers inside a container: table row separators and the dashed line above the product line on the verdict card.

## Shapes

Soft, machined geometry. Buttons, nav items, chips, the theme switch and the network pill are full pills. Fields, notices, error messages, skeleton bars and picker rows use the 16px control radius. Cards, tables, empty states, popovers and verdict cards use the 22px panel radius; the camera sheet's top corners are 28px. The mark is a lime squircle (9px radius on a 32px square) holding a circle whose left half is solid and right half hatched: one pack, two readings.

Hatch is the only texture: `repeating-linear-gradient(45deg, hatch 0 2px, transparent 2px 7px)`, where the hatch colour is 5.5% white on console and 7% ink on paper.

### Named Rules
**The Hatch Is the Unknown Rule.** The 45 degree hatch marks exactly what is not known yet: loading skeletons and the verdict-loading card, empty states, the "Cannot check" verdict, the network-status pill while it is asking, and the simulation banner. Do not extend it to decoration, headers or anything that is known.

## Components

### Buttons
Tactile pills that sink a pixel when pressed.
- **Shape:** full pill, min height 44px, 20px side padding, Plex Condensed 600 at 15px.
- **Primary:** lime fill, near-black text, lighter lime on hover. One per view. Disabled goes flat neutral (sunken fill, meta text, no shadow, full opacity) rather than half-opacity lime, so it still reads as a button.
- **Secondary:** transparent with a strong inset rim; raised-surface fill on hover.
- **Danger:** danger fill and ink with the danger line as rim; brightens 10% on hover.
- **Quiet:** text only; sunken fill on hover. Used for log out and sheet close.
- **Motion:** colour transitions at 150ms on the console ease (`cubic-bezier(0.22, 0.61, 0.36, 1)`); `active` translates down 1px.

### Chips
- **Status chip:** pill, status fill with status ink, 13px semibold, 2px by 12px. Always holds a word.
- **Count badge:** pill in caution fill and ink beside the Alerts nav item.

### Cards / Containers
- **Corner Style:** 22px panel radius.
- **Background:** surface.
- **Shadow Strategy:** console card shadow plus a 1px rim (see Elevation & Depth).
- **Border:** none; the rim is an inset shadow.
- **Internal Padding:** 20px, 28px from `md`.
- **Tables** sit in a card that scrolls sideways; the header row is raised-surface with 13px meta labels; rows are separated by hairlines and lift to the raised surface on hover; numbers are tabular.
- **Notices and problem messages:** 16px radius, status fill, status ink, status line rim, capped at 72ch.
- **Empty state:** hatched panel with a rim, a title, one muted sentence and an optional action.

### Inputs / Fields
- **Style:** inset well (inset colour), no border, 1px inset rim, 16px radius, 44px min height, 16px side padding, placeholder in meta.
- **Hover:** rim goes to the strong rim.
- **Focus:** rim turns accent-ink (lime on console, olive on paper); the caret is accent-ink too. No glow.
- **Disabled:** 60% opacity.
- **Scan field:** the same well at 56px, set in Iosevka at 1.125rem with a "Scanner ready / paused" status dot line and a Camera pill below.
- **Party picker:** radio rows at 16px radius; the selected row goes sunken with a 1.5px accent-ink rim; unreachable parties drop to 60% opacity and say "not answering".

### Navigation
- **Staff rail:** pills 44px tall, 19px stroke icons. Inactive: muted text, raised-surface fill and full ink on hover. Active: sunken fill, strong rim, semibold ink, icon in accent-ink.
- **Phone bottom bar:** five equal cells, 64px tall, icon over a 13px label; the active cell turns accent-ink and semibold. Translucent ground with backdrop blur and a top rim.
- **Theme switch:** a pill-shaped inset well holding three segments (System, Light, Dark) as a radio group; the active segment is styled like the active nav pill. "System" leaves the theme to `prefers-color-scheme`.
- **Network status:** a pill with a halo'd status dot, a network icon and "N of M online"; it opens a float popover naming who is not answering. While asking, the pill is hatched.

### Verdict Card (signature)
The answer first. A panel-radius card whose status wash fades from the top-left corner (168 degrees, gone by 58%) into the surface, rimmed in the status line. A 48px (56px from `md`) solid status chip holds the icon (check, triangle, ban, question), beside the verdict word in Anton caps in the status ink. One sentence at 1.125rem, the action in semibold, then a dashed hairline and the product line in muted text. "Cannot check" has no wash; it wears the hatch instead. It enters with a 280ms fade and 6px rise; motion follows the user's reduced-motion preference. While verifying, a hatched card shows "Asked N of M organisations" with a lime progress bar.

### Mark and Brand
The lime squircle mark at 28px, then "Asali" in Anton, then a ghost separator and the portal's own line in muted Plex Condensed. The mark is decorative wherever a name sits beside it.

## Do's and Don'ts

### Do:
- **Do** use lime as a fill on at most one primary button per view, and switch to the accent-ink token for any accent that is text, outline or icon.
- **Do** edge every container with a 1px inset rim plus the console card shadow; float anything above the page with the float shadow.
- **Do** set page titles in IBM Plex Sans Condensed 700 and keep Anton to the wordmark and the verdict word.
- **Do** put every serial, GTIN and lot in Iosevka, grouped and copyable.
- **Do** use the hatch for loading, empty, cannot-check, asking-the-network and simulation, and nowhere else.
- **Do** pair every status colour with a word, and verdicts and chips with an icon.
- **Do** keep every target at least 44px and every text pair passing `scripts/check_contrast.mjs` in both themes; add any new token pair to that script.
- **Do** self-host every font and asset; the portals run on a LAN with no internet.
- **Do** keep print on paper colours (white ground, ink text) whatever theme is on screen.

### Don't:
- **Don't** give a portal its own accent colour; the user chose lime in every portal.
- **Don't** fade a disabled primary button to half-opacity lime; it goes flat neutral.
- **Don't** draw cards or fields with outer borders or heavy outlines.
- **Don't** use the status colours for decoration, branding or categories.
- **Don't** set placeholder text, labels or headings in Iosevka.
- **Don't** load fonts or scripts from a CDN.
- **Don't** change routes, features, copy or logic as part of visual work on these portals.
