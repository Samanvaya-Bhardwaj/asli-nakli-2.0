"""
query_parser.py
---------------
Understanding a natural-language question well enough to route it.

Rule-based and standard-library only, like the rest of the project, and every
decision it makes is listed in `explanation` so the plan can be audited. It finds:

  identifiers  medicine codes (also damaged ones: 'med asal1 oo9'), batch numbers,
               vendor / distributor / manufacturer ids
  intents      what is being asked: authenticity, cold chain, recall, complaints,
               lab results, stock, sales, shipments, manufacturing
  terms        the remaining content words ('Novamox', 'Mumbai'), passed to every
               relevant database, which matches them against its OWN columns: the
               coordinator holds no product, pharmacy or city list of its own.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, List

from integration.uncertainty.standardize import canonical_code

INTENT_WORDS: Dict[str, List[str]] = {
    "authenticity": ["genuine", "fake", "counterfeit", "authentic", "verify", "real", "asali", "nakali",
                     "safe", "legit", "spurious"],
    "cold_chain": ["cold chain", "cold-chain", "temperature", "refrigerat", "excursion", "storage", "frozen"],
    "recall": ["recall", "withdrawn", "banned", "blacklist", "ban "],
    "complaint": ["complaint", "grievance", "reported", "adverse", "side effect"],
    "lab": ["lab ", "laboratory", "tested", "assay", "test result"],
    "stock": ["stock", "inventory", "in stock", "received", "available"],
    "sales": ["sold", "sale", "sales", "checkout", "purchased", "dispensed", "bought"],
    "shipment": ["ship", "dispatch", "distributor", "delivered", "delivery", "warehouse", "logistics", "transport"],
    "manufacturing": ["manufactur", "produced", "production", "plant", "factory", "quality certificate",
                      "release certificate", "qc", "gmp"],
}

STOPWORDS = set("""a an the of for in on at to from by with and or is are was were be been it its this that these
those what which who whom whose where when why how did does do has have had any all some there their them
about into over under than then also can could should would will shall may might me my we our you your i
show tell find list give get please whether if not no yes medicine medicines pack packs drug drugs item items
product products code codes batch number via between same anything everything known send sent got
went came""".split())

# the separator after MED is required, or 'medicine in' would read as a code
CODE_RE = re.compile(r"\bmed[\s_\-.]+[a-z0-9]{3,8}[\s_\-.]+[a-z0-9]{2,6}\b", re.I)
BATCH_RE = re.compile(r"\bbatch[\s\-#:]*([a-z]{1,4}-?[a-z]?\d{3,6})\b", re.I)
ID_RES = {
    "vendor_id": (re.compile(r"\bvnd[\s\-_]?0*(\d{1,4})\b", re.I), "VND-{:03d}"),
    "distributor_id": (re.compile(r"\bdist[\s\-_]?0*(\d{1,4})\b", re.I), "DIST-{:03d}"),
    "manufacturer_id": (re.compile(r"\bmfg[\s\-_]?0*(\d{1,4})\b", re.I), "MFG-{:03d}"),
}


@dataclass
class ParsedQuery:
    text: str
    item_codes: List[str] = field(default_factory=list)       # as typed, tidied (canonical_code)
    batch_numbers: List[str] = field(default_factory=list)
    vendor_ids: List[str] = field(default_factory=list)
    distributor_ids: List[str] = field(default_factory=list)
    manufacturer_ids: List[str] = field(default_factory=list)
    intents: List[str] = field(default_factory=list)
    terms: List[str] = field(default_factory=list)
    explanation: List[str] = field(default_factory=list)
    # the query's own words and intent phrases ('cold chain', 'recall'), kept whole: each
    # database uses them to judge which context is relevant (score_context.py)
    keywords: List[str] = field(default_factory=list)

    def concepts(self) -> Dict[str, List[str]]:
        return {k: v for k, v in {"item_code": self.item_codes, "batch_number": self.batch_numbers,
                                  "vendor_id": self.vendor_ids, "distributor_id": self.distributor_ids,
                                  "manufacturer_id": self.manufacturer_ids}.items() if v}


def parse(text: str) -> ParsedQuery:
    q = ParsedQuery(text=text)
    rest = f" {text} "

    for m in CODE_RE.finditer(text):
        code = canonical_code(m.group(0))
        if code not in q.item_codes:
            q.item_codes.append(code)
            q.explanation.append(f"medicine code {m.group(0).strip()!r} -> {code}"
                                 + ("" if m.group(0).strip().upper() == code else " (tidied; each database "
                                    "will also try look-alike characters)"))
        rest = rest.replace(m.group(0), " ")
    for m in BATCH_RE.finditer(rest):
        b = m.group(1).upper()
        b = b if b.startswith("BATCH-") else f"BATCH-{b}" if re.match(r"^[A-Z]\d{3}$", b) else b
        if b not in q.batch_numbers:
            q.batch_numbers.append(b)
            q.explanation.append(f"batch number {m.group(0).strip()!r} -> {b}")
        rest = rest.replace(m.group(0), " ")
    for concept, (rx, fmt) in ID_RES.items():
        for m in rx.finditer(rest):
            v = fmt.format(int(m.group(1)))
            target = getattr(q, concept + "s")
            if v not in target:
                target.append(v)
                q.explanation.append(f"{concept.replace('_', ' ')} {m.group(0).strip()!r} -> {v}")
            rest = rest.replace(m.group(0), " ")

    low = rest.lower()
    for intent, words in INTENT_WORDS.items():
        hits = [w.strip() for w in words if w in low]
        if hits:
            q.intents.append(intent)
            q.keywords.extend(h for h in sorted(set(hits)) if h not in q.keywords)
            q.explanation.append(f"intent {intent}: {', '.join(sorted(set(hits)))}")
            for w in hits:
                # a one-word keyword removes the whole word it starts ('ship' -> 'shipments'),
                # or a fragment like 'ments' would be left behind as a search term
                low = re.sub(rf"\b\w*{re.escape(w)}\w*\b", " ", low) if " " not in w else low.replace(w, " ")

    for tok in re.findall(r"[a-z][a-z0-9+]{2,}", low):
        if tok not in STOPWORDS and tok not in q.terms and not any(tok in w for ws in INTENT_WORDS.values() for w in ws):
            q.terms.append(tok)
    if q.terms:
        q.explanation.append(f"terms for the databases to match locally: {', '.join(q.terms)}")
    q.keywords.extend(t for t in q.terms if t not in q.keywords)
    if not (q.concepts() or q.intents or q.terms):
        q.explanation.append("nothing recognisable: every database will be asked with the raw text")
        q.terms = [t for t in re.findall(r"[a-z0-9]{3,}", text.lower())][:8]
    return q
