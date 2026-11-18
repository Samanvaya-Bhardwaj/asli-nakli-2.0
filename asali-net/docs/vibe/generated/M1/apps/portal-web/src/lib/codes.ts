// Pack code rules for instant feedback in the browser: normalise, parse, check characters.
// Port of packages/asali_codes (normalise.py, parse.py, checks.py, dates.py). Correction stays server-side.
// Both implementations are tested against docs/plan/test-vectors/codes.json.

export const ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";
export const SERIAL_LENGTH = 11;
export const GS = "\x1d";
const INDEX = new Map([...ALPHABET].map((c, i) => [c, i]));
const ALIASES: Record<string, string> = { O: "0", I: "1", L: "1" };
const N = 32;

export type FieldStatus = "valid" | "invalid_check" | "invalid_char" | "invalid_value" | "wrong_length" | "missing";
export type Grammar = "digital_link" | "element_string" | "label_line" | "bare_serial" | "bare_gtin" | "unknown";
export interface Reading {
  raw: string;
  grammar: Grammar;
  gtin: string | null;
  serial: string | null;
  lot: string | null;
  expiry: string | null; // ISO date
  status: { gtin: FieldStatus; serial: FieldStatus; lot: FieldStatus; expiry: FieldStatus };
  notes: string[];
}

export function gs1CheckDigit(body13: string): string {
  if (!/^\d{13}$/.test(body13)) throw new Error(`GTIN body must be 13 digits, got ${body13}`);
  let total = 0;
  [...body13].reverse().forEach((d, i) => (total += Number(d) * (i % 2 === 0 ? 3 : 1)));
  return String((10 - (total % 10)) % 10);
}

export const gtinIsValid = (g: string): boolean => /^\d{14}$/.test(g) && gs1CheckDigit(g.slice(0, 13)) === g[13];

function luhnSum(s: string, firstFactor: 1 | 2): number {
  let factor = firstFactor;
  let total = 0;
  for (const ch of [...s].reverse()) {
    const v = INDEX.get(ch);
    if (v === undefined) throw new Error(`${ch} is not in the serial alphabet`);
    const addend = factor * v;
    factor = factor === 2 ? 1 : 2;
    total += Math.floor(addend / N) + (addend % N);
  }
  return total;
}

export const luhn32CheckChar = (payload: string): string => ALPHABET[(N - (luhnSum(payload, 2) % N)) % N];

export function luhn32IsValid(full: string): boolean {
  if (!full || [...full].some((c) => !INDEX.has(c))) return false;
  return luhnSum(full, 1) % N === 0;
}

export const formatSerial = (s: string): string => s.match(/.{1,4}/g)?.join("-") ?? s;

const SYMBOLOGY = /^\](?:Q1|Q3|d2|C1)/;
export function normaliseRaw(raw: string): string {
  const text = raw.normalize("NFKC").trim();
  const kept = [...text].filter((ch) => ch === GS || !/\p{C}/u.test(ch)).join("");
  return kept.replace(SYMBOLOGY, "").trim();
}

const SEPARATORS = new Set([..." -‐‑‒–—―−_.\t"]);
export function normaliseSerial(text: string): { serial: string; notes: string[] } {
  const out: string[] = [];
  const notes: string[] = [];
  for (const ch of text.toUpperCase()) {
    if (SEPARATORS.has(ch)) continue;
    if (ch in ALIASES) {
      notes.push(`read ${ch} as ${ALIASES[ch]} at position ${out.length + 1}`);
      out.push(ALIASES[ch]);
    } else {
      if (!INDEX.has(ch)) notes.push(`'${ch}' at position ${out.length + 1} is not in the code alphabet`);
      out.push(ch);
    }
  }
  return { serial: out.join(""), notes };
}

// ---- dates ----
const MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
const pad = (n: number) => String(n).padStart(2, "0");
const year = (t: string) => (Number(t) < 100 ? 2000 + Number(t) : Number(t));
function safeDate(y: number, m: number, d: number): string | null {
  const dt = new Date(Date.UTC(y, m - 1, d));
  return dt.getUTCFullYear() === y && dt.getUTCMonth() === m - 1 && dt.getUTCDate() === d ? `${y}-${pad(m)}-${pad(d)}` : null;
}
function lastDay(y: number, m: number): string | null {
  if (m < 1 || m > 12 || y < 2000 || y > 2099) return null;
  return safeDate(y, m, new Date(Date.UTC(y, m, 0)).getUTCDate());
}
export function gs1Yymmdd(t: string): string | null {
  if (!/^\d{6}$/.test(t)) return null;
  const [y, m, d] = [2000 + Number(t.slice(0, 2)), Number(t.slice(2, 4)), Number(t.slice(4))];
  return d === 0 ? lastDay(y, m) : safeDate(y, m, d);
}
export function printedExpiry(text: string): string | null {
  const t = text.trim().toUpperCase().replace(/\.$/, "");
  let m: RegExpMatchArray | null;
  if ((m = t.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})$/))) return safeDate(year(m[3]), Number(m[2]), Number(m[1]));
  if ((m = t.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/))) return safeDate(Number(m[1]), Number(m[2]), Number(m[3]));
  if ((m = t.match(/^(\d{1,2})\s*[/.-]\s*(\d{2}|\d{4})$/))) return lastDay(year(m[2]), Number(m[1]));
  if ((m = t.match(/^(\d{4})-(\d{1,2})$/))) return lastDay(Number(m[1]), Number(m[2]));
  if ((m = t.match(/^([A-Z]{3,9})[\s.\-/']*(\d{2}|\d{4})$/))) {
    const month = MONTHS.indexOf(m[1].slice(0, 3)) + 1;
    return month ? lastDay(year(m[2]), month) : null;
  }
  return null;
}

// ---- parsing ----
type Fields = Record<string, string>;
const FIXED_AI: Record<string, number> = { "01": 14, "11": 6, "17": 6 };
const VARIABLE_AI: Record<string, number> = { "10": 20, "21": 20 };
const LABEL =
  /(?<![A-Z0-9])(GTIN|S\s?\/\s?N|S\.N\.?|SERIAL(?:\s*NO\.?)?|SN|LOT(?:\s*NO\.?)?|B\.?\s?NO\.?|BATCH(?:\s*NO\.?)?|EXPIRY|EXP\.?|USE\s+BEFORE)(?![A-Z0-9])/gi;

export function parse(raw: string): Reading {
  const text = normaliseRaw(raw);
  if (/^https?:\/\//i.test(text)) {
    const f = digitalLink(text);
    if (f) return reading(raw, "digital_link", f);
  }
  if (text.startsWith("(")) {
    const f = bracketed(text);
    if (Object.keys(f).length) return reading(raw, "element_string", f);
  }
  const compact = text.replace(/ /g, "");
  if (/^01\d{14}[0-9A-Za-z\x1d/\-.]*$/.test(compact) && compact.length > 16) {
    const f = bestAiParse(compact);
    if (f) return reading(raw, "element_string", f);
  }
  LABEL.lastIndex = 0;
  if (LABEL.test(text)) {
    const f = labelLine(text);
    if (Object.keys(f).length) return reading(raw, "label_line", f);
  }
  return bare(raw, text);
}

function digitalLink(text: string): Fields | null {
  let url: URL;
  try {
    url = new URL(text);
  } catch {
    return null;
  }
  const segs = url.pathname.split("/").filter(Boolean).map(decodeURIComponent);
  const f: Fields = {};
  for (let i = 0; i < segs.length - 1; i++) if (["01", "10", "21", "17"].includes(segs[i]) && !(segs[i] in f)) f[segs[i]] = segs[i + 1];
  for (const k of ["10", "17", "21"]) {
    const v = url.searchParams.get(k);
    if (v !== null && !(k in f)) f[k] = v;
  }
  return "01" in f ? f : null;
}

function bracketed(text: string): Fields {
  const f: Fields = {};
  for (const m of text.matchAll(/\((\d{2})\)([^(]*)/g)) f[m[1]] = m[2].replaceAll(GS, "").trim();
  return f;
}

function bestAiParse(s: string): Fields | null {
  const results: Fields[] = [];
  const isAi = (i: number) => s.slice(i, i + 2) in FIXED_AI || s.slice(i, i + 2) in VARIABLE_AI;
  const walk = (i: number, acc: Fields): void => {
    if (results.length > 64) return;
    if (i === s.length) {
      results.push(acc);
      return;
    }
    const ai = s.slice(i, i + 2);
    if (ai in acc) return;
    if (ai in FIXED_AI) {
      const n = FIXED_AI[ai];
      const value = s.slice(i + 2, i + 2 + n);
      const j = i + 2 + n;
      if (value.length === n && /^\d+$/.test(value)) walk(s[j] === GS ? j + 1 : j, { ...acc, [ai]: value });
    } else if (ai in VARIABLE_AI) {
      const start = i + 2;
      for (let end = start + 1; end <= Math.min(s.length, start + VARIABLE_AI[ai]); end++) {
        if (end === s.length || s[end] === GS || isAi(end)) walk(s[end] === GS ? end + 1 : end, { ...acc, [ai]: s.slice(start, end) });
        if (end < s.length && s[end] === GS) break;
      }
    }
  };
  walk(0, {});
  if (!results.length) return null;
  const score = (f: Fields): number =>
    (luhn32IsValid(normaliseSerial(f["21"] ?? "").serial) ? 100 : 0) + (gtinIsValid(f["01"] ?? "") ? 10 : 0) + Object.keys(f).length;
  return results.reduce((a, b) => (score(b) > score(a) ? b : a));
}

function labelLine(text: string): Fields {
  const matches = [...text.matchAll(LABEL)];
  const f: Fields = {};
  matches.forEach((m, k) => {
    const end = k + 1 < matches.length ? matches[k + 1].index! : text.length;
    const value = text.slice(m.index! + m[0].length, end).replace(/^[\s:#\-.]+|[\s:#\-.]+$/g, "");
    const label = m[1].toUpperCase().replace(/[^A-Z]/g, "");
    if (label === "GTIN") f["01"] ??= value.replace(/\s/g, "");
    else if (label.startsWith("SN") || label.startsWith("SERIAL")) f["21"] ??= value;
    else if (/^(LOT|BNO|BATCH)/.test(label)) f["10"] ??= value.replace(/\s/g, "");
    else if (/^(EXP|USEBEFORE)/.test(label)) f["exp_text"] ??= value;
  });
  return f;
}

function bare(raw: string, text: string): Reading {
  const compact = text.replace(/[\s\-–—]/g, "");
  if (/^\d{14}$/.test(compact)) return reading(raw, "bare_gtin", { "01": compact });
  if (/^\d{13}$/.test(compact)) return reading(raw, "bare_gtin", { "01": "0" + compact });
  const looksLikeSerial = /^[0-9A-Za-z]{10,12}$/.test(compact) && !/^\d+$/.test(compact);
  if (looksLikeSerial && (compact.length === SERIAL_LENGTH || /\d/.test(compact))) return reading(raw, "bare_serial", { "21": text });
  return reading(raw, "unknown", {});
}

function reading(raw: string, grammar: Grammar, f: Fields): Reading {
  const status: Reading["status"] = { gtin: "missing", serial: "missing", lot: "missing", expiry: "missing" };
  const notes: string[] = [];
  const gtin = f["01"] || null;
  if (gtin !== null) {
    status.gtin = !/^\d+$/.test(gtin) ? "invalid_char" : gtin.length !== 14 ? "wrong_length" : gtinIsValid(gtin) ? "valid" : "invalid_check";
  }
  let serial: string | null = null;
  if (f["21"]) {
    const n = normaliseSerial(f["21"]);
    serial = n.serial;
    notes.push(...n.notes);
    if (n.notes.some((x) => x.includes("not in the code alphabet"))) status.serial = "invalid_char";
    else if (serial.length !== SERIAL_LENGTH) status.serial = "wrong_length";
    else status.serial = luhn32IsValid(serial) ? "valid" : "invalid_check";
  }
  const lot = f["10"] || null;
  if (lot !== null) status.lot = lot.length > 0 && lot.length <= 20 ? "valid" : "wrong_length";
  let expiry: string | null = null;
  if ("17" in f) {
    expiry = gs1Yymmdd(f["17"]);
    status.expiry = expiry ? "valid" : "invalid_value";
  } else if ("exp_text" in f) {
    expiry = printedExpiry(f["exp_text"]);
    status.expiry = expiry ? "valid" : "invalid_value";
  }
  return { raw, grammar, gtin, serial, lot, expiry, status, notes };
}
