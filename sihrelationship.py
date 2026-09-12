
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

LIMITATION (documented, not hidden): entity resolution here is done on
normalized names + hard identifiers (phone/vehicle/account). Two different
people who happen to share an exact name string will currently be merged
into one node. Proper disambiguation (DOB, address, fuzzy matching) is a
job for the NLP/entity-resolution stage planned later.
"""

import json
import os
import re
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx
import pandas as pd

# ==========================================
# 1. PIPELINE FILE LOCATIONS & OUTPUT PATHS
# ==========================================

PIPELINE_FILES = {
    "fir": "complete_fir_dataset.csv",
    "cdr": "Call_Recording.csv",
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

    # ---- node helpers ----
    def _ensure_node(self, node_id: str, node_type: str, label: str, **extra):
        if not self.graph.has_node(node_id):
            self.graph.add_node(node_id, type=node_type, label=label,
                                 case_ids=set(), roles=set(), **extra)
        return node_id

    def add_person(self, name: str, role: Optional[str] = None, case_id: Optional[str] = None) -> Optional[str]:
        name = normalize_name(name)
        if not name:
            return None
        node_id = f"PERSON::{name}"
        self._ensure_node(node_id, NODE_TYPE_PERSON, name)
        if case_id:
            self.graph.nodes[node_id]["case_ids"].add(case_id)
        if role:
            self.graph.nodes[node_id]["roles"].add(role)
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
                person = self.add_person(row.get(name_c), role, case_id)
                role_nodes[role] = person
                if not person:
                    continue
                self._link(person, f"CASE::{case_id}", f"INVOLVED_AS_{role}", case_id=case_id)
                phone = self.add_phone(row.get(phone_c))
                self._link(person, phone, "OWNS_PHONE", case_id=case_id)
                for veh in parse_vehicle_field(row.get(veh_c)):
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
        self.ingest_cdr_table(tables.get("cdr", pd.DataFrame()))
        self.ingest_fastag_table(tables.get("fastag", pd.DataFrame()))
        self.ingest_bank_table(tables.get("bank", pd.DataFrame()))
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

def build_relationship_graph(base_dir: str = ".", save: bool = True) -> Tuple[nx.Graph, List[Dict[str, Any]]]:
    builder = RelationshipGraphBuilder()
    graph = builder.build(base_dir=base_dir)
    if save:
        builder.save()
    return graph, builder.cross_case_links


if __name__ == "__main__":
    print("==================================================================")
    print("            SIH RELATIONSHIP GRAPH BUILDER — STANDALONE RUN        ")
    print("==================================================================")
    graph, links = build_relationship_graph()
    summary = summarize_graph(graph)
    print(json.dumps(summary, indent=2))

    cross_case = [l for l in links if l["cross_case"]]
    print(f"\nCross-case suspect links found: {len(cross_case)}")
    for link in cross_case[:10]:
        print(f" - {link['person_a']}  <->  {link['person_b']}  "
              f"via shared {link['shared_identifier_type']} ({link['shared_identifier']})  "
              f"[cases {link['cases_a']} vs {link['cases_b']}]")

    print(f"\nGraph saved to: {GRAPH_OUTPUT_PATH}")
