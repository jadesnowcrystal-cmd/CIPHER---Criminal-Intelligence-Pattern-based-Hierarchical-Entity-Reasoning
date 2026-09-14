"""
sihrelationship.py
===================
RELATIONSHIP / GRAPH-BUILDING LAYER (Module 3a)

WHAT THIS REPLACES
-------------------
The old `relationship.py` was a FastAPI + Neo4j service that only knew how to
ingest a pre-built NLP entity/relation payload ("Janvi's NLP output"). Since
the NLP/RAG extraction step is being built later, that service had nothing to
actually ingest yet, and pulled in two hard dependencies (fastapi, neo4j)
that add no value to the current pipeline.

WHAT THIS FILE DOES INSTEAD (the crucial missing piece)
---------------------------------------------------------
It builds the relationship graph directly from the structured CSVs that
`main_investigation_pipeline.py` already generates (FIR dataset, Call
Records, FASTag/ANPR logs, Bank statements) using stable, canonical entity
IDs (phone number, vehicle plate, account number) instead of the old
`sihextraction.py` approach of hashing a name into a NEW id per case.

Why that matters for the problem statement ("uncover hidden relationships
... data is fragmented, unstructured, and distributed across multiple
systems"): because a phone number / vehicle / bank account is given the SAME
node id everywhere it appears, two people from two *different* FIRs who
share a phone, a vehicle, or an account are automatically connected in one
graph. `resolve_cross_case_links()` then turns those shared identifiers into
explicit PERSON-PERSON links, which is the core "connect the dots across
fragmented case files" capability the problem statement asks for.

This module is the shared foundation: `sihnetworkanalytics.py` (centrality /
bridges / communities / visualization) and `sihintelligenceengine.py`
(pattern detection / alerts) both build on the graph produced here instead
of re-parsing the CSVs themselves.

ENTITY RESOLUTION (UPDATED)
----------------------------
Exact-name matching alone used to mean "Rahul Sharma", "Rahul Shrma" (typo),
and "R. Sharma" became three disconnected PERSON nodes even when they were
the same suspect. `resolve_person_aliases()` (see below) now runs every
unique raw person name collected during ingestion through
`entity_resolution.EntityResolver` -- phonetic blocking + Fellegi-Sunter
probabilistic linkage over name similarity, shared phone, shared address,
and shared vehicle -- and merges confirmed alias nodes into one canonical
PERSON node before cross-case linking runs. Ambiguous pairs (not enough
corroborating evidence) are NOT auto-merged; they're surfaced via
`resolver.possible_matches_for_review()` for an investigator to confirm.
Two different people who genuinely share an exact name string with no other
distinguishing data can still be merged -- that residual case needs DOB or
a government ID field, which isn't in the current CSVs.
"""

import json
import logging
import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
import pandas as pd

from sihentityresolution import EntityResolver, PersonRecord

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("RelationshipGraph")

# ==========================================
# 1. PIPELINE FILE LOCATIONS & OUTPUT PATHS
# ==========================================

PIPELINE_FILES = {
    "fir": "complete_fir_dataset.csv",
    "cdr": "Call_Recording.csv",
    "sdr": "Subscriber_Detail_Records.csv",
    "fastag": "FASTag_Toll_Logs.csv",
    "bank": "Bank_Statement_Records.csv",
}

GRAPH_OUTPUT_PATH = "relationship_graph.json"

NODE_TYPE_PERSON = "PERSON"
NODE_TYPE_PHONE = "PHONE"
NODE_TYPE_VEHICLE = "VEHICLE"
NODE_TYPE_ACCOUNT = "ACCOUNT"
NODE_TYPE_LOCATION = "LOCATION"
NODE_TYPE_CASE = "CASE"


# ==========================================
# 2. NORMALIZATION HELPERS
# ==========================================

def normalize_name(raw: Any) -> Optional[str]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = re.sub(r"\s+", " ", str(raw)).strip()
    if not s or s.lower() in ("nan", "none", "n/a", "unknown"):
        return None
    return s.title()


def normalize_phone(raw: Any) -> Optional[str]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    digits = "".join(ch for ch in str(raw) if ch.isdigit())
    if len(digits) < 10:
        return None
    return digits[-10:]


def normalize_plate(raw: Any) -> Optional[str]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip().upper()
    if not s or s in ("NONE", "N/A", "NAN"):
        return None
    return s


def normalize_account(raw: Any) -> Optional[str]:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    s = str(raw).strip()
    if not s or s.upper() in ("NONE", "N/A", "NAN"):
        return None
    return s


def parse_vehicle_field(raw: Any) -> List[Dict[str, str]]:
    """Parses the '<PLATE> (<Color> <Make> <Model>); <PLATE> (...)' fields
    used throughout the FIR dataset into a list of {plate, description}."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    s = str(raw).strip()
    if not s or s.lower() in ("none", "n/a", "nan"):
        return []
    out = []
    for chunk in s.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "(" in chunk:
            plate, desc = chunk.split("(", 1)
            plate = normalize_plate(plate)
            desc = desc.rstrip(")").strip()
        else:
            plate, desc = normalize_plate(chunk), ""
        if plate:
            out.append({"plate": plate, "description": desc})
    return out


def parse_bank_person_field(raw: Any) -> Tuple[Optional[str], Optional[str]]:
    """'Saanvi Singh (INFORMANT)' -> ('Saanvi Singh', 'INFORMANT')."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None, None
    m = re.match(r"^(.*?)\s*\(([A-Za-z]+)\)\s*$", str(raw).strip())
    if m:
        return normalize_name(m.group(1)), m.group(2).upper()
    return normalize_name(raw), None


def _find_column(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """Case/whitespace-insensitive lookup of the first matching column name.
    Used for SDR ingestion since the exact header text in
    Subscriber_Detail_Records.csv isn't pinned down here -- if
    main_investigation_pipeline.py uses a different phrasing than the
    candidates below, add it to the relevant list rather than editing the
    ingestion logic itself."""
    normalized = {re.sub(r"[\s_]+", "", str(c)).lower(): c for c in df.columns}
    for candidate in candidates:
        key = re.sub(r"[\s_]+", "", candidate).lower()
        if key in normalized:
            return normalized[key]
    return None


# ==========================================
# 3. PIPELINE DATA LOADING
# ==========================================

def load_pipeline_tables(base_dir: str = ".") -> Dict[str, pd.DataFrame]:
    """Loads whichever of the pipeline's generated CSVs are present. Missing
    files degrade gracefully to an empty DataFrame instead of crashing, so
    this works even if only part of `main_investigation_pipeline.py` has
    been run."""
    tables = {}
    for key, filename in PIPELINE_FILES.items():
        path = os.path.join(base_dir, filename)
        if os.path.exists(path):
            try:
                tables[key] = pd.read_csv(path)
            except Exception:
                tables[key] = pd.DataFrame()
        else:
            tables[key] = pd.DataFrame()
    return tables


# ==========================================
# 4. GRAPH BUILDER
# ==========================================

class RelationshipGraphBuilder:
    """Builds one unified NetworkX graph across every case, with canonical
    node ids for people, phones, vehicles, accounts, locations, and cases."""

    def __init__(self):
        self.graph = nx.Graph()
        self.cross_case_links: List[Dict[str, Any]] = []

        # ---- entity resolution / alias dedup state ----
        # Aggregates every raw person name seen during ingestion with
        # whatever phone/address/vehicle evidence has been seen for it, so
        # resolve_person_aliases() can run Fellegi-Sunter linkage across
        # ALL sources (FIR + SDR + Bank) at once, not per-table.
        self._person_attrs: Dict[str, Dict[str, Any]] = {}
        self.resolved_entities: list = []
        self.entity_resolution_report: List[Dict[str, Any]] = []
        self.possible_duplicate_pairs: List[Dict[str, Any]] = []

    # ---- node helpers ----
    def _ensure_node(self, node_id: str, node_type: str, label: str, **extra):
        if not self.graph.has_node(node_id):
            self.graph.add_node(node_id, type=node_type, label=label,
                                 case_ids=set(), roles=set(), **extra)
        return node_id

    def add_person(self, name: str, role: Optional[str] = None, case_id: Optional[str] = None,
                    phone: Any = None, address: Any = None, vehicles: Optional[List[str]] = None) -> Optional[str]:
        name = normalize_name(name)
        if not name:
            return None
        node_id = f"PERSON::{name}"
        self._ensure_node(node_id, NODE_TYPE_PERSON, name)
        if case_id:
            self.graph.nodes[node_id]["case_ids"].add(case_id)
        if role:
            self.graph.nodes[node_id]["roles"].add(role)

        # feed the entity-resolution aggregator (optional phone/address/
        # vehicles let alias merging use more than just name similarity)
        attrs = self._person_attrs.setdefault(
            name, {"phone": None, "address": None, "vehicles": set(), "case_id": case_id}
        )
        norm_phone = normalize_phone(phone)
        if norm_phone and not attrs["phone"]:
            attrs["phone"] = norm_phone
        if address and not attrs["address"]:
            attrs["address"] = str(address)
        if vehicles:
            attrs["vehicles"].update(vehicles)
        if case_id and not attrs["case_id"]:
            attrs["case_id"] = case_id

        return node_id

    def add_phone(self, phone: Any) -> Optional[str]:
        phone = normalize_phone(phone)
        if not phone:
            return None
        node_id = f"PHONE::{phone}"
        self._ensure_node(node_id, NODE_TYPE_PHONE, phone)
        return node_id

    def add_vehicle(self, plate: Any, description: str = "") -> Optional[str]:
        plate = normalize_plate(plate)
        if not plate:
            return None
        node_id = f"VEHICLE::{plate}"
        self._ensure_node(node_id, NODE_TYPE_VEHICLE, plate, description=description)
        return node_id

    def add_account(self, account: Any, owner_label: str = "") -> Optional[str]:
        account = normalize_account(account)
        if not account:
            return None
        node_id = f"ACCOUNT::{account}"
        self._ensure_node(node_id, NODE_TYPE_ACCOUNT, account, owner_label=owner_label)
        return node_id

    def add_location(self, name: Any) -> Optional[str]:
        name = normalize_name(name)
        if not name:
            return None
        node_id = f"LOCATION::{name}"
        self._ensure_node(node_id, NODE_TYPE_LOCATION, name)
        return node_id

    def add_case(self, case_id: str, **meta) -> str:
        node_id = f"CASE::{case_id}"
        self._ensure_node(node_id, NODE_TYPE_CASE, case_id, **meta)
        return node_id

    # ---- edge helper (merges repeated edges instead of overwriting) ----
    def _link(self, a: Optional[str], b: Optional[str], relation: str,
               weight: float = 1.0, case_id: Optional[str] = None, **attrs):
        if not a or not b or a == b:
            return
        if self.graph.has_edge(a, b):
            e = self.graph[a][b]
            e["weight"] = e.get("weight", 1.0) + weight
            rel_types = e.setdefault("relation_types", set())
            rel_types.add(relation)
            if case_id:
                e.setdefault("case_ids", set()).add(case_id)
            evidence = e.setdefault("evidence", [])
            if len(evidence) < 25:
                evidence.append({"relation": relation, "case_id": case_id, **attrs})
        else:
            self.graph.add_edge(
                a, b, weight=weight, relation_types={relation},
                case_ids={case_id} if case_id else set(),
                evidence=[{"relation": relation, "case_id": case_id, **attrs}]
            )

    # ---- ingestion: FIR dataset ----
    def ingest_fir_table(self, df: pd.DataFrame):
        if df is None or df.empty:
            return
        role_cols = {
            "INFORMANT": ("Informant_Name", "Informant_Contact", "Informant_Vehicles"),
            "VICTIM": ("Victim_Name", "Victim_Contact", "Victim_Vehicles"),
            "ACCUSED": ("Accused_Name_Alias", "Accused_Contact", "Accused_Vehicles"),
        }
        for _, row in df.iterrows():
            case_id = str(row.get("FIR_No", "UNKNOWN"))
            self.add_case(case_id, district=row.get("District"), case_type=row.get("Case_Type"),
                          date=row.get("Date_Time_of_FIR"))
            role_nodes = {}
            for role, (name_c, phone_c, veh_c) in role_cols.items():
                veh_list = parse_vehicle_field(row.get(veh_c))
                person = self.add_person(
                    row.get(name_c), role, case_id,
                    phone=row.get(phone_c), address=row.get("District"),
                    vehicles=[v["plate"] for v in veh_list],
                )
                role_nodes[role] = person
                if not person:
                    continue
                self._link(person, f"CASE::{case_id}", f"INVOLVED_AS_{role}", case_id=case_id)
                phone = self.add_phone(row.get(phone_c))
                self._link(person, phone, "OWNS_PHONE", case_id=case_id)
                for veh in veh_list:
                    vnode = self.add_vehicle(veh["plate"], veh["description"])
                    self._link(person, vnode, "OWNS_VEHICLE", case_id=case_id)

            if role_nodes.get("ACCUSED") and role_nodes.get("VICTIM"):
                self._link(role_nodes["ACCUSED"], role_nodes["VICTIM"], "ACCUSED_OF_CRIME_AGAINST",
                           case_id=case_id, case_type=row.get("Case_Type"))
            if role_nodes.get("INFORMANT") and role_nodes.get("VICTIM"):
                self._link(role_nodes["INFORMANT"], role_nodes["VICTIM"], "REPORTED_INCIDENT_FOR",
                           case_id=case_id)

    # ---- ingestion: Call Detail Records ----
    def ingest_cdr_table(self, df: pd.DataFrame):
        if df is None or df.empty:
            return
        for _, row in df.iterrows():
            case_id = str(row.get("Case_ID", "UNKNOWN"))
            a = self.add_phone(row.get("Calling Number (A-Party)"))
            b = self.add_phone(row.get("Called Number (B-Party)"))
            self._link(a, b, "CALLED", case_id=case_id,
                       timestamp=row.get("Call Date & Time"),
                       duration_s=row.get("Duration (s)"))

    # ---- ingestion: FASTag / ANPR toll crossings ----
    def ingest_fastag_table(self, df: pd.DataFrame):
        if df is None or df.empty:
            return
        for _, row in df.iterrows():
            case_id = str(row.get("Case_ID", "UNKNOWN"))
            vehicle = self.add_vehicle(row.get("Vehicle Registration"))
            location = self.add_location(row.get("Toll Plaza ID & Location"))
            mismatch = str(row.get("ANPR Cross-Match", "")).upper() == "MISMATCH"
            self._link(vehicle, location, "CROSSED_TOLL", case_id=case_id,
                       timestamp=row.get("Timestamp (IST)"), anpr_mismatch=mismatch)

    # ---- ingestion: Bank statements ----
    def ingest_bank_table(self, df: pd.DataFrame):
        if df is None or df.empty:
            return
        for _, row in df.iterrows():
            case_id = str(row.get("Case_ID", "UNKNOWN"))
            name, role = parse_bank_person_field(row.get("Person"))
            person = self.add_person(name, role, case_id)
            account = self.add_account(row.get("Account_Number"), owner_label=name or "")
            self._link(person, account, "OWNS_ACCOUNT", case_id=case_id)

            counterparty_id = row.get("Counterparty_Account_UPI") or row.get("Counterparty_Name")
            counterparty = self.add_account(counterparty_id, owner_label=row.get("Counterparty_Name", ""))
            if counterparty:
                self.graph.nodes[counterparty]["label"] = row.get("Counterparty_Name", counterparty)
            txn_type = str(row.get("Type_CR_DR", "")).upper()
            src, dst = (account, counterparty) if txn_type == "DR" else (counterparty, account)
            self._link(src, dst, "TRANSFERRED_TO", case_id=case_id,
                       amount=row.get("Amount_INR"), timestamp=row.get("Transaction_DateTime"),
                       channel=row.get("Channel"))

    # ---- ingestion: Subscriber Detail Records (SDR) ----
    # THE FIX for phone numbers floating with no person attached: FIR
    # ingestion only links a phone to a person when that number is the
    # FIR's own Informant/Victim/Accused contact field. Every OTHER number
    # a person's phone called (from Call_Recording.csv) had no name behind
    # it. SDR is the actual "who owns this number" registry investigators
    # use for exactly this -- so every phone node, including third-party
    # call contacts, gets a PERSON node attached whenever SDR has a record
    # for it.
    def ingest_sdr_table(self, df: pd.DataFrame):
        if df is None or df.empty:
            return
        phone_col = _find_column(df, [
            "Mobile Number", "Phone Number", "Subscriber Mobile Number",
            "MSISDN", "Contact Number", "Number",
        ])
        name_col = _find_column(df, [
            "Subscriber Name", "Name", "Customer Name", "Registered Name", "Owner Name",
        ])
        case_col = _find_column(df, ["Case_ID", "Case Id", "FIR_No"])

        if not phone_col or not name_col:
            logger.warning(
                "Subscriber_Detail_Records.csv is loaded but its phone/name "
                "columns couldn't be identified (looked for phone in %s, "
                "name in %s -- actual columns: %s). SDR phone-owner linking "
                "skipped; add the real header names to the candidate lists "
                "in _find_column() calls inside ingest_sdr_table().",
                phone_col, name_col, list(df.columns),
            )
            return

        for _, row in df.iterrows():
            phone = self.add_phone(row.get(phone_col))
            case_id = str(row.get(case_col)) if case_col else None
            person = self.add_person(row.get(name_col), case_id=case_id, phone=row.get(phone_col))
            if not phone or not person:
                continue
            self._link(person, phone, "REGISTERED_SUBSCRIBER_OF", case_id=case_id)

    # ---- entity resolution / alias dedup (runs BEFORE cross-case linking,
    #      so shared-identifier links connect through the merged canonical
    #      person instead of missing because a suspect was split across
    #      several misspelled PERSON nodes) ----
    def resolve_person_aliases(self) -> List[Dict[str, Any]]:
        """Runs entity_resolution.EntityResolver over every unique raw
        person name seen during ingestion (FIR + SDR + Bank), merges
        confirmed-alias PERSON nodes into one canonical node, and returns
        an audit report of what was merged and why. Ambiguous pairs are
        NOT auto-merged -- see resolver.possible_matches_for_review()."""
        if not self._person_attrs:
            return []

        resolver = EntityResolver()
        for name, attrs in self._person_attrs.items():
            resolver.add_record(PersonRecord(
                record_id=name,
                name=name,
                phone=attrs.get("phone"),
                address=attrs.get("address"),
                vehicles=sorted(attrs.get("vehicles") or []),
                case_id=attrs.get("case_id"),
            ))
        self.resolved_entities = resolver.resolve()

        report = []
        for entity in self.resolved_entities:
            if len(entity.member_record_ids) < 2:
                continue  # nothing to merge for this person
            canonical_node = f"PERSON::{entity.canonical_name}"
            for alias_name in entity.member_record_ids:
                alias_node = f"PERSON::{alias_name}"
                if alias_node == canonical_node or not self.graph.has_node(alias_node):
                    continue
                self._merge_person_node(alias_node, canonical_node)
            report.append({
                "canonical_name": entity.canonical_name,
                "aliases_merged": [a for a in entity.member_record_ids if a != entity.canonical_name],
                "confidence": entity.confidence,
                "evidence": [
                    {"record_a": e.record_a, "record_b": e.record_b,
                     "score": e.score, "features": e.features}
                    for e in entity.evidence
                ],
            })

        possible = resolver.possible_matches_for_review()
        self.possible_duplicate_pairs = [
            {
                "name_a": p.record_a, "name_b": p.record_b,
                "score": p.score, "features": p.features,
            }
            for p in possible
        ]
        if possible:
            logger.info(
                "%d name pair(s) flagged POSSIBLE_MATCH for investigator "
                "review (not auto-merged): %s",
                len(possible), [(p.record_a, p.record_b, p.score) for p in possible],
            )
        self.entity_resolution_report = report
        if report:
            logger.info("Entity resolution merged %d alias cluster(s).", len(report))
        return report

    def _merge_person_node(self, alias_node: str, canonical_node: str):
        """Redirects every edge on alias_node onto canonical_node, unions
        their case_ids/roles, records the merge, and removes alias_node."""
        if not self.graph.has_node(canonical_node):
            self.graph.add_node(canonical_node, type=NODE_TYPE_PERSON,
                                 label=canonical_node.split("::", 1)[1],
                                 case_ids=set(), roles=set())
        c_attrs = self.graph.nodes[canonical_node]
        a_attrs = self.graph.nodes[alias_node]
        c_attrs["case_ids"] = c_attrs.get("case_ids", set()) | a_attrs.get("case_ids", set())
        c_attrs["roles"] = c_attrs.get("roles", set()) | a_attrs.get("roles", set())
        c_attrs.setdefault("merged_aliases", set()).add(a_attrs.get("label", alias_node))

        for neighbor in list(self.graph.neighbors(alias_node)):
            if neighbor == canonical_node:
                continue
            edge_attrs = self.graph[alias_node][neighbor]
            if self.graph.has_edge(canonical_node, neighbor):
                ce = self.graph[canonical_node][neighbor]
                ce["weight"] = ce.get("weight", 1.0) + edge_attrs.get("weight", 1.0)
                ce.setdefault("relation_types", set()).update(edge_attrs.get("relation_types", set()))
                ce.setdefault("case_ids", set()).update(edge_attrs.get("case_ids", set()))
                ce.setdefault("evidence", []).extend(edge_attrs.get("evidence", [])[:25])
            else:
                self.graph.add_edge(canonical_node, neighbor, **edge_attrs)
        self.graph.remove_node(alias_node)

    # ---- cross-case identity resolution (the key "hidden network" step) ----
    def resolve_cross_case_links(self) -> List[Dict[str, Any]]:
        """For every shared identifier (phone / vehicle / account) touching
        more than one PERSON node, draw a direct PERSON-PERSON edge. If the
        people involved come from different FIR cases, this is exactly the
        kind of hidden cross-case link investigators are asked to find."""
        findings = []
        for node_id, attrs in list(self.graph.nodes(data=True)):
            if attrs.get("type") not in (NODE_TYPE_PHONE, NODE_TYPE_VEHICLE, NODE_TYPE_ACCOUNT):
                continue
            person_neighbors = [n for n in self.graph.neighbors(node_id)
                                 if self.graph.nodes[n].get("type") == NODE_TYPE_PERSON]
            if len(person_neighbors) < 2:
                continue
            for i in range(len(person_neighbors)):
                for j in range(i + 1, len(person_neighbors)):
                    p1, p2 = person_neighbors[i], person_neighbors[j]
                    cases1 = self.graph.nodes[p1].get("case_ids", set())
                    cases2 = self.graph.nodes[p2].get("case_ids", set())
                    cross_case = bool(cases1 - cases2 or cases2 - cases1)
                    self._link(p1, p2, f"LINKED_VIA_SHARED_{attrs['type']}",
                               shared_identifier=attrs.get("label"))
                    findings.append({
                        "person_a": self.graph.nodes[p1]["label"],
                        "person_b": self.graph.nodes[p2]["label"],
                        "shared_identifier_type": attrs["type"],
                        "shared_identifier": attrs.get("label"),
                        "cross_case": cross_case,
                        "cases_a": sorted(cases1), "cases_b": sorted(cases2)
                    })
        self.cross_case_links = findings
        return findings

    def build(self, tables: Optional[Dict[str, pd.DataFrame]] = None, base_dir: str = ".") -> nx.Graph:
        tables = tables or load_pipeline_tables(base_dir)
        self.ingest_fir_table(tables.get("fir", pd.DataFrame()))
        self.ingest_sdr_table(tables.get("sdr", pd.DataFrame()))
        self.ingest_cdr_table(tables.get("cdr", pd.DataFrame()))
        self.ingest_fastag_table(tables.get("fastag", pd.DataFrame()))
        self.ingest_bank_table(tables.get("bank", pd.DataFrame()))
        self.resolve_person_aliases()   # merge alias spellings BEFORE cross-case linking
        self.resolve_cross_case_links()
        return self.graph

    # ---- persistence (JSON instead of a Neo4j server -- no DB required) ----
    def save(self, path: str = GRAPH_OUTPUT_PATH):
        data = nx.node_link_data(self.graph, edges="edges")
        # sets aren't JSON serializable -> convert
        for node in data["nodes"]:
            for k, v in list(node.items()):
                if isinstance(v, set):
                    node[k] = sorted(v)
        for edge in data["edges"]:
            for k, v in list(edge.items()):
                if isinstance(v, set):
                    edge[k] = sorted(v)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
        return path

    @staticmethod
    def load(path: str = GRAPH_OUTPUT_PATH) -> nx.Graph:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return nx.node_link_graph(data, edges="edges")


# ==========================================
# 5. QUERY HELPERS (used by the timeline / analytics UI)
# ==========================================

def get_entity_connections(graph: nx.Graph, entity_id: str, depth: int = 1) -> Dict[str, Any]:
    if entity_id not in graph:
        return {"entity_id": entity_id, "found": False}
    nodes = {entity_id}
    frontier = {entity_id}
    for _ in range(depth):
        nxt = set()
        for n in frontier:
            nxt.update(graph.neighbors(n))
        nodes.update(nxt)
        frontier = nxt
    sub = graph.subgraph(nodes)
    return {
        "entity_id": entity_id, "found": True,
        "nodes": [{"id": n, **{k: (sorted(v) if isinstance(v, set) else v) for k, v in a.items()}}
                  for n, a in sub.nodes(data=True)],
        "edges": [{"source": u, "target": v,
                   **{k: (sorted(x) if isinstance(x, set) else x) for k, x in a.items()}}
                  for u, v, a in sub.edges(data=True)]
    }


def find_relationship_path(graph: nx.Graph, source_id: str, target_id: str,
                            max_depth: int = 6) -> Optional[List[str]]:
    if source_id not in graph or target_id not in graph:
        return None
    try:
        path = nx.shortest_path(graph, source_id, target_id)
        return path if len(path) - 1 <= max_depth else None
    except nx.NetworkXNoPath:
        return None


def summarize_graph(graph: nx.Graph) -> Dict[str, Any]:
    type_counts = defaultdict(int)
    for _, attrs in graph.nodes(data=True):
        type_counts[attrs.get("type", "UNKNOWN")] += 1
    return {
        "total_nodes": graph.number_of_nodes(),
        "total_edges": graph.number_of_edges(),
        "node_type_counts": dict(type_counts),
        "density": round(nx.density(graph), 5) if graph.number_of_nodes() else 0.0,
    }


# ==========================================
# 6. TOP-LEVEL ENTRY POINT
# ==========================================

ENTITY_RESOLUTION_REPORT_PATH = "entity_resolution_report.json"


def build_relationship_graph(base_dir: str = ".", save: bool = True) -> Tuple[nx.Graph, List[Dict[str, Any]], Dict[str, Any]]:
    builder = RelationshipGraphBuilder()
    graph = builder.build(base_dir=base_dir)
    entity_resolution = {
        "merged_clusters": builder.entity_resolution_report,
        "possible_duplicates": builder.possible_duplicate_pairs,
    }
    if save:
        builder.save()
        with open(ENTITY_RESOLUTION_REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(entity_resolution, f, indent=2, default=str)
    return graph, builder.cross_case_links, entity_resolution


if __name__ == "__main__":
    print("==================================================================")
    print("            SIH RELATIONSHIP GRAPH BUILDER — STANDALONE RUN        ")
    print("==================================================================")
    graph, links, entity_resolution = build_relationship_graph()
    summary = summarize_graph(graph)
    print(json.dumps(summary, indent=2))

    print(f"\nEntity resolution: {len(entity_resolution['merged_clusters'])} alias cluster(s) merged, "
          f"{len(entity_resolution['possible_duplicates'])} pair(s) flagged for review.")
    print(f"Entity resolution report saved to: {ENTITY_RESOLUTION_REPORT_PATH}")

    cross_case = [l for l in links if l["cross_case"]]
    print(f"\nCross-case suspect links found: {len(cross_case)}")
    for link in cross_case[:10]:
        print(f" - {link['person_a']}  <->  {link['person_b']}  "
              f"via shared {link['shared_identifier_type']} ({link['shared_identifier']})  "
              f"[cases {link['cases_a']} vs {link['cases_b']}]")

    print(f"\nGraph saved to: {GRAPH_OUTPUT_PATH}")
