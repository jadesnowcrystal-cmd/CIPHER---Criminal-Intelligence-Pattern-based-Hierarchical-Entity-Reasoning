"""
sihintelligenceengine.py
=========================
PATTERN DETECTION & ALERTING LAYER (Module 3c)

WHAT'S KEPT FROM THE OLD `intelligence_engine.py`
-----------------------------------------------------
`detect_communication_spikes` (per-entity call-volume outliers) and
`detect_financial_anomalies` (per-sender transaction-amount outliers) were
already working, generic, statistically sound (z-score based) implementations
-- kept, just re-pointed at the real CDR / Bank Statement column names instead
of the placeholder `entity_a/entity_b` / `sender/receiver` schema.

Graph-level risk scoring and clustering are NOT duplicated here -- that's
`sihnetworkanalytics.py`'s job, working off the same shared graph from
`sihrelationship.py`. This file reads that module's report so alerts stay
consistent with one graph instead of two engines computing centrality twice.

WHAT WAS MISSING AND IS NOW IMPLEMENTED (the crucial gap)
--------------------------------------------------------------
The old file's `detect_contact_chains`, `detect_coordinated_sequences`,
`detect_location_loops`, and `detect_movement_anomalies` were explicit,
documented stubs that always returned an empty DataFrame. These map directly
onto the problem statement's "detect suspicious patterns and unusual
activities" requirement, and the pipeline already generates the CDR/FASTag
data needed to compute them without any NLP step, so they're implemented
here:

- detect_contact_chains        -> A calls B, B calls C within a short window
                                   (classic relay / cut-out communication
                                   pattern).
- detect_coordinated_sequences -> 2+ distinct vehicles crossing the same toll
                                   plaza within a tight time window (possible
                                   convoy / coordinated meet).
- detect_location_loops        -> the same vehicle re-crossing the same toll
                                   plaza repeatedly in a short span (possible
                                   surveillance evasion / repeated rendezvous).
- detect_movement_anomalies    -> surfaces the ANPR "plate mismatch" flags the
                                   pipeline already generates (identity /
                                   plate-cloning signal), so it's caught as an
                                   intelligence alert instead of only living
                                   silently inside a CSV column.
"""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

try:
    from sihrelationship import load_pipeline_tables
except ImportError:
    load_pipeline_tables = None

try:
    from sihnetworkanalytics import run_network_analytics, ANALYTICS_OUTPUT_PATH
except ImportError:
    run_network_analytics, ANALYTICS_OUTPUT_PATH = None, "network_analytics_report.json"

INTELLIGENCE_OUTPUT_PATH = "intelligence_report.json"


def _safe_float(val, default=0.0):
    try:
        return float(val) if pd.notnull(val) else default
    except Exception:
        return default


def _normalize_score(val):
    return float(np.clip(val, 0, 100))


@dataclass
class EngineConfig:
    alert_threshold: float = 55.0
    max_alerts: int = 100
    comm_spike_min_days: int = 3
    contact_chain_max_gap_minutes: int = 30
    coordinated_window_minutes: int = 20
    location_loop_min_repeats: int = 3
    location_loop_window_hours: int = 48


@dataclass
class IntelligenceAlert:
    alert_id: str
    alert_type: str
    severity: str
    score: float
    confidence: float
    summary: str
    entities: List[str]
    evidence: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self):
        return self.__dict__


class PatternIntelligenceEngine:
    def __init__(self, config: Optional[EngineConfig] = None):
        self.config = config or EngineConfig()
        self.alerts: List[IntelligenceAlert] = []

    def _severity(self, s: float) -> str:
        return "critical" if s >= 85 else "high" if s >= 70 else "medium" if s >= 55 else "low"

    def _alert(self, atype, score, conf, summary, entities, evidence) -> IntelligenceAlert:
        return IntelligenceAlert(
            alert_id=f"ALT-{len(self.alerts) + 1:05d}", alert_type=atype,
            severity=self._severity(score), score=round(_normalize_score(score), 2),
            confidence=round(_normalize_score(conf), 2), summary=summary,
            entities=sorted(set(map(str, entities))), evidence=evidence
        )

    # ================================================================
    # ADAPTERS: raw pipeline CSV columns -> generic analysis schema
    # ================================================================
    @staticmethod
    def adapt_communications(cdr_df: pd.DataFrame) -> pd.DataFrame:
        if cdr_df is None or cdr_df.empty:
            return pd.DataFrame(columns=["entity_a", "entity_b", "timestamp", "case_id", "duration_s"])
        df = pd.DataFrame({
            "entity_a": cdr_df["Calling Number (A-Party)"].astype(str),
            "entity_b": cdr_df["Called Number (B-Party)"].astype(str),
            "timestamp": pd.to_datetime(cdr_df["Call Date & Time"], format="%d/%m/%Y %H:%M", errors="coerce"),
            "case_id": cdr_df.get("Case_ID"),
            "duration_s": cdr_df.get("Duration (s)"),
        })
        return df.dropna(subset=["timestamp"])

    @staticmethod
    def adapt_transactions(bank_df: pd.DataFrame) -> pd.DataFrame:
        if bank_df is None or bank_df.empty:
            return pd.DataFrame(columns=["sender", "receiver", "amount", "timestamp", "case_id"])
        person = bank_df["Person"].astype(str).str.replace(r"\s*\([A-Za-z]+\)\s*$", "", regex=True)
        is_debit = bank_df["Type_CR_DR"].astype(str).str.upper() == "DR"
        sender = np.where(is_debit, person, bank_df["Counterparty_Name"].astype(str))
        receiver = np.where(is_debit, bank_df["Counterparty_Name"].astype(str), person)
        df = pd.DataFrame({
            "sender": sender, "receiver": receiver,
            "amount": bank_df["Amount_INR"].apply(_safe_float),
            "timestamp": pd.to_datetime(bank_df["Transaction_DateTime"], errors="coerce"),
            "case_id": bank_df.get("Case_ID"),
        })
        return df.dropna(subset=["timestamp"])

    # ================================================================
    # KEPT & RE-POINTED DETECTORS
    # ================================================================
    def detect_communication_spikes(self, communications: pd.DataFrame) -> pd.DataFrame:
        """Entities whose daily call volume is a statistical outlier (z>=2)
        relative to their OWN baseline."""
        if communications is None or communications.empty:
            return pd.DataFrame()
        long_df = pd.concat([
            communications[["entity_a", "timestamp"]].rename(columns={"entity_a": "entity_id"}),
            communications[["entity_b", "timestamp"]].rename(columns={"entity_b": "entity_id"})
        ])
        daily = (long_df.groupby(["entity_id", long_df["timestamp"].dt.date])
                 .size().rename("daily_count").reset_index())
        rows = []
        for entity_id, group in daily.groupby("entity_id"):
            if len(group) < self.config.comm_spike_min_days:
                continue
            mean, std = group["daily_count"].mean(), group["daily_count"].std(ddof=0)
            if not std or pd.isna(std):
                continue
            group = group.copy()
            group["z_score"] = (group["daily_count"] - mean) / std
            for _, r in group[group["z_score"] >= 2.0].iterrows():
                rows.append({"entity_id": entity_id, "date": str(r["timestamp"]),
                             "daily_count": int(r["daily_count"]), "baseline_mean": round(float(mean), 2),
                             "z_score": round(float(r["z_score"]), 2)})
        return pd.DataFrame(rows)

    def detect_financial_anomalies(self, transactions: pd.DataFrame) -> pd.DataFrame:
        """Transactions whose amount is a statistical outlier (z>=2.5)
        relative to the sender's OWN baseline."""
        if transactions is None or transactions.empty:
            return pd.DataFrame()
        rows = []
        for sender, group in transactions.groupby("sender"):
            if len(group) < 3:
                continue
            mean, std = group["amount"].mean(), group["amount"].std(ddof=0)
            if not std or pd.isna(std):
                continue
            for _, r in group.iterrows():
                z = (r["amount"] - mean) / std
                if z >= 2.5:
                    rows.append({"sender": str(sender), "receiver": str(r["receiver"]),
                                 "amount": r["amount"], "timestamp": str(r["timestamp"]),
                                 "baseline_mean": round(float(mean), 2), "z_score": round(float(z), 2)})
        return pd.DataFrame(rows)

    # ================================================================
    # NEWLY IMPLEMENTED DETECTORS (previously permanent stubs)
    # ================================================================
    def detect_contact_chains(self, communications: pd.DataFrame) -> pd.DataFrame:
        """A calls B, then B calls someone new (C) shortly after -- a relay
        / cut-out pattern often used to keep a principal off direct comms."""
        if communications is None or communications.empty:
            return pd.DataFrame()
        df = communications.sort_values("timestamp")
        gap = pd.Timedelta(minutes=self.config.contact_chain_max_gap_minutes)
        by_a = {a: g.sort_values("timestamp") for a, g in df.groupby("entity_a")}

        chains = []
        for _, first in df.iterrows():
            a, b, t = first["entity_a"], first["entity_b"], first["timestamp"]
            relay = by_a.get(b)
            if relay is None:
                continue
            window = relay[(relay["timestamp"] > t) & (relay["timestamp"] <= t + gap) & (relay["entity_b"] != a)]
            for _, second in window.iterrows():
                chains.append({
                    "leg_1": f"{a} -> {b}", "leg_2": f"{b} -> {second['entity_b']}",
                    "hop_entities": [a, b, second["entity_b"]],
                    "first_call_time": str(t), "second_call_time": str(second["timestamp"]),
                    "gap_minutes": round((second["timestamp"] - t).total_seconds() / 60, 1),
                    "case_id": first.get("case_id")
                })
        return pd.DataFrame(chains).drop_duplicates(subset=["leg_1", "leg_2"]) if chains else pd.DataFrame()

    def detect_coordinated_sequences(self, fastag_df: pd.DataFrame) -> pd.DataFrame:
        """2+ distinct vehicles crossing the SAME toll plaza within a tight
        time window -- a possible convoy or coordinated rendezvous."""
        if fastag_df is None or fastag_df.empty:
            return pd.DataFrame()
        df = fastag_df.copy()
        df["ts"] = pd.to_datetime(df["Timestamp (IST)"], errors="coerce")
        df = df.dropna(subset=["ts"]).sort_values("ts")
        window = pd.Timedelta(minutes=self.config.coordinated_window_minutes)

        rows = []
        plaza_col, veh_col = "Toll Plaza ID & Location", "Vehicle Registration"
        for plaza, group in df.groupby(plaza_col):
            group = group.sort_values("ts").reset_index(drop=True)
            for i, row in group.iterrows():
                cohort = group[(group["ts"] >= row["ts"]) & (group["ts"] <= row["ts"] + window)]
                distinct_vehicles = cohort[veh_col].unique()
                if len(distinct_vehicles) >= 2:
                    rows.append({
                        "toll_plaza": plaza, "window_start": str(row["ts"]),
                        "vehicles": sorted(map(str, distinct_vehicles)),
                        "vehicle_count": len(distinct_vehicles),
                        "case_ids": sorted(cohort["Case_ID"].astype(str).unique().tolist())
                    })
        if not rows:
            return pd.DataFrame()
        out = pd.DataFrame(rows)
        out["dedupe_key"] = out["vehicles"].apply(lambda v: tuple(v))
        return out.drop_duplicates(subset=["toll_plaza", "dedupe_key"]).drop(columns=["dedupe_key"])

    def detect_location_loops(self, fastag_df: pd.DataFrame) -> pd.DataFrame:
        """The same vehicle re-crossing the same toll plaza repeatedly inside
        a short window -- back-and-forth movement worth a second look."""
        if fastag_df is None or fastag_df.empty:
            return pd.DataFrame()
        df = fastag_df.copy()
        df["ts"] = pd.to_datetime(df["Timestamp (IST)"], errors="coerce")
        df = df.dropna(subset=["ts"])
        window = pd.Timedelta(hours=self.config.location_loop_window_hours)

        rows = []
        for (vehicle, plaza), group in df.groupby(["Vehicle Registration", "Toll Plaza ID & Location"]):
            group = group.sort_values("ts")
            times = group["ts"].tolist()
            for i in range(len(times)):
                span = [t for t in times if times[i] <= t <= times[i] + window]
                if len(span) >= self.config.location_loop_min_repeats:
                    rows.append({
                        "vehicle": vehicle, "toll_plaza": plaza, "repeat_count": len(span),
                        "window_start": str(span[0]), "window_end": str(span[-1]),
                        "case_id": str(group["Case_ID"].iloc[0])
                    })
                    break
        return pd.DataFrame(rows)

    def detect_movement_anomalies(self, fastag_df: pd.DataFrame) -> pd.DataFrame:
        """Surfaces toll crossings where the pipeline's own ANPR cross-check
        already flagged a plate mismatch (possible cloned/spoofed plate)."""
        if fastag_df is None or fastag_df.empty:
            return pd.DataFrame()
        mism = fastag_df[fastag_df["ANPR Cross-Match"].astype(str).str.upper() == "MISMATCH"].copy()
        if mism.empty:
            return pd.DataFrame()
        return mism.rename(columns={
            "Vehicle Registration": "vehicle", "Toll Plaza ID & Location": "toll_plaza",
            "Timestamp (IST)": "timestamp", "Case_ID": "case_id"
        })[["case_id", "vehicle", "toll_plaza", "timestamp"]]

    # ================================================================
    # ALERT GENERATION
    # ================================================================
    def generate_alerts(self, communication_spikes=None, financial_anomalies=None,
                         contact_chains=None, coordinated_sequences=None,
                         location_loops=None, movement_anomalies=None,
                         graph_bridge_entities=None, graph_clusters=None) -> List[Dict[str, Any]]:
        gen = []

        if communication_spikes is not None and not communication_spikes.empty:
            for _, r in communication_spikes.iterrows():
                z = _safe_float(r.get("z_score"))
                sc = _normalize_score(50 + min(z, 6) * 8)
                if sc >= self.config.alert_threshold:
                    gen.append(self._alert("COMMUNICATION_SPIKE", sc, min(90, 50 + z * 6),
                               f"{r['entity_id']} shows a contact-volume spike on {r['date']} "
                               f"({z:.1f} std devs above its own baseline).", [str(r["entity_id"])], r.to_dict()))

        if financial_anomalies is not None and not financial_anomalies.empty:
            for _, r in financial_anomalies.iterrows():
                z = _safe_float(r.get("z_score"))
                sc = _normalize_score(55 + min(z, 6) * 7)
                if sc >= self.config.alert_threshold:
                    gen.append(self._alert("FINANCIAL_ANOMALY", sc, min(92, 55 + z * 6),
                               f"Transaction of INR {r.get('amount')} from {r.get('sender')} to "
                               f"{r.get('receiver')} is a statistical outlier ({z:.1f} std devs above "
                               f"sender's baseline).", [str(r.get("sender")), str(r.get("receiver"))], r.to_dict()))

        if contact_chains is not None and not contact_chains.empty:
            for _, r in contact_chains.iterrows():
                sc = _normalize_score(60 + max(0, 10 - r.get("gap_minutes", 30)))
                if sc >= self.config.alert_threshold:
                    gen.append(self._alert("CONTACT_CHAIN", sc, 65,
                               f"Relay call pattern: {r['leg_1']} then {r['leg_2']} within "
                               f"{r['gap_minutes']} min.", r["hop_entities"], r.to_dict()))

        if coordinated_sequences is not None and not coordinated_sequences.empty:
            for _, r in coordinated_sequences.iterrows():
                sc = _normalize_score(55 + min(r.get("vehicle_count", 2), 8) * 5)
                if sc >= self.config.alert_threshold:
                    gen.append(self._alert("COORDINATED_MOVEMENT", sc, 60,
                               f"{r['vehicle_count']} distinct vehicles crossed {r['toll_plaza']} within "
                               f"{self.config.coordinated_window_minutes} min starting {r['window_start']}.",
                               r["vehicles"], r.to_dict()))

        if location_loops is not None and not location_loops.empty:
            for _, r in location_loops.iterrows():
                sc = _normalize_score(50 + min(r.get("repeat_count", 3), 10) * 5)
                if sc >= self.config.alert_threshold:
                    gen.append(self._alert("LOCATION_LOOP", sc, 60,
                               f"Vehicle {r['vehicle']} crossed {r['toll_plaza']} {r['repeat_count']} times "
                               f"between {r['window_start']} and {r['window_end']}.", [str(r["vehicle"])], r.to_dict()))

        if movement_anomalies is not None and not movement_anomalies.empty:
            for _, r in movement_anomalies.iterrows():
                gen.append(self._alert("VEHICLE_IDENTITY_MISMATCH", 88, 80,
                           f"ANPR camera reading did not match the FASTag-registered plate for "
                           f"vehicle {r['vehicle']} at {r['toll_plaza']} ({r['timestamp']}).",
                           [str(r["vehicle"])], r.to_dict()))

        if graph_bridge_entities:
            for e in graph_bridge_entities[:20]:
                gen.append(self._alert("GRAPH_BRIDGE_ENTITY", 72, 70,
                           f"{e.get('label')} structurally bridges otherwise-separate parts of the network.",
                           [e.get("id")], e))

        if graph_clusters:
            # Small clusters (~4-6 members) are usually just one FIR's own
            # informant/victim/accused/phone/vehicle -- not interesting on
            # their own. Only alert on clusters notably larger than that,
            # which signal entities pulled together across multiple cases.
            cluster_sizes = [c.get("member_count", 0) for c in graph_clusters]
            size_cutoff = max(12, int(np.percentile(cluster_sizes, 75))) if cluster_sizes else 12
            for c in graph_clusters:
                if c.get("member_count", 0) >= size_cutoff:
                    gen.append(self._alert("EMERGING_ENTITY_CLUSTER", 65, 60,
                               f"Dense cluster of {c['member_count']} linked entities detected "
                               f"(cell {c['community_id']}).",
                               [m["id"] for m in c.get("members", [])], c))

        gen.sort(key=lambda a: (a.score, a.confidence), reverse=True)
        self.alerts.extend(gen[: self.config.max_alerts])
        return [a.to_dict() for a in self.alerts[-self.config.max_alerts:]]


# ==========================================
# TOP-LEVEL ENTRY POINT
# ==========================================
def run_full_intelligence_analysis(base_dir: str = ".", save: bool = True) -> Dict[str, Any]:
    tables = load_pipeline_tables(base_dir) if load_pipeline_tables else {}
    engine = PatternIntelligenceEngine()

    communications = engine.adapt_communications(tables.get("cdr", pd.DataFrame()))
    transactions = engine.adapt_transactions(tables.get("bank", pd.DataFrame()))
    fastag = tables.get("fastag", pd.DataFrame())

    comm_spikes = engine.detect_communication_spikes(communications)
    fin_anomalies = engine.detect_financial_anomalies(transactions)
    contact_chains = engine.detect_contact_chains(communications)
    coordinated = engine.detect_coordinated_sequences(fastag)
    loops = engine.detect_location_loops(fastag)
    mismatches = engine.detect_movement_anomalies(fastag)

    # Pull bridge / cluster findings from the network-analytics report so we
    # don't recompute the graph a second time.
    bridge_entities, clusters = [], []
    analytics_path = os.path.join(base_dir, ANALYTICS_OUTPUT_PATH)
    net_report = None
    if os.path.exists(analytics_path):
        with open(analytics_path, "r", encoding="utf-8") as f:
            net_report = json.load(f)
    elif run_network_analytics:
        net_report = run_network_analytics(base_dir=base_dir, save=save)
    if net_report:
        bridge_ids = {b["source"] for b in net_report.get("critical_bridges", [])} | \
                     {b["target"] for b in net_report.get("critical_bridges", [])}
        bridge_entities = [s for s in net_report.get("top_suspects", []) if s["id"] in bridge_ids]
        clusters = net_report.get("communities", [])

    alerts = engine.generate_alerts(
        communication_spikes=comm_spikes, financial_anomalies=fin_anomalies,
        contact_chains=contact_chains, coordinated_sequences=coordinated,
        location_loops=loops, movement_anomalies=mismatches,
        graph_bridge_entities=bridge_entities, graph_clusters=clusters
    )

    report = {
        "generated_at": datetime.now().isoformat(),
        "alerts": alerts,
        "pattern_detections": {
            "communication_spikes": comm_spikes.to_dict(orient="records"),
            "financial_anomalies": fin_anomalies.to_dict(orient="records"),
            "contact_chains": contact_chains.to_dict(orient="records"),
            "coordinated_sequences": coordinated.to_dict(orient="records"),
            "location_loops": loops.to_dict(orient="records"),
            "vehicle_identity_mismatches": mismatches.to_dict(orient="records"),
        },
        "meta": {
            "alert_count": len(alerts),
            "critical_or_high_alerts": sum(1 for a in alerts if a["severity"] in ("critical", "high")),
        }
    }
    if save:
        with open(INTELLIGENCE_OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
    return report


if __name__ == "__main__":
    print("==================================================================")
    print("         MODULE 3: PATTERN INTELLIGENCE ENGINE — STANDALONE RUN    ")
    print("==================================================================")
    report = run_full_intelligence_analysis()

    print("\n[SUMMARY]")
    print(json.dumps(report["meta"], indent=2))

    print("\n[TOP ALERTS]")
    for a in report["alerts"][:10]:
        print(f"  [{a['severity'].upper():8s}] {a['alert_type']:28s} score={a['score']:5.1f}  {a['summary']}")

    for key, rows in report["pattern_detections"].items():
        print(f"\n[{key}] {len(rows)} records detected")

    print(f"\nFull report saved to: {INTELLIGENCE_OUTPUT_PATH}")
