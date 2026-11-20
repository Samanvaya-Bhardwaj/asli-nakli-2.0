// Runs dashboard/phase3.html's own script in Node against REAL saved responses
// (phase3/documentation/evidence/*.json), with a minimal DOM stand-in, and checks
// that every section renders without an exception. It proves the page's logic
// handles real answers; it does not show what the page looks like in a browser.
//
//   node phase3/tools/check_page_render.mjs
import fs from "fs";
import path from "path";
import vm from "vm";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Z]:)/, "$1")), "..", "..");
const html = fs.readFileSync(path.join(root, "dashboard", "phase3.html"), "utf8");
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];
const ev = (f) => JSON.parse(fs.readFileSync(path.join(root, "phase3", "documentation", "evidence", f), "utf8"));

const nodes = {};
const el = (id) => (nodes[id] ||= { id, innerHTML: "", textContent: "", value: "", className: "", type: "",
  appendChild() {}, addEventListener() {}, onclick: null });
const ctx = {
  document: { querySelector: (s) => el(s), createElement: () => el("btn" + Math.random()) },
  fetch: async (url) => ({ ok: true, json: async () => (url.includes("nodes") ? ev("nodes.json") : null) }),
  console, setTimeout, String, JSON, Object, Array, Math,
};
vm.createContext(ctx);
vm.runInContext(script, ctx);
await new Promise((r) => setTimeout(r, 50));            // deployment() resolves

let failures = 0;
const dep = el("#deployment").innerHTML;
console.log(`deployment panel: ${dep.includes("Deployment:") ? "rendered" : "MISSING"} (${dep.length} chars)`);
if (!dep.includes("Deployment:")) failures++;
for (const f of ["scenario_1.json", "scenario_2.json", "scenario_3.json"]) {
  const res = ev(f);
  try {
    vm.runInContext("render", ctx)(res);
  } catch (e) {
    console.log(`${f}: EXCEPTION ${e.message}`); failures++; continue;
  }
  const out = el("#out").innerHTML;
  const sections = (out.match(/class="step"/g) || []).length;
  const docs = (out.match(/class="doc"/g) || []).length;
  const ok = sections === 7 && docs === res.integrated.E_documents.length && out.includes(res.question.slice(0, 20));
  if (!ok) failures++;
  console.log(`${f}: ${sections}/7 sections, ${docs}/${res.integrated.E_documents.length} documents, ` +
              `${out.length} chars of HTML - ${ok ? "ok" : "PROBLEM"}`);
}
console.log(failures ? `FAILED (${failures})` : "OK");
process.exit(failures ? 1 : 0);
