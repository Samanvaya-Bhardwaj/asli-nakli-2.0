// Checks the contrast of every text and background pair in the token file, in both themes (DESIGN.md 3.1).
// Body text needs 4.5:1; UI parts (solid status colours, the accent) need 3:1.
import { readFileSync } from 'node:fs'

const css = readFileSync(new URL('../src/styles/tokens.css', import.meta.url), 'utf8')

function block(selector) {
  const start = css.indexOf(selector)
  const open = css.indexOf('{', start)
  let depth = 0
  for (let i = open; i < css.length; i++) {
    if (css[i] === '{') depth++
    if (css[i] === '}' && --depth === 0) return css.slice(open + 1, i)
  }
  return ''
}
const vars = (text) => Object.fromEntries([...text.matchAll(/--([\w-]+):\s*(#[0-9a-fA-F]{6})/g)].map((m) => [m[1], m[2]]))

const light = vars(block(':root {'))
const dark = { ...light, ...vars(block(":root[data-theme='dark']")) }

function lum(hex) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4))
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
}
const ratio = (a, b) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p)
  return (x + 0.05) / (y + 0.05)
}

const TEXT = 4.5
const UI = 3
const pairs = (t) => [
  ['text on bg', t.text, t.bg, TEXT], ['text on surface', t.text, t.surface, TEXT], ['text on sunken', t.text, t.sunken, TEXT],
  ['muted on bg', t['text-muted'], t.bg, TEXT], ['muted on surface', t['text-muted'], t.surface, TEXT],
  ['meta on bg', t['text-meta'], t.bg, TEXT], ['meta on surface', t['text-meta'], t.surface, TEXT], ['meta on sunken', t['text-meta'], t.sunken, TEXT],
  ...['ok', 'warn', 'bad', 'unknown'].flatMap((s) => [
    [`${s} text on its tint`, t[`${s}-fg`], t[`${s}-bg`], TEXT],
    [`${s} solid on surface (icons)`, t[`${s}-solid`], t.surface, UI],
    [`${s} solid on bg (icons)`, t[`${s}-solid`], t.bg, UI],
  ]),
  // One accent in every portal: lime as a fill, accent-ink where the accent is text (olive on paper).
  ['accent-ink on surface (links, active nav)', t['accent-ink'], t.surface, TEXT],
  ['accent-ink on bg', t['accent-ink'], t.bg, TEXT],
  ['accent-ink on sunken (active nav)', t['accent-ink'], t.sunken, TEXT],
  ['on-accent on accent (button)', t['on-accent'], t.accent, TEXT],
  ['on-accent on accent hover (button)', t['on-accent'], t['accent-hover'], TEXT],
  ['muted on sunken', t['text-muted'], t.sunken, TEXT],
  ['text on inset (fields)', t.text, t.inset, TEXT],
  ['meta on inset (placeholders)', t['text-meta'], t.inset, TEXT],
  ...['ok', 'warn', 'bad', 'unknown'].map((s) => [`icon on ${s} chip`, t[`on-${s}`], t[`${s}-solid`], UI]),
  ['border strong on surface (control edge)', t['border-strong'], t.surface, 1.5],
]

let failed = 0
for (const [name, theme] of [['light', light], ['dark', dark]]) {
  for (const [label, fg, bg, min] of pairs(theme)) {
    if (!fg || !bg) { console.log(`MISSING ${name}: ${label}`); failed++; continue }
    const r = ratio(fg, bg)
    if (r < min) { console.log(`FAIL ${name}: ${label} ${r.toFixed(2)}:1 (needs ${min}:1)`); failed++ }
  }
}
console.log(failed === 0 ? `Contrast OK: ${pairs(light).length} pairs in each of 2 themes` : `${failed} pair(s) fail`)
process.exit(failed === 0 ? 0 : 1)
