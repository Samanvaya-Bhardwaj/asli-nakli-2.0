# Portal review: audit and critique

Done as an in-thread pass by Claude following the Impeccable `audit` and `critique` references, on 20 Nov 2026, with the detector, axe and the browser screenshots in `docs/evidence/ui/e2e/` as evidence. It is not a second person's review. The Impeccable skill reported a newer version (4.10.0 against 4.9.1); it was not updated.

## Audit health score

| # | Dimension | Score | Key finding |
|---|-----------|-------|-------------|
| 1 | Accessibility | 4 | axe (WCAG 2.2 AA tags) clean on 25 screens and states, light and dark. Contrast checked for 36 token pairs in both themes. One real finding, fixed: scrollable tables were not keyboard focusable. |
| 2 | Performance | 3 | The first build was one 540 kB script. Staff portals are now a separate 73 kB chunk, so a customer's phone loads 468 kB (150 kB gzip). Not measured on a slow connection. |
| 3 | Theming | 4 | No hard-coded colours outside `tokens.css`. Dark works and is now switchable (System, Light, Dark). |
| 4 | Responsive | 3 | 360 px checked on the report page, the phone menu and the network page: no sideways scroll. Two touch targets were 36 px; both now 44 px. Touch gestures were not tested on a real phone. |
| 5 | Implementation integrity | 4 | Detector at zero findings. The one earlier hit (side-tab border) was fixed in the design. |
| **Total** | | **18/20** | Excellent, minor polish |

## Critique: what was found and what changed

- **Verdict block looked faded in the first screenshot.** Cause: the screenshot and the contrast check ran during the 160 ms fade-in. The e2e helper now waits for the fade to finish, so the evidence shows the real colours.
- **Ten documents under every result.** For a copied pack the page was mostly unrelated certificates. The server already puts documents that raised a finding first; the page now shows three and puts the rest under "Show 7 more documents".
- **Reason chips wrapped to three lines** ("Do / not / use") and **dates wrapped** ("1 / Oct"). Both fixed with no-wrap.
- **The phone bottom bar had no way to reach the 5th to 7th menu items** (Documents, Network and others). Added "More", with the theme switch and Log out inside it.

## Not done

- No review by a second person, no test with a real shop assistant or customer.
- Hindi, Marathi and Kannada receipt text still needs a speaker.
- The Humanizer pass on prose was not run (plugin not installed). `check_copy.mjs` covers banned words, dashes and emoji only.
