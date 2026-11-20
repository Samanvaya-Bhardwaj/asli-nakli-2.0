"""
doc_store.py
------------
One source's unstructured documents: ingestion, index and context-aware search.
It runs inside that source's own service, over that source's own document folder
(ASALI_DOCS_DIR, default data/documents/<db>). Documents are files; nothing here
writes them into a database table.

INGESTION (per document)
  1. extract text      .md / .txt (front-matter header + body), .html (tags stripped, <title>/<meta>)
  2. clean/normalise   Unicode NFKC, markup removed, whitespace collapsed, header date -> ISO
  3. chunk             by section/paragraph; long sections in ~120-word windows (30 overlap)
  4. metadata          doc_id, title, type, source, date, owner, file, format
  5. entities          medicine codes (also damaged ones: canonical form + scanner-look-alike
                       key), batch numbers, manufacturer / distributor / vendor ids, dispatch
                       and complaint refs; company names resolved to ids through the OWNER's
                       own database when it has them (a manufacturer's documents name the
                       manufacturer; DB3 knows its id)
  6. index             BM25 over chunks + an entity index

SEARCH (a context-aware request built by the coordinator from the SCORE context)
  lexical   weighted BM25: the question's words (weight 1) and the context terms (their
            aggregated scores); saturated to 0..1 by 1 - exp(-bm25 / 6), so scores from
            different sources are comparable
  entity    matched identifiers: medicine code exact 1.0, look-alike 0.85, batch 0.8,
            dispatch ref 0.6, manufacturer / distributor 0.35, vendor 0.25, company
            name 0.3 - each times the request's weight for that entity (anchors 1.0,
            context-derived 0.5); capped at 2
  gate      a document needs an entity match, or at least two INFORMATIVE query terms
            (idf >= 1.5) and lexical >= 0.3: sharing a common word is not enough
  conflict  the question names medicines, the document names others and none of them:
            x 0.25 (a sibling batch one character away is a different medicine)
  type      x 1.25 when the document type suits the question's intent
  recency   x (1 + 0.1 * years since 2025-01-01, at most 1.5 years)
  score     (0.4 * lexical + 0.6 * entity / 2) * type * recency * conflict; returned if >= 0.15
"""

from __future__ import annotations
import html
import math
import os
import re
import sqlite3
import threading
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional

from integration.federation.query_parser import STOPWORDS
from integration.uncertainty import paths
from integration.uncertainty.context import fold
from integration.uncertainty.standardize import canonical_code, to_date

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
K1, B = 1.5, 0.75
LEX_TAU = 6.0
IDF_MIN = 1.5
MIN_SCORE = 0.15      # below this a document is not returned (in practice: penalised as about another medicine)
CHUNK_WORDS, CHUNK_OVERLAP = 120, 30
ENTITY_WEIGHT = {"item_code": 1.0, "item_code_lookalike": 0.85, "batch_number": 0.8, "dispatch_ref": 0.6,
                 "manufacturer_id": 0.35, "distributor_id": 0.35, "vendor_id": 0.25, "name": 0.3}
INTENT_TYPES = {
    "cold_chain": {"distributor_shipment_note", "cold_chain_incident_report", "batch_inspection_report",
                   "product_safety_document"},
    "recall": {"recall_notice", "regulatory_investigation_report", "nsq_bulletin", "manufacturer_quality_report"},
    "complaint": {"consumer_complaint", "pharmacy_incident_report", "regulatory_investigation_report"},
    "lab": {"regulatory_investigation_report", "batch_inspection_report"},
    "authenticity": {"regulatory_investigation_report", "pharmacy_incident_report", "consumer_complaint",
                     "nsq_bulletin", "recall_notice"},
    "manufacturing": {"batch_inspection_report", "manufacturer_quality_report"},
    "safety": {"product_safety_document", "recall_notice", "batch_inspection_report", "consumer_complaint",
               "regulatory_investigation_report"},
    "stock": {"pharmacy_incident_report"}, "sales": {"pharmacy_incident_report"},
    "shipment": {"distributor_shipment_note", "cold_chain_incident_report"},
}
# Who wrote it decides what it can establish (see the integrated response)
EVIDENCE = {
    "recall_notice": "official regulatory notice", "nsq_bulletin": "official regulatory notice",
    "regulatory_investigation_report": "regulatory finding",
    "manufacturer_quality_report": "manufacturer's own record", "batch_inspection_report": "manufacturer's own record",
    "product_safety_document": "reference information",
    "distributor_shipment_note": "distributor's operational record",
    "cold_chain_incident_report": "distributor's operational record",
    "pharmacy_incident_report": "pharmacy's report (not verified)",
    "consumer_complaint": "consumer allegation (not verified)",
}

CODE_RE = re.compile(r"\bmed[\s_\-.]+[a-z0-9]{3,8}[\s_\-.]+[a-z0-9]{2,6}\b", re.I)
ID_RES = {
    "batch_number": re.compile(r"\b(BATCH-[A-Z]\d{3,4}|[A-Z]{3}\d{5})\b"),
    "dispatch_ref": re.compile(r"\b(DBATCH-[A-Z]?\d{3,5})\b"),
    "manufacturer_id": re.compile(r"\b(MFG-\d{3})\b"),
    "distributor_id": re.compile(r"\b(DIST-\d{3})\b"),
    "vendor_id": re.compile(r"\b(VND-\d{3})\b"),
    "complaint_ref": re.compile(r"\b(MCA-\d{4}-[A-Z]?\d{3,5})\b"),
}
WORD = re.compile(r"[a-z][a-z0-9+]{2,}")


def docs_dir(db_id: str) -> str:
    return os.environ.get("ASALI_DOCS_DIR") or os.path.join(BASE_DIR, "data", "documents", db_id)


# -- 1-2. text extraction and cleaning ----------------------------------------------------------

class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__()
        self.meta, self.parts, self._in_title = {}, [], False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "meta" and a.get("name"):
            self.meta[a["name"]] = a.get("content", "")
        if tag == "title":
            self._in_title = True
        if tag in ("p", "h1", "h2", "h3", "li", "br", "div"):
            self.parts.append("\n\n")

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.meta.setdefault("title", data.strip())
        else:
            self.parts.append(data)


def extract(path: str) -> (Dict[str, str], str):
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()
    if path.lower().endswith((".html", ".htm")):
        p = _HTMLText()
        p.feed(raw)
        return p.meta, "".join(p.parts)
    meta, body = {}, raw
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = m.group(2)
    return meta, body


def clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(text))
    text = re.sub(r"^\s{0,3}#{1,6}\s*", "", text, flags=re.M)        # markdown headings
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.M)               # bullets
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


# Company-name and web fragments: rare in some collections, so they look informative,
# but sharing 'Ltd' with a document says nothing about what it is about
GENERIC = {"ltd", "limited", "pvt", "private", "inc", "llp", "www", "com", "org", "http", "https"}


def tokens(text: str) -> List[str]:
    return [t for t in WORD.findall(text.lower()) if t not in STOPWORDS and t not in GENERIC]


# -- 3. chunking -----------------------------------------------------------------------------

def chunk(text: str) -> List[str]:
    out, buf = [], []
    for para in [p.strip() for p in text.split("\n\n") if p.strip()]:
        words = para.split()
        if len(words) > CHUNK_WORDS:
            if buf:
                out.append(" ".join(buf)); buf = []
            for i in range(0, len(words), CHUNK_WORDS - CHUNK_OVERLAP):
                out.append(" ".join(words[i:i + CHUNK_WORDS]))
                if i + CHUNK_WORDS >= len(words):
                    break
        elif len(buf) + len(words) > CHUNK_WORDS:
            out.append(" ".join(buf)); buf = list(words)
        else:
            buf.extend(words)
    if buf:
        out.append(" ".join(buf))
    return out or [text]


# -- 5. entities -----------------------------------------------------------------------------

def owner_dictionary(db_id: str) -> Dict[str, tuple]:
    """Names the owner's own database can resolve to ids (lowercased name -> (kind, id))."""
    q = {"db3": ("SELECT company_name, manufacturer_id FROM manufacturers", "manufacturer_id"),
         "db2": ("SELECT company_name, distributor_id FROM distributors", "distributor_id"),
         "db1": ("SELECT vendor_name, vendor_id FROM vendors", "vendor_id")}.get(db_id)
    path = paths.db_path(db_id) if db_id in ("db1", "db2", "db3", "db4") else None
    if not q or not path or not os.path.exists(path):
        return {}
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        out = {}
        for name, ident in c.execute(q[0]):
            if name and name.lower() not in out:
                out[name.lower()] = (q[1], ident)
        return out
    except sqlite3.Error:
        return {}
    finally:
        c.close()


def entities(text: str, dictionary: Dict[str, tuple]) -> Dict[str, List[Dict[str, str]]]:
    out: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    seen = set()
    for m in CODE_RE.finditer(text):
        raw = m.group(0)
        canon = canonical_code(raw)
        if ("item_code", canon) not in seen:
            seen.add(("item_code", canon))
            out["item_code"].append({"value": canon, "raw": raw, "fold": fold(canon)})
    for kind, rx in ID_RES.items():
        for m in rx.finditer(text):
            v = m.group(1).upper()
            if (kind, v) not in seen:
                seen.add((kind, v))
                out[kind].append({"value": v, "raw": m.group(0)})
    low = text.lower()
    for name, (kind, ident) in dictionary.items():
        if name in low and (kind, ident) not in seen:
            seen.add((kind, ident))
            out[kind].append({"value": ident, "raw": name, "via": "owner's name dictionary"})
    return dict(out)


# -- the store -----------------------------------------------------------------------------------

@dataclass
class Chunk:
    doc_id: str
    n: int
    text: str
    tf: Counter
    length: int


@dataclass
class Document:
    doc_id: str
    title: str
    type: str
    source: str
    date_raw: str
    date: Optional[str]
    owner: str
    file: str
    fmt: str
    entities: Dict[str, List[Dict[str, str]]]
    chunks: List[Chunk] = field(default_factory=list)

    def metadata(self) -> Dict[str, Any]:
        ids = lambda k: [e["value"] for e in self.entities.get(k, [])]
        return {"doc_id": self.doc_id, "title": self.title, "type": self.type, "source": self.source,
                "date": self.date, "date_as_written": self.date_raw, "owner_database": self.owner,
                "file": self.file, "format": self.fmt, "chunks": len(self.chunks),
                "medicine_ids": ids("item_code"), "batch_ids": ids("batch_number"),
                "manufacturer_ids": ids("manufacturer_id"), "distributor_ids": ids("distributor_id"),
                "vendor_ids": ids("vendor_id"), "dispatch_refs": ids("dispatch_ref"),
                "complaint_refs": ids("complaint_ref")}


class DocStore:
    def __init__(self, db_id: str):
        self.db_id = db_id
        self._lock = threading.Lock()
        self._version = None
        self.docs: Dict[str, Document] = {}
        self.chunks: List[Chunk] = []
        self.df: Counter = Counter()
        self.avg_len = 1.0

    def _files(self) -> List[str]:
        d = docs_dir(self.db_id)
        if not os.path.isdir(d):
            return []
        return sorted(os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith((".md", ".txt", ".html", ".htm")))

    def version(self) -> tuple:
        fs = self._files()
        return (len(fs), max((os.stat(f).st_mtime_ns for f in fs), default=0))

    def ensure(self) -> "DocStore":
        with self._lock:
            v = self.version()
            if v != self._version:
                self._ingest()
                self._version = v
        return self

    def _ingest(self):
        dictionary = owner_dictionary(self.db_id)
        self.docs, self.chunks, self.df = {}, [], Counter()
        for path in self._files():
            meta, body = extract(path)
            text = clean(body)
            doc_id = meta.get("doc_id") or os.path.splitext(os.path.basename(path))[0]
            when = to_date(meta.get("date"))
            doc = Document(doc_id, meta.get("title") or doc_id, meta.get("type") or "unclassified",
                           meta.get("source") or "unknown", meta.get("date", ""),
                           when.date().isoformat() if when else None, self.db_id,
                           os.path.basename(path), os.path.splitext(path)[1].lstrip("."),
                           entities(text, dictionary))
            for i, c in enumerate(chunk(f"{doc.title}\n\n{text}")):
                toks = tokens(c)
                ch = Chunk(doc_id, i, c, Counter(toks), len(toks) or 1)
                doc.chunks.append(ch)
                self.chunks.append(ch)
                self.df.update(set(toks))
            self.docs[doc_id] = doc
        self.avg_len = sum(c.length for c in self.chunks) / max(1, len(self.chunks))

    def idf(self, t: str) -> float:
        n, df = len(self.chunks), self.df.get(t, 0)
        return math.log(1 + (n - df + 0.5) / (df + 0.5))

    def bm25(self, ch: Chunk, weighted: Dict[str, float]) -> (float, List[str]):
        s, hit = 0.0, []
        for t, w in weighted.items():
            f = ch.tf.get(t, 0)
            if not f:
                continue
            s += w * self.idf(t) * f * (K1 + 1) / (f + K1 * (1 - B + B * ch.length / self.avg_len))
            hit.append(t)
        return s, hit

    def stats(self) -> Dict[str, Any]:
        self.ensure()
        types = Counter(d.type for d in self.docs.values())
        return {"database": self.db_id, "folder": docs_dir(self.db_id), "documents": len(self.docs),
                "chunks": len(self.chunks), "vocabulary": len(self.df), "types": dict(types),
                "formats": dict(Counter(d.fmt for d in self.docs.values())),
                "documents_with_medicine_ids": sum(1 for d in self.docs.values() if d.entities.get("item_code"))}

    # -- search ---------------------------------------------------------------------------------

    def search(self, req: Dict[str, Any]) -> Dict[str, Any]:
        self.ensure()
        weighted: Dict[str, float] = defaultdict(float)
        # codes are matched as entities, not words: 'MED-NAKALI-001' must not turn into the words
        # 'med' and 'nakali', which every other NAKALI document also contains
        for t in tokens(CODE_RE.sub(" ", req.get("query_text", ""))):
            weighted[t] = max(weighted[t], 1.0)
        for item in req.get("context_terms", []):
            for t in tokens(str(item.get("term", ""))):
                weighted[t] = max(weighted[t], float(item.get("weight", 0.5)))
        weighted = dict(weighted)
        informative = {t for t in weighted if self.idf(t) >= IDF_MIN}
        wanted = req.get("entities", [])
        # the medicines / batches this question is about: the question's own or found through FK joins
        query_codes = [e for e in wanted if e["kind"] in ("item_code", "batch_number") and float(e.get("weight", 0)) >= 0.5]
        names = [n for n in req.get("names", []) if len(n) >= 4]
        preferred = set().union(*[INTENT_TYPES.get(i, set()) for i in req.get("intents", [])]) if req.get("intents") else set()
        results = []
        for doc in self.docs.values():
            lex_scores = sorted(((self.bm25(c, weighted), c) for c in doc.chunks), key=lambda x: -x[0][0])
            (best, hit), best_chunk = lex_scores[0]
            raw = best + 0.2 * sum(s for (s, _h), _c in lex_scores[1:2])
            lexical = 1 - math.exp(-raw / LEX_TAU)
            hits = sorted(set(hit))
            # entities
            matched, ent = [], 0.0
            have = doc.entities
            for e in wanted:
                kind, val, w = e["kind"], e["value"], float(e.get("weight", 1.0))
                if kind == "item_code":
                    for d in have.get("item_code", []):
                        if d["value"] == val:
                            matched.append({"kind": "item_code", "value": val, "as_written": d["raw"], "match": "exact"})
                            ent += ENTITY_WEIGHT["item_code"] * w
                            break
                        if d["fold"] == fold(val):
                            matched.append({"kind": "item_code", "value": val, "as_written": d["raw"],
                                            "match": "scanner look-alike"})
                            ent += ENTITY_WEIGHT["item_code_lookalike"] * w
                            break
                elif any(d["value"] == str(val).upper() for d in have.get(kind, [])):
                    matched.append({"kind": kind, "value": val, "match": "exact"})
                    ent += ENTITY_WEIGHT.get(kind, 0.3) * w
            low = " ".join(c.text for c in doc.chunks).lower()
            for n in names:
                if n.lower() in low and not any(m.get("as_written", "").lower() == n.lower() for m in matched):
                    matched.append({"kind": "name", "value": n, "match": "name in text"})
                    ent += ENTITY_WEIGHT["name"]
            ent = min(ent, 2.0)
            informative_hits = [t for t in hits if t in informative]
            if ent == 0 and not (len(informative_hits) >= 2 and lexical >= 0.3):
                continue
            why, factor = [], 1.0
            doc_codes = {d["value"] for d in have.get("item_code", [])} | {d["value"] for d in have.get("batch_number", [])}
            if query_codes and doc_codes and not any(m["kind"] in ("item_code", "batch_number") for m in matched):
                factor *= 0.25
                why.append(f"penalised: about a different medicine ({', '.join(sorted(doc_codes)[:3])})")
            type_boost = 1.25 if doc.type in preferred else 1.0
            years = 0.0
            if doc.date:
                d0 = date.fromisoformat(doc.date)
                years = max(0.0, min(1.5, (d0 - date(2025, 1, 1)).days / 365.0))
            recency = 1 + 0.1 * years
            score = (0.4 * lexical + 0.6 * ent / 2.0) * type_boost * recency * factor
            for m in matched:
                if m["kind"] == "item_code":
                    why.insert(0, f"mentions medicine {m['value']}" + ("" if m["match"] == "exact" else
                                                                        f" (written '{m['as_written']}', a scanner look-alike)"))
                elif m["kind"] == "name":
                    why.append(f"names {m['value']}")
                else:
                    why.append(f"mentions {m['kind'].replace('_', ' ')} {m['value']}")
            if informative_hits:
                why.append("matches context terms: " + ", ".join(informative_hits[:6]))
            if type_boost > 1:
                why.append(f"a {doc.type.replace('_', ' ')} suits a question about {', '.join(req.get('intents', []))}")
            if score < MIN_SCORE:
                continue
            marks = sorted(set(hits) | {m["as_written"] for m in matched if m.get("as_written")} |
                           {m["value"] for m in matched}, key=len, reverse=True)
            snippet = best_chunk.text
            if marks:   # one pass, longest first, whole words only: no nested markers
                snippet = re.sub(r"(?i)(?<![A-Za-z0-9])(" + "|".join(map(re.escape, marks)) + r")(?![A-Za-z0-9])",
                                 r"**\1**", snippet)
            results.append({**doc.metadata(), "score": round(score, 4),
                            "score_parts": {"lexical": round(lexical, 3), "entity": round(ent, 3), "type": type_boost,
                                            "recency": round(recency, 3), "conflict": factor},
                            "matched_entities": matched, "matched_terms": hits, "why_retrieved": why,
                            "evidence_status": EVIDENCE.get(doc.type, "unclassified document"),
                            "best_chunk": {"n": best_chunk.n, "of": len(doc.chunks), "text": snippet[:700]}})
        results.sort(key=lambda r: (-r["score"], r["doc_id"]))
        top = int(req.get("top_k", 8))
        return {"database": self.db_id, "documents_searched": len(self.docs), "chunks_searched": len(self.chunks),
                "passed_relevance_gate": len(results), "weighted_query_terms": len(weighted),
                "results": results[:top]}


_STORES: Dict[str, DocStore] = {}


def store(db_id: str) -> DocStore:
    if db_id not in _STORES:
        _STORES[db_id] = DocStore(db_id)
    return _STORES[db_id].ensure()


if __name__ == "__main__":
    import json
    import sys
    for d in (sys.argv[1:] or ["db1", "db2", "db3", "db4"]):
        print(json.dumps(store(d).stats(), indent=1))
