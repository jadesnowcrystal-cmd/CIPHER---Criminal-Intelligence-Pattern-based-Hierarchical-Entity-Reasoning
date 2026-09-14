"""
entity_resolution.py
=====================
ENTITY RESOLUTION / ALIAS DEDUPLICATION LAYER

WHAT THIS FIXES
----------------
sihrelationship.py currently builds person nodes as:
    node_id = f"PERSON::{normalize_name(name)}"

That is an EXACT STRING match. "Rahul Sharma", "Rahul Shrma" (typo),
"Rahul Kumar Sharma", and "R. Sharma" all become four disconnected graph
nodes -- even though FIR data, CDR statements, and witness reports routinely
spell the same suspect's name differently across sources. This directly
undermines the core ask in the problem statement: "identifying hidden
relationships among suspects" when "data is fragmented ... and distributed
across multiple systems."

This module resolves that by:
  1. BLOCKING     -- group candidate records with phonetic keys (Soundex +
                     first-token index) so we never do a full O(n^2) compare.
  2. SCORING      -- Fellegi-Sunter probabilistic record linkage: combine
                     several weak/partial signals (name similarity, shared
                     phone, shared address/district, shared vehicle, case
                     co-occurrence) into one log-likelihood-ratio match
                     score, instead of trusting name-similarity alone.
  3. CLUSTERING   -- Union-Find over pairs that clear the match threshold,
                     producing one canonical entity per real person with a
                     confidence score and a full evidence trail (auditable --
                     important for investigators who need to justify a merge).

No third-party dependencies (no `python-Levenshtein`, no `jellyfish`) --
Levenshtein, Jaro-Winkler and Soundex are implemented from scratch so this
drops into the existing pipeline with zero new installs.

INTEGRATION POINT
------------------
sihrelationship.py's `RelationshipGraphBuilder.add_person()` should resolve
the canonical entity ID via this module *before* building "PERSON::{name}",
so two spellings of the same suspect collapse into a single graph node
instead of staying as separate, disconnected people.
"""

from __future__ import annotations

import re
import itertools
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


# ==========================================
# 1. STRING NORMALIZATION (Indian-name aware)
# ==========================================

# Common Indian honorific / transliteration noise to strip before comparing
_HONORIFIC_RE = re.compile(
    r"\b(mr|mrs|ms|md|shri|smt|dr|kumar|kum)\.?\b", re.IGNORECASE
)

# Common spelling-variant equivalence classes seen across FIR/CDR/witness
# transliteration of the same underlying name (extend as real data reveals more)
_ALIAS_EQUIV = {
    "mohd": "mohammed", "md": "mohammed", "muhammad": "mohammed",
    "mohammad": "mohammed",
    "shrma": "sharma", "sharme": "sharma",
    "kumr": "kumar",
}


def normalize_for_matching(raw: Any) -> str:
    """Lowercase, strip honorifics/punctuation, collapse whitespace, and
    apply known transliteration-equivalence substitutions token-by-token."""
    if raw is None:
        return ""
    s = str(raw).strip().lower()
    if not s or s in ("nan", "none", "n/a", "unknown"):
        return ""
    s = _HONORIFIC_RE.sub(" ", s)
    s = re.sub(r"[^a-z\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    tokens = [_ALIAS_EQUIV.get(tok, tok) for tok in s.split(" ")]
    return " ".join(tokens)


# ==========================================
# 2. PHONETIC ENCODING (blocking key)
# ==========================================

def soundex(name: str) -> str:
    """Classic Soundex code, applied per-token then joined -- used purely as
    a BLOCKING key (cheap pre-filter), never as the match decision itself."""
    name = re.sub(r"[^A-Za-z]", "", name).upper()
    if not name:
        return "0000"
    codes = {
        **{c: "1" for c in "BFPV"},
        **{c: "2" for c in "CGJKQSXZ"},
        **{c: "3" for c in "DT"},
        "L": "4",
        **{c: "5" for c in "MN"},
        "R": "6",
    }
    first_letter = name[0]
    tail = []
    prev = codes.get(first_letter, "")
    for ch in name[1:]:
        code = codes.get(ch, "")
        if code and code != prev:
            tail.append(code)
        if ch not in "HW":
            prev = code
    result = (first_letter + "".join(tail) + "000")[:4]
    return result


def phonetic_key(full_name: str) -> str:
    """Blocking key = soundex of first token + soundex of last token.
    Two names only get pairwise-compared if they land in the same block."""
    norm = normalize_for_matching(full_name)
    tokens = norm.split(" ")
    if not tokens or tokens == [""]:
        return "0000-0000"
    first = soundex(tokens[0])
    last = soundex(tokens[-1]) if len(tokens) > 1 else first
    return f"{first}-{last}"


# ==========================================
# 3. STRING SIMILARITY METRICS
# ==========================================

def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cost = 0 if ca == cb else 1
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
        prev = cur
    return prev[-1]


def levenshtein_similarity(a: str, b: str) -> float:
    if not a and not b:
        return 1.0
    dist = levenshtein(a, b)
    return 1.0 - dist / max(len(a), len(b), 1)


def jaro_similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    la, lb = len(a), len(b)
    if la == 0 or lb == 0:
        return 0.0
    match_dist = max(la, lb) // 2 - 1
    match_dist = max(match_dist, 0)

    a_matches = [False] * la
    b_matches = [False] * lb
    matches = 0
    for i, ca in enumerate(a):
        start = max(0, i - match_dist)
        end = min(i + match_dist + 1, lb)
        for j in range(start, end):
            if b_matches[j] or ca != b[j]:
                continue
            a_matches[i] = b_matches[j] = True
            matches += 1
            break
    if matches == 0:
        return 0.0

    transpositions = 0
    k = 0
    for i in range(la):
        if not a_matches[i]:
            continue
        while not b_matches[k]:
            k += 1
        if a[i] != b[k]:
            transpositions += 1
        k += 1
    transpositions //= 2

    m = matches
    return (m / la + m / lb + (m - transpositions) / m) / 3.0


def jaro_winkler_similarity(a: str, b: str, prefix_weight: float = 0.1) -> float:
    """Jaro-Winkler -- rewards names that share a common prefix, which fits
    Indian first-name/surname truncation and initial-based variants well."""
    jaro = jaro_similarity(a, b)
    prefix_len = 0
    for ca, cb in zip(a, b):
        if ca != cb:
            break
        prefix_len += 1
        if prefix_len == 4:
            break
    return jaro + prefix_len * prefix_weight * (1 - jaro)


def name_similarity(a: str, b: str) -> float:
    """Blend of Jaro-Winkler (good for typos/truncation) and normalized
    Levenshtein (good for insertions/deletions), normalized text only."""
    na, nb = normalize_for_matching(a), normalize_for_matching(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    jw = jaro_winkler_similarity(na, nb)
    lev = levenshtein_similarity(na, nb)
    return 0.6 * jw + 0.4 * lev


# ==========================================
# 4. FELLEGI-SUNTER PROBABILISTIC LINKAGE
# ==========================================
#
# For each comparison field we define:
#   m = P(agreement | records ARE the same entity)   -- typically high
#   u = P(agreement | records are NOT the same entity) -- typically low
# Field weight (log2(m/u) on agreement, log2((1-m)/(1-u)) on disagreement)
# is added to a total score. Higher score = stronger evidence of a match.
# These m/u values are illustrative priors (standard practice when no
# labeled training pairs exist yet); they should be re-estimated with EM
# once real labeled match/non-match pairs are available.

@dataclass
class FieldWeights:
    m: float  # P(agree | match)
    u: float  # P(agree | non-match)

    @property
    def agree_weight(self) -> float:
        import math
        return math.log2(self.m / self.u)

    @property
    def disagree_weight(self) -> float:
        import math
        return math.log2((1 - self.m) / (1 - self.u))


FIELD_PRIORS = {
    "name":    FieldWeights(m=0.92, u=0.10),  # fuzzy-agree threshold >= 0.85
    "phone":   FieldWeights(m=0.98, u=0.001), # exact match, very discriminating
    "address": FieldWeights(m=0.80, u=0.15),  # district/locality overlap
    "vehicle": FieldWeights(m=0.97, u=0.005), # exact plate match
    "case_co_occurrence": FieldWeights(m=0.55, u=0.20),  # weak corroborator only
}

# Score thresholds (tune against labeled pairs when available)
THRESHOLD_MATCH = 4.0      # auto-merge
THRESHOLD_POSSIBLE = 1.0   # flag for investigator review, don't auto-merge


@dataclass
class PersonRecord:
    record_id: str                     # e.g. "FIR-2024-001::ACCUSED"
    name: str
    phone: Optional[str] = None
    address: Optional[str] = None
    vehicles: List[str] = field(default_factory=list)
    case_id: Optional[str] = None
    source: Optional[str] = None       # e.g. "FIR", "CDR", "witness_statement"


@dataclass
class MatchExplanation:
    record_a: str
    record_b: str
    score: float
    decision: str  # "MATCH" | "POSSIBLE_MATCH" | "NON_MATCH"
    features: Dict[str, Any]


def _address_agree(a: Optional[str], b: Optional[str]) -> Optional[bool]:
    if not a or not b:
        return None
    na, nb = normalize_for_matching(a), normalize_for_matching(b)
    if not na or not nb:
        return None
    return na == nb or name_similarity(a, b) >= 0.80


def score_pair(r1: PersonRecord, r2: PersonRecord) -> MatchExplanation:
    score = 0.0
    features: Dict[str, Any] = {}

    # --- name field (always evaluated) ---
    nsim = name_similarity(r1.name, r2.name)
    name_agree = nsim >= 0.85
    w = FIELD_PRIORS["name"]
    score += w.agree_weight if name_agree else w.disagree_weight
    features["name_similarity"] = round(nsim, 3)
    features["name_agree"] = name_agree

    # --- phone field (only scored if both present) ---
    if r1.phone and r2.phone:
        phone_agree = r1.phone == r2.phone
        w = FIELD_PRIORS["phone"]
        score += w.agree_weight if phone_agree else w.disagree_weight
        features["phone_agree"] = phone_agree

    # --- address field ---
    addr_agree = _address_agree(r1.address, r2.address)
    if addr_agree is not None:
        w = FIELD_PRIORS["address"]
        score += w.agree_weight if addr_agree else w.disagree_weight
        features["address_agree"] = addr_agree

    # --- vehicle overlap ---
    if r1.vehicles and r2.vehicles:
        shared = set(r1.vehicles) & set(r2.vehicles)
        veh_agree = len(shared) > 0
        w = FIELD_PRIORS["vehicle"]
        score += w.agree_weight if veh_agree else w.disagree_weight
        features["vehicle_agree"] = veh_agree
        if shared:
            features["shared_vehicles"] = sorted(shared)

    # --- case co-occurrence (weak corroborating signal only) ---
    if r1.case_id and r2.case_id:
        co_agree = r1.case_id == r2.case_id
        w = FIELD_PRIORS["case_co_occurrence"]
        score += w.agree_weight if co_agree else w.disagree_weight
        features["same_case"] = co_agree

    if score >= THRESHOLD_MATCH:
        decision = "MATCH"
    elif score >= THRESHOLD_POSSIBLE:
        decision = "POSSIBLE_MATCH"
    else:
        decision = "NON_MATCH"

    return MatchExplanation(
        record_a=r1.record_id, record_b=r2.record_id,
        score=round(score, 3), decision=decision, features=features,
    )


# ==========================================
# 5. BLOCKING + UNION-FIND CLUSTERING
# ==========================================

class _UnionFind:
    def __init__(self, ids: List[str]):
        self.parent = {i: i for i in ids}

    def find(self, x: str) -> str:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, x: str, y: str):
        rx, ry = self.find(x), self.find(y)
        if rx != ry:
            self.parent[ry] = rx


@dataclass
class ResolvedEntity:
    canonical_id: str
    canonical_name: str
    member_record_ids: List[str]
    aliases: List[str]
    confidence: float
    evidence: List[MatchExplanation]


class EntityResolver:
    """Blocks candidate records by phonetic key, scores pairs within each
    block with Fellegi-Sunter linkage, and clusters MATCH-decision pairs
    with Union-Find into canonical entities."""

    def __init__(self):
        self.records: Dict[str, PersonRecord] = {}
        self.explanations: List[MatchExplanation] = []

    def add_record(self, record: PersonRecord):
        self.records[record.record_id] = record

    def add_records(self, records: List[PersonRecord]):
        for r in records:
            self.add_record(r)

    def _phonetic_blocks(self) -> Dict[str, List[str]]:
        blocks: Dict[str, List[str]] = {}
        for rid, rec in self.records.items():
            key = phonetic_key(rec.name)
            blocks.setdefault(key, []).append(rid)
        return blocks

    def _identifier_blocks(self) -> Dict[str, List[str]]:
        """Second blocking pass on strong identifiers (phone, vehicle plate).
        Two records sharing an exact phone/plate should always be compared
        even if their name strings land in different phonetic blocks (e.g.
        'R. Sharma' vs 'Rahul Sharma') -- name-only blocking would miss this."""
        blocks: Dict[str, List[str]] = {}
        for rid, rec in self.records.items():
            if rec.phone:
                blocks.setdefault(f"PHONE::{rec.phone}", []).append(rid)
            for v in rec.vehicles:
                blocks.setdefault(f"VEH::{v}", []).append(rid)
        return blocks

    def resolve(self) -> List[ResolvedEntity]:
        ids = list(self.records.keys())
        uf = _UnionFind(ids)
        self.explanations = []
        compared_pairs = set()

        all_blocks = list(self._phonetic_blocks().values()) + list(self._identifier_blocks().values())
        for block_ids in all_blocks:
            if len(block_ids) < 2:
                continue
            for rid_a, rid_b in itertools.combinations(sorted(block_ids), 2):
                pair_key = (rid_a, rid_b)
                if pair_key in compared_pairs:
                    continue
                compared_pairs.add(pair_key)
                exp = score_pair(self.records[rid_a], self.records[rid_b])
                self.explanations.append(exp)
                if exp.decision == "MATCH":
                    uf.union(rid_a, rid_b)

        clusters: Dict[str, List[str]] = {}
        for rid in ids:
            root = uf.find(rid)
            clusters.setdefault(root, []).append(rid)

        results = []
        for root, member_ids in clusters.items():
            members = [self.records[m] for m in member_ids]
            # canonical name = most frequent normalized name, longest form as tiebreak
            names = [m.name for m in members]
            canonical_name = max(set(names), key=lambda n: (names.count(n), len(n)))
            aliases = sorted(set(n for n in names if n != canonical_name))
            cluster_scores = [
                e.score for e in self.explanations
                if e.record_a in member_ids and e.record_b in member_ids
            ]
            confidence = round(
                min(1.0, max(cluster_scores) / (THRESHOLD_MATCH * 1.5)) if cluster_scores else 1.0,
                3,
            )
            evidence = [
                e for e in self.explanations
                if e.record_a in member_ids and e.record_b in member_ids
            ]
            results.append(ResolvedEntity(
                canonical_id=f"ENTITY::{root}",
                canonical_name=canonical_name,
                member_record_ids=member_ids,
                aliases=aliases,
                confidence=confidence,
                evidence=evidence,
            ))
        return results

    def possible_matches_for_review(self) -> List[MatchExplanation]:
        """POSSIBLE_MATCH pairs are deliberately NOT auto-merged -- surface
        them for an investigator to confirm/reject instead of silently
        guessing, since a wrong merge in a criminal case is far costlier
        than a missed one."""
        return [e for e in self.explanations if e.decision == "POSSIBLE_MATCH"]


# ==========================================
# 6. CONVENIENCE: name -> canonical id lookup
# ==========================================

def build_alias_lookup(resolved: List[ResolvedEntity]) -> Dict[str, str]:
    """Flatten resolved entities into {raw_name_or_record_id: canonical_id}
    for quick use inside RelationshipGraphBuilder.add_person()."""
    lookup: Dict[str, str] = {}
    for entity in resolved:
        for rid in entity.member_record_ids:
            lookup[rid] = entity.canonical_id
    return lookup


if __name__ == "__main__":
    # Small smoke test with realistic FIR/CDR-style alias noise
    resolver = EntityResolver()
    resolver.add_records([
        PersonRecord("FIR-101::ACCUSED", "Rahul Sharma", phone="9876543210",
                      address="Pune", case_id="FIR-101", source="FIR"),
        PersonRecord("FIR-204::ACCUSED", "Rahul Shrma", phone="9876543210",
                      address="Pune", case_id="FIR-204", source="FIR"),
        PersonRecord("CDR-889::CALLER", "R. Sharma", phone="9876543210",
                      case_id="CDR-889", source="CDR"),
        PersonRecord("WIT-33::MENTIONED", "Mohd Irfan", address="Nagpur",
                      case_id="WIT-33", source="witness"),
        PersonRecord("FIR-305::VICTIM", "Md Irfan Sheikh", address="Nagpur",
                      case_id="FIR-305", source="FIR"),
        PersonRecord("FIR-450::ACCUSED", "Sanjay Patil", phone="9123456780",
                      case_id="FIR-450", source="FIR"),
    ])
    entities = resolver.resolve()
    print(f"\n{len(resolver.records)} raw records -> {len(entities)} resolved entities\n")
    for e in entities:
        print(f"  {e.canonical_id}  '{e.canonical_name}'  confidence={e.confidence}")
        if e.aliases:
            print(f"      aliases merged: {e.aliases}")
        print(f"      source records: {e.member_record_ids}")
    review = resolver.possible_matches_for_review()
    if review:
        print(f"\n{len(review)} pair(s) flagged POSSIBLE_MATCH for investigator review:")
        for r in review:
            print(f"  {r.record_a} <-> {r.record_b}  score={r.score}  {r.features}")