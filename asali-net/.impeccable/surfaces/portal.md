# Surface: portal-web (all five portals)

Mode: Operate. Scope: visual layer of `apps/portal-web` only. Routes, features, copy, API calls and logic stay as they are.

## Direction contract

THESIS: The portal adopts the project's own "Forensic Console" system from the `main` branch dashboard (`dashboard/style.css`), so the network's working screens and its earlier explainer read as one product. It refuses the generic light admin template the portal shipped with.

OWN-WORLD: Near-black console ground (#08090A, surfaces #111316 / #16181C / #1C1F24) with faint top-lit rims instead of hard borders; warm paper variant (#F1F0EC, white surfaces) when the system asks for light. One accent, lime #D8FF3E (olive #4E6B00 as text on paper), on primary buttons, focus, selection and the active nav item. Verdict colours green, amber, red and slate as soft fills with readable ink. Anton caps only for the brand wordmark and the verdict word; page titles in IBM Plex Sans Condensed 700 (as the reference's `.page-title`), which also carries everything spoken; Iosevka for codes and serials only, never for placeholder words. Pill buttons, 16 px inset fields, 22 px cards. Lime squircle mark with the half-hatched pack.

STORY: Staff and consumers do exactly what they did before; the screens now carry the project's identity and the verdict reads at a glance.

FIRST VIEWPORT: Staff: the existing left rail (mark, organisation, nav pills, account, theme) beside the work area; page title in Plex Condensed 700; content in rimmed cards. Consumer: sticky blurred top bar with mark and links; one column; the check form in a card; the verdict as a tinted card with a coloured chip and the verdict word in Anton.

FORM: seed: none (pinned) — "use this repo, to for ui designing of our project... do not chage the features or don't make any logical changes in this code, just change the ui as the repo hve". Confirmed by the user: lime everywhere, keep the sidebar, follow the system theme.

SIGNATURE: the reference's hatching (45° stripes) as the texture of the unknown: loading skeletons and the "Cannot check" state.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
