"""
sihnetworkanalytics.py
=======================
NETWORK ANALYTICS LAYER
Computes network centrality, bridge entities, communities, risk scores,
and generates the interactive PyVis network visualization map.
"""

import os
import json
import logging
import networkx as nx
from typing import Dict, Any, List, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
logger = logging.getLogger("NetworkAnalytics")

ANALYTICS_OUTPUT_PATH = "network_analytics_report.json"
HTML_MAP_OUTPUT_PATH = "network_map.html"

# ---------------------------------------------------------------------------
# ENTITY TYPE COLOR PALETTE
# Kept in sync with the `type_palette` used for the Plotly network view in
# sihdashboard.py (Network Analysis / Analytics pages) so a node is the same
# color everywhere it's drawn. Add new entity types here (and mirror them in
# sihdashboard.py's type_palette / node type distribution chart) if
# sihrelationship.py starts emitting a type not listed below.
# ---------------------------------------------------------------------------
ENTITY_TYPE_COLORS = {
    "PERSON": "#818cf8",     # indigo
    "PHONE": "#38bdf8",      # blue
    "VEHICLE": "#f59e0b",    # amber
    "ACCOUNT": "#a855f7",    # purple
    "LOCATION": "#10b981",   # green (covers toll plazas / ANPR points / towers)
    "CASE": "#ef4444",       # red
}
DEFAULT_NODE_COLOR = "#94a3b8"  # slate gray fallback for any unmapped type


def get_node_color(node_type: Optional[str]) -> str:
    """Looks up the display color for a node's entity type, case-insensitively,
    falling back to a neutral gray for anything not in ENTITY_TYPE_COLORS."""
    if not node_type:
        return DEFAULT_NODE_COLOR
    return ENTITY_TYPE_COLORS.get(str(node_type).upper(), DEFAULT_NODE_COLOR)

try:
    from sihrelationship import build_relationship_graph
except ImportError:
    build_relationship_graph = None


class NetworkAnalyticsEngine:
    def __init__(self, graph: Optional[nx.Graph] = None):
        self.graph = graph if graph is not None else nx.Graph()

    def set_graph(self, graph: nx.Graph):
        self.graph = graph

    def calculate_centrality_metrics(self) -> Dict[str, Dict[str, float]]:
        """Calculates degree, betweenness, and eigenvector centrality."""
        if len(self.graph) == 0:
            return {}

        degree = nx.degree_centrality(self.graph)
        betweenness = nx.betweenness_centrality(self.graph)
        
        try:
            eigenvector = nx.eigenvector_centrality(self.graph, max_iter=1000)
        except Exception:
            eigenvector = {node: 0.0 for node in self.graph.nodes()}

        metrics = {}
        for node in self.graph.nodes():
            metrics[node] = {
                "degree": round(degree.get(node, 0.0), 4),
                "betweenness": round(betweenness.get(node, 0.0), 4),
                "eigenvector": round(eigenvector.get(node, 0.0), 4)
            }
        return metrics

    def detect_bridge_edges(self) -> List[Dict[str, Any]]:
        """Identifies critical bridge connections."""
        if len(self.graph) == 0:
            return []

        bridges = list(nx.bridges(self.graph))
        bridge_details = []

        for u, v in bridges:
            u_data = self.graph.nodes[u]
            v_data = self.graph.nodes[v]
            bridge_details.append({
                "source": u,
                "source_label": u_data.get("label", u),
                "source_type": u_data.get("type", "Unknown"),
                "target": v,
                "target_label": v_data.get("label", v),
                "target_type": v_data.get("type", "Unknown")
            })
        return bridge_details

    def detect_communities(self) -> List[Dict[str, Any]]:
        """Applies community detection to find tightly knit clusters."""
        if len(self.graph) == 0:
            return []

        try:
            communities = list(nx.community.greedy_modularity_communities(self.graph))
        except Exception:
            communities = [set(self.graph.nodes())]

        community_list = []
        for idx, comm in enumerate(communities):
            members = []
            for node in comm:
                n_data = self.graph.nodes[node]
                members.append({
                    "id": node,
                    "label": n_data.get("label", node),
                    "type": n_data.get("type", "Unknown")
                })
            community_list.append({
                "community_id": idx + 1,
                "member_count": len(members),
                "members": members
            })

        return community_list

    def rank_top_suspects(self, centrality_metrics: Dict[str, Dict[str, float]]) -> List[Dict[str, Any]]:
        """Ranks entities based on composite network centrality risk scores matching frontend schema."""
        communities = self.detect_communities()
        community_map = {}
        for comm in communities:
            c_id = comm["community_id"]
            for member in comm["members"]:
                community_map[member["id"]] = c_id

        ranked_list = []

        for node, metrics in centrality_metrics.items():
            n_data = self.graph.nodes[node]
            node_type = n_data.get("type", "Unknown")

            score = (metrics["betweenness"] * 0.5 + metrics["degree"] * 0.3 + metrics["eigenvector"] * 0.2) * 100
            if node_type in ["Person", "Phone", "Vehicle"]:
                score *= 1.25

            final_score = round(min(score, 100.0), 2)

            if final_score >= 70:
                risk_tier = "CRITICAL"
            elif final_score >= 40:
                risk_tier = "HIGH"
            elif final_score >= 15:
                risk_tier = "MEDIUM"
            else:
                risk_tier = "LOW"

            ranked_list.append({
                "id": node,
                "label": n_data.get("label", node),
                "type": node_type,
                "risk_score": final_score,
                "composite_score": final_score,
                "risk_tier": risk_tier,
                "degree": metrics["degree"],
                "betweenness": metrics["betweenness"],
                "eigenvector": metrics["eigenvector"],
                "community_id": community_map.get(node, 1)
            })

        ranked_list.sort(key=lambda x: x["composite_score"], reverse=True)
        return ranked_list

    def generate_html_network_map(self, output_filepath: str = HTML_MAP_OUTPUT_PATH):
        """Generates an interactive HTML network visualization map using PyVis,
        with each node colored by its entity `type` using ENTITY_TYPE_COLORS
        (the same palette the Plotly network views in sihdashboard.py use)."""
        clean_graph = self.graph.copy()
        for node, attrs in clean_graph.nodes(data=True):
            for k, v in list(attrs.items()):
                if isinstance(v, set):
                    clean_graph.nodes[node][k] = list(v)
                elif not isinstance(v, (str, int, float, bool, list, dict, type(None))):
                    clean_graph.nodes[node][k] = str(v)
            # Assign the display color here, before PyVis reads node attrs.
            clean_graph.nodes[node]["color"] = get_node_color(attrs.get("type"))
            # Nice-to-have: label on hover already includes type, but make it
            # explicit in the tooltip too so the color meaning is obvious.
            existing_title = clean_graph.nodes[node].get("title")
            type_label = attrs.get("type", "Unknown")
            clean_graph.nodes[node]["title"] = (
                f"{existing_title} | Type: {type_label}" if existing_title else
                f"{attrs.get('label', node)} (Type: {type_label})"
            )

        for u, v, attrs in clean_graph.edges(data=True):
            for k, val in list(attrs.items()):
                if isinstance(val, set):
                    clean_graph.edges[u, v][k] = list(val)
                elif not isinstance(val, (str, int, float, bool, list, dict, type(None))):
                    clean_graph.edges[u, v][k] = str(val)

        try:
            from pyvis.network import Network
            net = Network(height="750px", width="100%", bgcolor="#222222", font_color="white")
            net.from_nx(clean_graph)
            net.toggle_physics(True)
            net.write_html(output_filepath)
            logger.info(f"Interactive network map generated: {output_filepath}")
        except Exception as e:
            logger.warning(f"PyVis failed ({e}). Writing basic HTML fallback...")
            with open(output_filepath, "w", encoding="utf-8") as f:
                f.write("<html><body><h3>Network Map Fallback</h3></body></html>")

    def generate_case_html_network_map(
        self,
        case_id: str,
        output_filepath: Optional[str] = None,
        radius: int = 1,
    ) -> bool:
        """Generates a PyVis map scoped to ONE case/FIR, instead of the whole
        graph — for the 'load only this case's nodes/edges' request.

        How it finds the case's nodes: sihrelationship.py already creates a
        dedicated node per FIR with type == "CASE" (see ENTITY_TYPE_COLORS /
        the CASE color in the palette), directly connected to every person,
        phone, vehicle, account, and location involved in that FIR. So this
        just takes the ego graph (the case node + everything within `radius`
        hops of it) instead of the full graph.

        `case_id` is matched against both the node's id and its "label"
        attribute (case-insensitive), since depending on how
        build_relationship_graph() named CASE nodes, the FIR number might be
        the node id itself (e.g. "FIR/2026/0007") or stored in "label" with
        a different id. Adjust the matching below if your CASE node ids use
        a different convention (e.g. a "CASE::" prefix).

        Returns True if a matching case node was found and a map was
        written, False otherwise (with a logged warning) — callers can use
        this to show "no such case" in the UI instead of a silent no-op.
        """
        case_node = None
        target = str(case_id).strip().lower()
        for node, attrs in self.graph.nodes(data=True):
            if attrs.get("type") != "CASE":
                continue
            if str(node).strip().lower() == target or str(attrs.get("label", "")).strip().lower() == target:
                case_node = node
                break

        if case_node is None:
            logger.warning(f"No CASE node found matching '{case_id}' — case-scoped map not generated.")
            return False

        sub_nodes = nx.ego_graph(self.graph, case_node, radius=radius).nodes()
        subgraph = self.graph.subgraph(sub_nodes).copy()

        output_filepath = output_filepath or f"network_map_{target.replace('/', '_')}.html"
        sub_engine = NetworkAnalyticsEngine(graph=subgraph)
        sub_engine.generate_html_network_map(output_filepath=output_filepath)
        return True


def run_network_analytics(graph: Optional[nx.Graph] = None, base_dir: str = ".", save: bool = True) -> Dict[str, Any]:
    if graph is None:
        if build_relationship_graph:
            graph, _ = build_relationship_graph(base_dir=base_dir)
        else:
            graph = nx.Graph()

    engine = NetworkAnalyticsEngine(graph=graph)
    centrality = engine.calculate_centrality_metrics()
    bridges = engine.detect_bridge_edges()
    communities = engine.detect_communities()
    top_suspects = engine.rank_top_suspects(centrality)

    engine.generate_html_network_map(output_filepath=os.path.join(base_dir, HTML_MAP_OUTPUT_PATH))

    report = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_nodes": graph.number_of_nodes(),
            "total_edges": graph.number_of_edges(),
            "critical_bridge_count": len(bridges),
            "community_count": len(communities)
        },
        "top_suspects": top_suspects[:25],
        "critical_bridges": bridges,
        "communities": communities
    }

    if save:
        report_path = os.path.join(base_dir, ANALYTICS_OUTPUT_PATH)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)

    return report


if __name__ == "__main__":
    print("Running Network Analytics...")
    run_network_analytics()
    print("Done!")
