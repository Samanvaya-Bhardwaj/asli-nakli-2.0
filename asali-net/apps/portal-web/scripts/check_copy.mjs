// Scans the words the interface shows for banned words, exclamation marks, em dashes, emoji and Title Case buttons
// (DESIGN.md 10.2). The banned-word list is read from the backend's list, so both sides use one list.
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'

const root = new URL('../src/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
const py = readFileSync(new URL('../../../services/node/asali_node/verify/banned_words.py', import.meta.url), 'utf8')
const start = py.indexOf('BANNED_WORDS = (')
const block = py.slice(start, py.indexOf('\n)', start))
const banned = [...block.matchAll(/"([\w-]+)"/g)].map((m) => m[1])
if (banned.length < 10) throw new Error('could not read the banned word list')
const bannedRe = new RegExp(`\\b(${banned.join('|')})\\w*`, 'i')
const PROPER = new Set(['Asali', 'Sharma', 'Medicos', 'Apna', 'Chemist', 'Namma', 'Pharmacy', 'North', 'Star'])

function* files(dir) {
  for (const f of readdirSync(dir)) {
    const p = join(dir, f)
    if (statSync(p).isDirectory()) yield* files(p)
    else if (/\.(tsx?|json)$/.test(f) && !/\.test\.tsx?$/.test(f) && !/receipt\.(hi|mr|kn)\.json$/.test(f)) yield p
  }
}

// What a person can read: string literals and JSX text, not code.
function words(source) {
  const out = []
  for (const m of source.matchAll(/(["'`])((?:\\.|(?!\1)[^\\\n])*)\1/g)) if (/[A-Za-z]{3}/.test(m[2]) && /\s/.test(m[2])) out.push(m[2])
  for (const m of source.matchAll(/>([^<>{}\n][^<>{}]*)</g)) if (/[A-Za-z]{3}/.test(m[1])) out.push(m[1])
  return out
}

let found = 0
for (const file of files(root)) {
  const src = readFileSync(file, 'utf8')
  const shown = file.replace(root, 'src/')
  for (const w of words(src)) {
    const problems = []
    if (bannedRe.test(w)) problems.push(`banned word "${bannedRe.exec(w)[0]}"`)
    if (/[A-Za-z0-9.)]!(?=\s|$)/.test(w) && /\s/.test(w)) problems.push('exclamation mark')
    if (w.includes('—')) problems.push('em dash')
    if (/\p{Extended_Pictographic}/u.test(w)) problems.push('emoji')
    if (problems.length) { console.log(`${shown}: "${w.trim().slice(0, 70)}" -> ${problems.join(', ')}`); found++ }
  }
  for (const m of src.matchAll(/<Button[^>]*>\s*([A-Z][a-z]+(?: [A-Z][a-z]+)+)\s*<\/Button>/g)) {
    if (!m[1].split(' ').slice(1).every((x) => PROPER.has(x))) { console.log(`${shown}: Title Case button "${m[1]}"`); found++ }
  }
}
console.log(found === 0 ? 'Copy OK: no banned words, exclamation marks, em dashes, emoji or Title Case buttons' : `${found} finding(s)`)
process.exit(found === 0 ? 0 : 1)
