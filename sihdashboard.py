"""
sihdashboard.py
================
UNIFIED CRIMINAL INTELLIGENCE DASHBOARD (Module 4 — the front end)

WHAT THIS FILE IS
------------------
This replaces the old prototype `dashboard.py`, which imported five files
that no longer exist in this project (`fakedatagenration.py`, `extraction.py`,
`networkanalytics.py`, `timeline.py`, `intelligence_engine.py`). This version
is wired to the ACTUAL modules that exist on disk today:

    main_investigation_pipeline.py  -> synthetic FIR / CDR / vehicle / bank /
                                        crypto dataset generation (writes CSVs)
    sihrelationship.py              -> builds one unified NetworkX graph from
                                        those CSVs (Module 3a)
    sihnetworkanalytics.py          -> centrality / bridges / communities /
                                        risk ranking + interactive HTML map
                                        (Module 3b)
    sihintelligenceengine.py        -> statistical pattern/anomaly alerts
                                        (Module 3c)
    sihtimeline.py                  -> ready-made Streamlit renderers for the
                                        Timeline and Network/Intelligence
                                        pages (reused directly, not rebuilt)

Every one of those modules already reads/writes its files relative to the
current working directory, so this dashboard runs the whole pipeline once
(cached) and everything downstream — including sihtimeline's own page
renderers — reads the same on-disk CSV/JSON/HTML/TXT outputs.

WHAT'S NEW IN THIS FILE (vs. the old prototype)
-------------------------------------------------
1. Light / Dark theme toggle with dynamic CSS token injection (cards,
   metrics, tables, Plotly charts, and the map all reflow with it).
2. A live Mumbai & Navi Mumbai case map (Plotly scattermapbox, "carto-
   positron" / "carto-darkmatter" tiles — no Mapbox token required, but one
   is used automatically if `MAPBOX_TOKEN` is set as an env var / secret),
   colour-coded by crime category, with hover tooltips and a case selector
   that highlights cross-jurisdictional linked locations (toll plazas / ANPR
   cameras / telecom towers / bank counterparties) pulled from the pipeline's
   own CDR, FASTag and Bank CSVs.
3. Side-panel crime analytics: Crime Against Women/Children breakdown +
   a network-risk gauge/breakdown built from sihnetworkanalytics' own
   risk tiers.
4. The AI Assistant (SOP/legal RAG) page is left exactly as it was — model
   wiring is intentionally left for you to finish.
"""

import os
import re
import json
import hashlib
from collections import Counter
from datetime import datetime, date, time

import numpy as np
import pandas as pd
import networkx as nx
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import streamlit.components.v1 as components

# Import the sidebar SOP/RAG function from sihsoprag.py
from sihsoprag import render_sidebar_sop_rag

# ---------------------------------------------------------------------------
# Plotly >= 6.x renamed its Mapbox-based map traces to MapLibre-based "map"
# traces (px.scatter_mapbox -> px.scatter_map, go.Scattermapbox ->
# go.Scattermap, the "mapbox_style" layout key -> "map_style"). This shim
# keeps the dashboard working on both old and new Plotly releases without
# needing a Mapbox token either way.
# ---------------------------------------------------------------------------
_USE_NEW_MAP_API = hasattr(px, "scatter_map")
_SCATTER_MAP_FN = px.scatter_map if _USE_NEW_MAP_API else px.scatter_mapbox
_SCATTER_MAP_TRACE = go.Scattermap if hasattr(go, "Scattermap") else go.Scattermapbox
_MAP_STYLE_KEY = "map_style" if _USE_NEW_MAP_API else "mapbox_style"

# ---------------------------------------------------------------------------
# REAL BACKEND PIPELINE — every import below points at a file that actually
# exists in this project (see module docstring above for what each does).
# ---------------------------------------------------------------------------
from main_investigation_pipeline import (
    generate_fir_dataset,
    generate_telecom_data,
    generate_vehicle_intelligence_and_detect_anomalies,
    generate_financial_intelligence,
    generate_unified_investigation_report,
    classify_vulnerability,
    BNS_CRIME_DATABASE,
    DISTRICTS,
)
from sihrelationship import (
    build_relationship_graph,
    load_pipeline_tables,
    summarize_graph,
    normalize_name,
)
from sihnetworkanalytics import run_network_analytics
from sihintelligenceengine import run_full_intelligence_analysis
from sihtimeline import render_timeline_page, render_network_intelligence_page

# ---------------------------------------------------------------------------
# SOP / Legal RAG assistant — UNCHANGED from the previous prototype. This is
# intentionally left as-is ("keep it like that, I'll add the model"): the
# import is wrapped so a missing Ollama/langchain setup only disables this
# one page instead of crashing the whole dashboard.
# ---------------------------------------------------------------------------
RAG_IMPORT_ERROR = None
try:
    from langchain_chroma import Chroma as _Chroma
    from langchain_ollama import OllamaEmbeddings as _OllamaEmbeddings, ChatOllama as _ChatOllama
    from langchain_core.prompts import ChatPromptTemplate as _ChatPromptTemplate
    from langchain_core.output_parsers import StrOutputParser as _StrOutputParser
except Exception as _rag_import_exc:
    RAG_IMPORT_ERROR = str(_rag_import_exc)

RAG_SCORE_THRESHOLD = 0.5
RAG_VECTOR_DB_DIR = "./legal_vector_db"
RAG_EMBED_MODEL = "nomic-embed-text"
RAG_LLM_MODEL = "deepseek-r1:1.5b"

RAG_SYSTEM_PROMPT = (
    "You are a legal investigation assistant for police officers.\n"
    "Answer ONLY using the numbered excerpts below. Do not infer, assume, or "
    "extrapolate beyond what is explicitly written.\n"
    "Write a thorough, detailed answer: explain the relevant procedure or rule "
    "step by step, cover every condition, exception, and requirement mentioned "
    "in the excerpts, and use multiple sentences or a short bulleted list rather "
    "than a one-line summary. Do not pad with filler or repetition -- every "
    "sentence should add real information from the excerpts.\n"
    "If a specific Act, Section, or Rule number appears in the excerpts, quote it "
    "exactly as written — do not paraphrase legal citations.\n"
    "After your answer, list which excerpt number(s) you used, e.g. (Source: Excerpt 2).\n"
    "If the excerpts do not contain a clear answer, you MUST respond exactly: "
    "'Information not found in database.' Do not guess or fill gaps with general knowledge.\n\n"
    "Excerpts:\n{context}\n\n"
    "Question: {question}"
)


@st.cache_resource
def load_rag_components():
    """Load embeddings, vectorstore, and LLM once per Streamlit session."""
    embeddings = _OllamaEmbeddings(model=RAG_EMBED_MODEL)
    vectorstore = _Chroma(persist_directory=RAG_VECTOR_DB_DIR, embedding_function=embeddings)
    llm = _ChatOllama(model=RAG_LLM_MODEL, num_predict=1024, num_ctx=4096, temperature=0.3)
    return vectorstore, llm


def _rag_get_context_and_docs(vectorstore, query, k=5, score_threshold=RAG_SCORE_THRESHOLD):
    results = vectorstore.similarity_search_with_relevance_scores(query, k=k)
    strong_hits = [(doc, score) for doc, score in results if score >= score_threshold]
    return strong_hits, results


def _rag_format_numbered_context(strong_hits):
    parts = []
    for i, (doc, score) in enumerate(strong_hits, start=1):
        parts.append(f"[Excerpt {i}]\n{doc.page_content}")
    return "\n\n".join(parts)


def run_rag_query(vectorstore, llm, user_query, k=5, score_threshold=RAG_SCORE_THRESHOLD):
    try:
        strong_hits, all_hits = _rag_get_context_and_docs(
            vectorstore, user_query, k=k, score_threshold=score_threshold
        )
    except Exception as e:
        return None, [], [], f"Vector search failed: {e}"

    if not strong_hits:
        return "Information not found in database.", [], all_hits

    context = _rag_format_numbered_context(strong_hits)
    prompt = _ChatPromptTemplate.from_template(RAG_SYSTEM_PROMPT)
    chain = prompt | llm | _StrOutputParser()

    try:
        raw_answer = chain.invoke({"context": context, "question": user_query})
    except Exception as e:
        return None, [], all_hits, str(e)

    clean_answer = re.sub(r"<think>.*?</think>", "", raw_answer, flags=re.DOTALL).strip()
    return clean_answer, strong_hits, all_hits


# =============================================================================
# PAGE CONFIG + THEME ENGINE
# =============================================================================
st.set_page_config(
    page_title="AI Intelligence Dashboard",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "theme_dark" not in st.session_state:
    st.session_state["theme_dark"] = True
if "pipeline_nonce" not in st.session_state:
    st.session_state["pipeline_nonce"] = 0
if "manual_fir_cases" not in st.session_state:
    st.session_state["manual_fir_cases"] = []
if "selected_map_case" not in st.session_state:
    st.session_state["selected_map_case"] = None

THEMES = {
    "dark": {
        "bg": "#0b0d17", "panel": "#131728", "panel_border": "#1e243b",
        "text": "#e2e8f0", "text_strong": "#ffffff", "muted": "#94a3b8",
        "accent": "#6366f1", "accent2": "#818cf8", "grid": "#1e293b",
        "danger": "#f43f5e", "danger_bg": "#2a1b24",
        "warn": "#f59e0b", "warn_bg": "#272115",
        "info": "#3b82f6", "info_bg": "#162032",
        "high_bg": "#2c1527",
        "map_style": "carto-darkmatter",
        "plot_template": "plotly_dark",
    },
    "light": {
        "bg": "#f8fafc", "panel": "#ffffff", "panel_border": "#e2e8f0",
        "text": "#1e293b", "text_strong": "#0f172a", "muted": "#64748b",
        "accent": "#4f46e5", "accent2": "#6366f1", "grid": "#e2e8f0",
        "danger": "#e11d48", "danger_bg": "#fff1f2",
        "warn": "#d97706", "warn_bg": "#fffbeb",
        "info": "#2563eb", "info_bg": "#eff6ff",
        "high_bg": "#fdf2f8",
        "map_style": "carto-positron",
        "plot_template": "plotly_white",
    },
}


def current_theme():
    return THEMES["dark"] if st.session_state["theme_dark"] else THEMES["light"]


def inject_theme_css(t):
    st.markdown(
        f"""
    <style>
        .stApp {{ background-color: {t['bg']}; color: {t['text']}; }}
        .block-container {{ padding-top: 1.5rem; padding-bottom: 2rem; }}

        section[data-testid="stSidebar"] {{
            background-color: {t['panel']};
            border-right: 1px solid {t['panel_border']};
        }}

        div[data-testid="stVerticalBlock"] > div[style*="flex-direction: column;"] {{
            background-color: {t['panel']};
            border-radius: 12px;
            padding: 16px;
            border: 1px solid {t['panel_border']};
        }}

        [data-testid="stMetric"] {{
            background-color: {t['panel']};
            border: 1px solid {t['panel_border']};
            border-radius: 12px;
            padding: 12px 16px;
        }}
        [data-testid="stMetricLabel"] {{ color: {t['muted']}; }}
        [data-testid="stMetricValue"] {{ color: {t['text_strong']}; }}

        .panel-title {{
            font-size: 16px; font-weight: 600; color: {t['text_strong']};
            margin-bottom: 12px; letter-spacing: 0.5px;
        }}
        .section-title {{ font-size: 22px; font-weight: 700; color: {t['text_strong']}; margin-bottom: 15px; }}

        .info-box {{
            background-color: {t['info_bg']}; border-left: 4px solid {t['info']};
            padding: 12px; border-radius: 6px; color: {t['text']}; font-size: 14px;
        }}
        .warning-box {{
            background-color: {t['warn_bg']}; border-left: 4px solid {t['warn']};
            padding: 12px; border-radius: 6px; color: {t['text']}; font-size: 14px;
        }}
        .alert-high {{
            background-color: {t['high_bg']}; border-left: 4px solid {t['danger']};
            padding: 10px; margin-bottom: 8px; border-radius: 4px;
        }}
        .alert-medium {{
            background-color: {t['warn_bg']}; border-left: 4px solid {t['warn']};
            padding: 10px; margin-bottom: 8px; border-radius: 4px;
        }}
        .alert-info {{
            background-color: {t['info_bg']}; border-left: 4px solid {t['info']};
            padding: 10px; margin-bottom: 8px; border-radius: 4px;
        }}
        .alert-title {{ font-weight: 600; color: {t['text_strong']}; font-size: 13px; }}
        .alert-text {{ font-size: 12px; color: {t['muted']}; }}

        .stDataFrame, .stTable {{ border-radius: 8px; overflow: hidden; }}
        [data-testid="stExpander"] {{
            background-color: {t['panel']}; border: 1px solid {t['panel_border']}; border-radius: 10px;
        }}
    </style>
    """,
        unsafe_allow_html=True,
    )


def style_fig(fig, t, height=380, legend=False):
    fig.update_layout(
        template=t["plot_template"],
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=t["muted"]),
        showlegend=legend,
    )
    return fig


# =============================================================================
# GEOGRAPHY — Mumbai & Navi Mumbai anchor points + deterministic fallback
# =============================================================================
MAP_CENTER = {"lat": 19.0330, "lon": 73.0297}
MAP_DEFAULT_ZOOM = 11

KNOWN_LOCATIONS = {
    "thane": (19.2183, 72.9781), "panvel": (18.9894, 73.1175),
    "belapur": (19.0176, 73.0357), "seawoods": (19.0187, 73.0175),
    "khandeshwar": (19.0245, 73.0680), "kharghar": (19.0474, 73.0669),
    "airoli": (19.1550, 72.9986), "kalyan": (19.2437, 73.1355),
    "nerul": (19.0330, 73.0297), "vashi": (19.0771, 72.9986),
    "dadar": (19.0184, 72.8425), "andheri": (19.1197, 72.8697),
    "lower parel": (19.0000, 72.8300), "vashi toll plaza": (19.0700, 72.9990),
    "khalapur": (18.7906, 73.2907), "urse": (18.7300, 73.5390),
    "khed toll plaza": (18.0167, 73.3833), "mumbai": (19.0760, 72.8777),
    "navi mumbai": (19.0330, 73.0297),
}
LAT_RANGE, LON_RANGE = (18.90, 19.25), (72.85, 73.15)

CATEGORY_COLORS = {
    "Women/Children": "#ec4899", "Violent": "#ef4444", "Property": "#f59e0b",
    "Financial": "#8b5cf6", "Cyber": "#3b82f6", "Organized": "#f97316",
    "State/Terror": "#7f1d1d", "Other": "#64748b",
}
LINKED_SOURCE_COLORS = {
    "FASTag / Toll": "#10b981", "ANPR Camera": "#22c55e",
    "Telecom Tower": "#3b82f6", "Bank Counterparty": "#a855f7",
}


def geo_for(place_name: str, salt: str = "") -> "tuple[float, float]":
    """Deterministic lat/lon for a place name: snaps to a known Mumbai/Navi
    Mumbai anchor when recognizable, otherwise scatters within the region's
    bounding box (or slightly beyond it for named expressway toll plazas)."""
    key = str(place_name or "unknown").strip().lower()
    base = None
    for known, coords in KNOWN_LOCATIONS.items():
        if known in key or key in known:
            base = coords
            break
    if base is None:
        h = int(hashlib.md5(key.encode()).hexdigest(), 16)
        base = (
            LAT_RANGE[0] + (h % 1000) / 1000 * (LAT_RANGE[1] - LAT_RANGE[0]),
            LON_RANGE[0] + ((h // 1000) % 1000) / 1000 * (LON_RANGE[1] - LON_RANGE[0]),
        )
    jseed = int(hashlib.md5(f"{key}{salt}".encode()).hexdigest(), 16)
    jlat = ((jseed % 240) - 120) / 100000.0 * 5
    jlon = (((jseed // 240) % 240) - 120) / 100000.0 * 5
    return base[0] + jlat, base[1] + jlon


def parse_gps_string(raw):
    """Parses ANPR's '19.0596 N, 72.9011 E' style coordinate strings."""
    m = re.match(r"\s*([\d.]+)\s*N\s*,\s*([\d.]+)\s*E\s*", str(raw))
    if m:
        return float(m.group(1)), float(m.group(2))
    return None


def case_type_category(case_type: str) -> str:
    return BNS_CRIME_DATABASE.get(case_type, {}).get("category", "Other")


# =============================================================================
# PIPELINE RUNNER — runs the real generation + analysis chain and writes
# every CSV/JSON/HTML/TXT output to the working directory, exactly as
# `python main_investigation_pipeline.py` would.
# =============================================================================
@st.cache_data(show_spinner="Generating FIR dataset and running the full intelligence pipeline...")
def load_pipeline_data(num_cases: int, _nonce: int = 0):
    fir_cases = generate_fir_dataset(count=num_cases)
    sdr, cdr, ipdr, case_map = generate_telecom_data(fir_cases)
    vahan, sarathi, fastag, anpr, master_veh, vehicle_anomalies = \
        generate_vehicle_intelligence_and_detect_anomalies(fir_cases, case_map)
    financial_records, financial_anomalies, case_financial_map = \
        generate_financial_intelligence(fir_cases, case_map)
    all_anomalies = vehicle_anomalies + financial_anomalies
    generate_unified_investigation_report(
        fir_cases, cdr, case_map, master_veh, all_anomalies, financial_records, case_financial_map
    )

    graph, cross_case_links = build_relationship_graph(base_dir=".")
    net_report = run_network_analytics(graph=graph, base_dir=".")
    intel_report = run_full_intelligence_analysis(base_dir=".")

    tables = load_pipeline_tables(".")
    anpr_df = pd.read_csv("ANPR_Camera_Feeds.csv") if os.path.exists("ANPR_Camera_Feeds.csv") else pd.DataFrame()
    fir_df = pd.DataFrame(fir_cases)

    return {
        "fir_cases": fir_cases,
        "fir_df": fir_df,
        "graph": graph,
        "graph_summary": summarize_graph(graph),
        "cross_case_links": cross_case_links,
        "net_report": net_report,
        "intel_report": intel_report,
        "tables": tables,
        "anpr_df": anpr_df,
    }


# =============================================================================
# SIDEBAR — navigation, theme toggle, pipeline controls
# =============================================================================
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Select View",
    ["Overview Dashboard", "FIR Registration", "Network Analysis", "Timeline & Event Correlation",
     "Suspicious Activity", "Persons and Witnesses", "Analytics", "AI Assistant"],
)

st.sidebar.divider()
st.sidebar.toggle("🌙 Dark Mode", key="theme_dark")
theme = current_theme()
inject_theme_css(theme)

st.sidebar.divider()
num_cases = st.sidebar.slider("Synthetic FIR batch size", min_value=5, max_value=40, value=20, step=5)
if st.sidebar.button("🔄 Regenerate dataset", use_container_width=True):
    st.session_state["pipeline_nonce"] += 1
    st.cache_data.clear()
    st.rerun()

# Embed the SOP / Legal assistant into the sidebar
render_sidebar_sop_rag()

with st.spinner("Loading intelligence pipeline..."):
    data = load_pipeline_data(num_cases, st.session_state["pipeline_nonce"])

fir_cases = data["fir_cases"]
fir_df = data["fir_df"]
G = data["graph"]
net_report = data["net_report"]
intel_report = data["intel_report"]
tables = data["tables"]
anpr_df = data["anpr_df"]
top_suspects = net_report.get("top_suspects", [])

st.sidebar.caption(
    f"Pipeline run: {len(fir_cases)} synthetic FIRs -> "
    f"{net_report['summary']['total_nodes']} entities -> "
    f"{net_report['summary']['total_edges']} links"
)
st.sidebar.caption(
    f"Intelligence alerts: {intel_report['meta']['alert_count']} "
    f"({intel_report['meta']['critical_or_high_alerts']} critical/high)"
)
if st.session_state["manual_fir_cases"]:
    st.sidebar.caption(f"+ {len(st.session_state['manual_fir_cases'])} manually registered FIR(s) pending pipeline ingestion")


def person_node_id(name):
    n = normalize_name(name)
    return f"PERSON::{n}" if n else None


def person_id_to_case(node_id: str):
    """Traces a PERSON:: graph node id back to the FIR case(s) and role(s) it
    appears in, using the real name (title-cased the same way the graph
    builder does)."""
    if not node_id or not node_id.startswith("PERSON::"):
        return []
    name = node_id.split("PERSON::", 1)[1]
    hits = []
    for case in fir_cases:
        for role, col in (("Informant", "Informant_Name"), ("Victim", "Victim_Name"),
                          ("Accused", "Accused_Name_Alias")):
            if normalize_name(case.get(col)) == name:
                hits.append({"case": case, "role": role})
    return hits


# =============================================================================
# PAGE 1: OVERVIEW DASHBOARD
# =============================================================================
if page == "Overview Dashboard":
    st.markdown('<div class="section-title">Case Intelligence & Network Overview</div>', unsafe_allow_html=True)

    risk_counts = Counter(s["risk_tier"] for s in top_suspects)
    critical_count = risk_counts.get("CRITICAL", 0)
    high_count = risk_counts.get("HIGH", 0)

    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("Total Entities", net_report["summary"]["total_nodes"])
    with m2:
        st.metric("Active Investigations", len(fir_cases) + len(st.session_state["manual_fir_cases"]))
    with m3:
        st.metric("Critical Bridges", net_report["summary"]["critical_bridge_count"])
    with m4:
        st.metric("Critical / High Risk Entities", critical_count + high_count, "Requires Action")

    st.write("")

    # ---- Build the case-location map dataframe -----------------------
    map_rows = []
    for c in fir_cases:
        lat, lon = geo_for(c.get("Place_of_Occurrence", "Mumbai"), salt=c["FIR_No"])
        map_rows.append({
            "FIR_No": c["FIR_No"], "Case_Type": c["Case_Type"],
            "Category": case_type_category(c["Case_Type"]),
            "District": c["District"], "Police_Station": c["Police_Station"],
            "Investigating_Officer_Name": c["Investigating_Officer_Name"],
            "Vulnerability_Category": c["Vulnerability_Category"],
            "lat": lat, "lon": lon,
        })
    map_df = pd.DataFrame(map_rows)

    left, right = st.columns([2.1, 1])

    with left:
        st.markdown('<div class="panel-title">Case Locations — Mumbai & Navi Mumbai</div>', unsafe_allow_html=True)

        mapbox_token = os.environ.get("MAPBOX_TOKEN")
        if not mapbox_token:
            try:
                mapbox_token = st.secrets.get("MAPBOX_TOKEN")
            except Exception:
                mapbox_token = None
        map_style = theme["map_style"]
        if mapbox_token and not _USE_NEW_MAP_API:
            # Official Mapbox styles ("dark"/"light") only apply to the legacy
            # Mapbox-based traces; the newer MapLibre "map" traces stick with
            # the free carto-positron/carto-darkmatter tiles regardless.
            px.set_mapbox_access_token(mapbox_token)
            map_style = "dark" if st.session_state["theme_dark"] else "light"

        fig = _SCATTER_MAP_FN(
            map_df, lat="lat", lon="lon", color="Category",
            color_discrete_map=CATEGORY_COLORS,
            hover_name="FIR_No",
            hover_data={
                "Case_Type": True, "Investigating_Officer_Name": True,
                "Police_Station": True, "District": True,
                "Vulnerability_Category": True, "lat": False, "lon": False, "Category": False,
            },
            custom_data=["FIR_No"],
            zoom=MAP_DEFAULT_ZOOM, center=MAP_CENTER, height=460,
        )
        fig.update_traces(marker=dict(size=14, opacity=0.9))
        fig.update_layout(
            **{_MAP_STYLE_KEY: map_style},
            margin=dict(l=0, r=0, t=0, b=0),
            paper_bgcolor="rgba(0,0,0,0)",
            legend=dict(orientation="h", y=-0.06, font=dict(color=theme["muted"])),
        )

        map_event = st.plotly_chart(
            fig, use_container_width=True, key="overview_map",
            on_select="rerun", selection_mode="points",
        )
        clicked_fir = None
        try:
            pts = map_event["selection"]["points"]
            if pts:
                clicked_fir = pts[0].get("customdata", [None])[0]
        except Exception:
            clicked_fir = None
        if clicked_fir:
            st.session_state["selected_map_case"] = clicked_fir

        case_options = ["— none —"] + list(map_df["FIR_No"])
        default_idx = (
            case_options.index(st.session_state["selected_map_case"])
            if st.session_state["selected_map_case"] in case_options else 0
        )
        selected_case_id = st.selectbox(
            "Select a case to highlight its cross-jurisdictional links:",
            options=case_options, index=default_idx, key="case_link_selector",
        )
        if selected_case_id != "— none —":
            st.session_state["selected_map_case"] = selected_case_id

        if st.session_state["selected_map_case"] and st.session_state["selected_map_case"] != "— none —":
            sel_id = st.session_state["selected_map_case"]
            sel_row = map_df[map_df["FIR_No"] == sel_id]
            if not sel_row.empty:
                s_lat, s_lon = float(sel_row.iloc[0]["lat"]), float(sel_row.iloc[0]["lon"])

                linked = []
                fastag_df = tables.get("fastag", pd.DataFrame())
                if not fastag_df.empty and "Case_ID" in fastag_df.columns:
                    for _, r in fastag_df[fastag_df["Case_ID"] == sel_id].iterrows():
                        plaza = str(r.get("Toll Plaza ID & Location", "Toll Plaza")).split("/")[-1].strip()
                        p_lat, p_lon = geo_for(plaza, salt=sel_id)
                        linked.append({"type": "FASTag / Toll", "label": plaza, "lat": p_lat, "lon": p_lon})
                if not anpr_df.empty and "Case_ID" in anpr_df.columns:
                    for _, r in anpr_df[anpr_df["Case_ID"] == sel_id].iterrows():
                        gps = parse_gps_string(r.get("GPS Coordinates", ""))
                        loc = str(r.get("Camera ID & Location", "ANPR Camera")).split("/")[-1].strip()
                        if gps:
                            linked.append({"type": "ANPR Camera", "label": loc, "lat": gps[0], "lon": gps[1]})
                cdr_df = tables.get("cdr", pd.DataFrame())
                if not cdr_df.empty and "Case_ID" in cdr_df.columns:
                    towers = set()
                    for _, r in cdr_df[cdr_df["Case_ID"] == sel_id].iterrows():
                        towers.add(str(r.get("First Tower Location", "")))
                        towers.add(str(r.get("Last Tower Location", "")))
                    for tw in list(towers)[:6]:
                        if tw and tw.lower() != "nan":
                            t_lat, t_lon = geo_for(tw, salt=sel_id)
                            linked.append({"type": "Telecom Tower", "label": tw, "lat": t_lat, "lon": t_lon})
                bank_df = tables.get("bank", pd.DataFrame())
                if not bank_df.empty and "Case_ID" in bank_df.columns:
                    seen_cp = set()
                    for _, r in bank_df[bank_df["Case_ID"] == sel_id].iterrows():
                        cp = str(r.get("Counterparty_Name", ""))
                        if cp and cp not in seen_cp:
                            seen_cp.add(cp)
                            b_lat, b_lon = geo_for(cp, salt=sel_id)
                            linked.append({"type": "Bank Counterparty", "label": cp, "lat": b_lat, "lon": b_lon})
                        if len(seen_cp) >= 5:
                            break

                if linked:
                    link_df = pd.DataFrame(linked)
                    highlight_fig = go.Figure(fig)
                    highlight_fig.add_trace(_SCATTER_MAP_TRACE(
                        lat=[s_lat], lon=[s_lon], mode="markers",
                        marker=dict(size=22, color="#fde047"),
                        name="Selected Case", hovertext=[sel_id], hoverinfo="text",
                    ))
                    for src_type, grp in link_df.groupby("type"):
                        line_lat, line_lon = [], []
                        for _, r in grp.iterrows():
                            line_lat.extend([s_lat, r["lat"], None])
                            line_lon.extend([s_lon, r["lon"], None])
                        highlight_fig.add_trace(_SCATTER_MAP_TRACE(
                            lat=line_lat, lon=line_lon, mode="lines",
                            line=dict(width=2, color=LINKED_SOURCE_COLORS.get(src_type, "#94a3b8")),
                            name=f"{src_type} link", hoverinfo="none",
                        ))
                        highlight_fig.add_trace(_SCATTER_MAP_TRACE(
                            lat=grp["lat"], lon=grp["lon"], mode="markers",
                            marker=dict(size=11, color=LINKED_SOURCE_COLORS.get(src_type, "#94a3b8")),
                            name=src_type, hovertext=grp["label"], hoverinfo="text",
                        ))
                    highlight_fig.update_layout(
                        **{_MAP_STYLE_KEY: map_style}, margin=dict(l=0, r=0, t=0, b=0),
                        height=460, paper_bgcolor="rgba(0,0,0,0)",
                        legend=dict(orientation="h", y=-0.06, font=dict(color=theme["muted"])),
                    )
                    st.markdown(f'<div class="panel-title">Cross-Jurisdictional Links — {sel_id}</div>', unsafe_allow_html=True)
                    st.plotly_chart(highlight_fig, use_container_width=True, config={"displayModeBar": False})
                else:
                    st.info(f"No linked FASTag / ANPR / telecom / bank records found for {sel_id} in this batch.")

    with right:
        st.markdown('<div class="panel-title">Crime Against Women & Children</div>', unsafe_allow_html=True)
        vuln_counts = Counter(c["Vulnerability_Category"] for c in fir_cases)
        vuln_df = pd.DataFrame({
            "Category": list(vuln_counts.keys()), "Count": list(vuln_counts.values())
        })
        vfig = go.Figure(data=[go.Pie(
            labels=vuln_df["Category"], values=vuln_df["Count"], hole=0.6,
            marker=dict(colors=["#ec4899", "#f472b6", "#a855f7", "#64748b"]),
            textinfo="percent",
        )])
        style_fig(vfig, theme, height=260, legend=True)
        vfig.update_layout(legend=dict(orientation="h", y=-0.15, font=dict(size=10, color=theme["muted"])))
        st.plotly_chart(vfig, use_container_width=True, config={"displayModeBar": False})

        st.markdown('<div class="panel-title">Network Risk Breakdown</div>', unsafe_allow_html=True)
        tier_order = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        tier_colors = {"LOW": "#38bdf8", "MEDIUM": "#f59e0b", "HIGH": "#f97316", "CRITICAL": "#ef4444"}
        tier_counts = [risk_counts.get(t, 0) for t in tier_order]
        gfig = go.Figure(data=[go.Bar(
            x=tier_order, y=tier_counts,
            marker=dict(color=[tier_colors[t] for t in tier_order]),
        )])
        style_fig(gfig, theme, height=200)
        gfig.update_layout(yaxis=dict(gridcolor=theme["grid"], title=""), xaxis=dict(title=""))
        st.plotly_chart(gfig, use_container_width=True, config={"displayModeBar": False})

        total_ranked = sum(risk_counts.values()) or 1
        pct_high_risk = round(100 * (critical_count + high_count) / total_ranked, 1)
        rgauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=pct_high_risk,
            number={"suffix": "%", "font": {"color": theme["text_strong"]}},
            title={"text": "High/Critical Risk Share", "font": {"color": theme["muted"], "size": 12}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": theme["muted"]},
                "bar": {"color": theme["accent"]},
                "steps": [
                    {"range": [0, 40], "color": theme["grid"]},
                    {"range": [40, 70], "color": "#f59e0b55"},
                    {"range": [70, 100], "color": "#ef444455"},
                ],
            },
        ))
        style_fig(rgauge, theme, height=200)
        st.plotly_chart(rgauge, use_container_width=True, config={"displayModeBar": False})

    st.write("")
    bl, br = st.columns([1.5, 1])
    with bl:
        st.markdown('<div class="panel-title">Key Suspects & Centrality Rankings</div>', unsafe_allow_html=True)
        if top_suspects:
            rdf = pd.DataFrame([{
                "Entity": s["label"], "Type": s["type"],
                "Degree": s["degree"], "Betweenness": s["betweenness"],
                "Risk Score": s["composite_score"], "Risk Tier": s["risk_tier"],
            } for s in top_suspects[:10]])
            st.dataframe(rdf, use_container_width=True, hide_index=True)
        else:
            st.info("No ranked suspects in this batch yet.")
    with br:
        st.markdown('<div class="panel-title">Case Category Breakdown</div>', unsafe_allow_html=True)
        cat_counts = Counter(case_type_category(c["Case_Type"]) for c in fir_cases)
        cfig = go.Figure(data=[go.Bar(
            x=list(cat_counts.keys()), y=list(cat_counts.values()),
            marker=dict(color=[CATEGORY_COLORS.get(k, "#818cf8") for k in cat_counts.keys()]),
        )])
        style_fig(cfig, theme, height=320)
        cfig.update_layout(yaxis=dict(gridcolor=theme["grid"]))
        st.plotly_chart(cfig, use_container_width=True, config={"displayModeBar": False})

# =============================================================================
# PAGE 2: FIR REGISTRATION
# =============================================================================
elif page == "FIR Registration":
    st.markdown('<div class="section-title">FIR / Case Registration</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="info-box">Enter case information below. For academic demonstrations, use fictional or '
        'sample identity information. Manually registered cases appear on the map and in Persons &amp; Witnesses '
        'immediately, but are not yet re-run through the relationship graph / network analytics pipeline until '
        'the dataset is regenerated (see sidebar).</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    st.subheader("1. Primary Details")
    c1, c2, c3 = st.columns(3)
    with c1:
        district = st.selectbox("District *", DISTRICTS)
    with c2:
        police_station = st.text_input("Police Station *", value=f"{district} PS")
    with c3:
        state = st.text_input("State *", value="Maharashtra")

    c1, c2 = st.columns(2)
    with c1:
        fir_number = st.text_input("FIR Number *", placeholder="Example: FIR/2026/0099")
    with c2:
        reporting_datetime = st.text_input("Date & Time of FIR", value=datetime.now().strftime("%Y-%m-%d %H:%M"))

    st.divider()
    st.subheader("2. Details of the Incident")
    case_type = st.selectbox("Case Type *", sorted(BNS_CRIME_DATABASE.keys()))
    c1, c2 = st.columns(2)
    with c1:
        occurrence_place = st.text_input("Place of Occurrence", placeholder="e.g. Kharghar")
    with c2:
        connectivity = st.radio("Connectivity Type", ["Unplaned", "Planed"], horizontal=True)

    st.divider()
    st.subheader("3. Complainant / Informant")
    c1, c2, c3 = st.columns(3)
    with c1:
        informant_name = st.text_input("Informant Name *")
    with c2:
        informant_contact = st.text_input("Informant Contact")
    with c3:
        informant_address = st.text_input("Informant Address")

    st.divider()
    st.subheader("4. Victim")
    c1, c2, c3 = st.columns(3)
    with c1:
        victim_name = st.text_input("Victim Name *")
    with c2:
        victim_age = st.number_input("Victim Age", min_value=0, max_value=120, value=25)
    with c3:
        victim_gender = st.selectbox("Victim Gender", ["Male", "Female"])
    victim_contact = st.text_input("Victim Contact")

    st.divider()
    st.subheader("5. Accused")
    accused_known = st.radio("Is the accused known?", ["Known", "Unknown"], horizontal=True)
    accused_name = st.text_input("Accused Name / Alias", value="Unknown Accused" if accused_known == "Unknown" else "")
    accused_address = st.text_input("Accused Address")

    st.divider()
    st.subheader("6. Investigating Officer & Narrative")
    io_name = st.text_input("Investigating Officer Name", value="Inspector (Unassigned)")
    narrative = st.text_area("Narrative / Statement", height=180, placeholder="Chronological description of the incident.")

    st.write("")
    if st.button("Register FIR", type="primary", use_container_width=True):
        if not fir_number:
            st.error("Please enter the FIR Number.")
        elif not informant_name:
            st.error("Please enter the Informant Name.")
        elif not victim_name:
            st.error("Please enter the Victim Name.")
        else:
            vulnerability = classify_vulnerability(victim_age, victim_gender, case_type)
            crime_meta = BNS_CRIME_DATABASE[case_type]
            new_case = {
                "District": district, "Police_Station": police_station, "State_UT": state,
                "FIR_No": fir_number, "Year": datetime.now().year,
                "Date_Time_of_FIR": reporting_datetime,
                "Acts_Sections": crime_meta["bns"], "Case_Type": case_type,
                "Connectivity_Type": connectivity, "Vulnerability_Category": vulnerability,
                "Place_of_Occurrence": occurrence_place or district,
                "Informant_Name": informant_name, "Informant_Contact": informant_contact,
                "Informant_Address": informant_address,
                "Victim_Name": victim_name, "Victim_Age": victim_age,
                "Victim_Gender": victim_gender, "Victim_Contact": victim_contact,
                "Accused_Status": accused_known, "Accused_Name_Alias": accused_name or "Unknown Accused",
                "Accused_Address": accused_address,
                "Investigating_Officer_Name": io_name,
                "FIR_Narrative_Statement": narrative,
            }
            st.session_state["manual_fir_cases"].append(new_case)
            st.success(f"FIR {fir_number} registered successfully and added to the working batch.")
            st.info(
                "This case now appears on the Overview map and in Persons & Witnesses. Click "
                "'🔄 Regenerate dataset' in the sidebar after adding cases you want folded into the "
                "relationship graph / network analytics for a fully consistent re-analysis."
            )

    if st.session_state["manual_fir_cases"]:
        st.write("")
        st.markdown('<div class="panel-title">Manually Registered Cases (this session)</div>', unsafe_allow_html=True)
        st.dataframe(pd.DataFrame(st.session_state["manual_fir_cases"]), use_container_width=True, hide_index=True)

# =============================================================================
# PAGE 3: NETWORK ANALYSIS
# =============================================================================
elif page == "Network Analysis":
    render_network_intelligence_page()

    st.divider()
    st.markdown('<div class="section-title">Entity Connection Explorer</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="info-box">Explore direct relationships for any person, phone, vehicle, account, '
        'location, or case node in the unified relationship graph built by sihrelationship.py.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    if G.number_of_nodes() == 0:
        st.warning("No connected entities available in the current batch.")
    else:
        node_options = sorted(G.nodes(), key=lambda n: G.nodes[n].get("label", n))
        node_labels = {n: f'{G.nodes[n].get("label", n)} ({G.nodes[n].get("type", "?")})' for n in node_options}
        selected_entity = st.selectbox("Select Entity", node_options, format_func=lambda n: node_labels[n])
        neighbors = list(G.neighbors(selected_entity))

        st.markdown(
            f'<div class="panel-title">Connections of {G.nodes[selected_entity].get("label", selected_entity)}</div>',
            unsafe_allow_html=True,
        )
        if neighbors:
            conn_df = pd.DataFrame({
                "Connected Entity": [G.nodes[n].get("label", n) for n in neighbors],
                "Entity Type": [G.nodes[n].get("type", "UNKNOWN") for n in neighbors],
                "Relationship Type(s)": [
                    ", ".join(sorted(G.get_edge_data(selected_entity, n).get("relation_types", set())))
                    for n in neighbors
                ],
            })
            st.dataframe(conn_df, use_container_width=True, hide_index=True)
        else:
            st.info("No direct connections found for this entity.")

        if selected_entity.startswith("PERSON::"):
            traces = person_id_to_case(selected_entity)
            if traces:
                with st.expander(f"🔍 Traced back to source FIR record(s)"):
                    for hit in traces:
                        c = hit["case"]
                        st.json({
                            "Role": hit["role"], "FIR No": c.get("FIR_No"),
                            "District": c.get("District"), "Case Type": c.get("Case_Type"),
                            "Date of FIR": c.get("Date_Time_of_FIR"),
                        })

        st.write("")
        pos = nx.spring_layout(G, seed=42)
        edge_x, edge_y = [], []
        for edge in G.edges():
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])
        edge_trace = go.Scatter(x=edge_x, y=edge_y, mode="lines", hoverinfo="none", line=dict(width=1, color=theme["grid"]))

        node_x, node_y, node_txt, node_colors = [], [], [], []
        type_palette = {"PERSON": "#818cf8", "PHONE": "#38bdf8", "VEHICLE": "#f59e0b",
                        "ACCOUNT": "#a855f7", "LOCATION": "#10b981", "CASE": "#ef4444"}
        for node in G.nodes():
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            attrs = G.nodes[node]
            node_txt.append(f"{attrs.get('label', node)} ({attrs.get('type', '?')})")
            node_colors.append(type_palette.get(attrs.get("type"), "#94a3b8"))

        node_trace = go.Scatter(
            x=node_x, y=node_y, mode="markers", hovertext=node_txt, hoverinfo="text",
            marker=dict(size=12, color=node_colors, line=dict(width=1, color=theme["panel_border"])),
        )
        gfig = go.Figure(data=[edge_trace, node_trace])
        style_fig(gfig, theme, height=550)
        gfig.update_layout(
            xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
            yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        )
        st.plotly_chart(gfig, use_container_width=True, config={"displayModeBar": False})

# =============================================================================
# PAGE 4: TIMELINE & EVENT CORRELATION (sihtimeline.py — reused directly)
# =============================================================================
elif page == "Timeline & Event Correlation":
    render_timeline_page()

# =============================================================================
# PAGE 5: SUSPICIOUS ACTIVITY
# =============================================================================
elif page == "Suspicious Activity":
    st.markdown('<div class="section-title">Suspicious Activity Detection</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="info-box">Structural network indicators (from sihnetworkanalytics.py) combined with '
        'statistical pattern alerts (from sihintelligenceengine.py): contact-volume spikes, financial outliers, '
        'relay/cut-out call chains, coordinated toll crossings, location loops and plate-mismatch flags.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    alert_rows = []
    for idx, s in enumerate([x for x in top_suspects if x["risk_tier"] in ("CRITICAL", "HIGH")][:12], start=1):
        pattern = "High network connectivity" if s["degree"] >= 0.3 else \
                  "Potential intermediary" if s["betweenness"] > 0.1 else "Elevated composite risk score"
        alert_rows.append({
            "Alert ID": f"NET-{idx:03d}", "Entity": s["label"], "Entity Type": s["type"],
            "Pattern": pattern, "Risk Tier": s["risk_tier"],
            "Status": "Requires Review" if s["risk_tier"] == "CRITICAL" else "Under Analysis",
        })
    for idx, b in enumerate(net_report.get("critical_bridges", [])[:6], start=len(alert_rows) + 1):
        alert_rows.append({
            "Alert ID": f"NET-{idx:03d}", "Entity": f'{b["source_label"]} ↔ {b["target_label"]}',
            "Entity Type": "BRIDGE", "Pattern": "Structural bridge connecting sub-networks",
            "Risk Tier": "MEDIUM", "Status": "Requires Review",
        })

    if alert_rows:
        st.dataframe(pd.DataFrame(alert_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No structural network alerts generated for the current batch.")

    st.write("")
    st.subheader("Pattern Intelligence Engine — Statistical Anomaly Alerts")
    pi_alerts = intel_report.get("alerts", [])
    if pi_alerts:
        severity_filter = st.multiselect(
            "Filter by severity:", options=["critical", "high", "medium", "low"],
            default=["critical", "high", "medium"],
        )
        alert_html = ""
        css_class = {"critical": "alert-high", "high": "alert-high", "medium": "alert-medium", "low": "alert-info"}
        for a in pi_alerts:
            if a["severity"] not in severity_filter:
                continue
            alert_html += (
                f'<div class="{css_class.get(a["severity"], "alert-info")}">'
                f'<div class="alert-title">[{a["severity"].upper()}] {a["alert_type"]} · score {a["score"]}</div>'
                f'<div class="alert-text">{a["summary"]}<br>Entities: {", ".join(a["entities"][:5])}</div></div>'
            )
        st.markdown(alert_html or "<div class='info-box'>No alerts match the selected severities.</div>", unsafe_allow_html=True)

        pi_df = pd.DataFrame([{
            "Alert ID": a["alert_id"], "Type": a["alert_type"], "Severity": a["severity"].capitalize(),
            "Score": a["score"], "Confidence": a["confidence"],
            "Entities": ", ".join(a["entities"][:4]), "Summary": a["summary"],
        } for a in pi_alerts])
        with st.expander("View all alerts as a table"):
            st.dataframe(pi_df, use_container_width=True, hide_index=True)
    else:
        st.info("No statistical pattern anomalies detected in the derived communication/transaction data for this batch.")

    st.caption(
        f"Intelligence engine: {intel_report['meta']['alert_count']} alerts raised, "
        f"{intel_report['meta']['critical_or_high_alerts']} critical/high severity."
    )

# =============================================================================
# PAGE 6: PERSONS AND WITNESSES
# =============================================================================
elif page == "Persons and Witnesses":
    st.markdown('<div class="section-title">Persons and Witnesses</div>', unsafe_allow_html=True)
    tabs = st.tabs(["Persons", "Entities by Type"])

    all_cases = fir_cases + st.session_state["manual_fir_cases"]
    with tabs[0]:
        person_rows = []
        for case in all_cases:
            for role, col in (("Informant", "Informant_Name"), ("Victim", "Victim_Name"),
                              ("Accused", "Accused_Name_Alias")):
                name = case.get(col)
                if not name or str(name).strip().lower() in ("", "nan", "unknown accused"):
                    continue
                pid = person_node_id(name)
                conn = G.degree(pid) if pid and pid in G else 0
                person_rows.append({
                    "Name": name, "Role": role, "Case ID": case.get("FIR_No"),
                    "District": case.get("District"), "Connections": conn,
                })
        if person_rows:
            st.dataframe(pd.DataFrame(person_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No persons available in the current batch.")

    with tabs[1]:
        type_counts = Counter(nx.get_node_attributes(G, "type").values())
        if type_counts:
            entities_df = pd.DataFrame({"Entity Type": list(type_counts.keys()), "Count": list(type_counts.values())})
            st.dataframe(entities_df, use_container_width=True, hide_index=True)
        else:
            st.info("No entities in the graph yet.")

# =============================================================================
# PAGE 7: ANALYTICS
# =============================================================================
elif page == "Analytics":
    st.markdown('<div class="section-title">Network & Case Analytics</div>', unsafe_allow_html=True)
    gs = data["graph_summary"]
    st.markdown(
        '<div class="info-box">'
        f'Relationship graph density: {gs["density"]} across {gs["total_nodes"]} nodes / {gs["total_edges"]} edges. '
        f'Cross-case suspect links found: {len([l for l in data["cross_case_links"] if l["cross_case"]])}.'
        '</div>', unsafe_allow_html=True,
    )
    st.write("")

    c1, c2 = st.columns(2)
    with c1:
        st.markdown('<div class="panel-title">Degree Centrality (Top Entities)</div>', unsafe_allow_html=True)
        if top_suspects:
            cdf = pd.DataFrame([{"Entity": s["label"], "Centrality": s["degree"]} for s in top_suspects[:15]])
            fig = go.Figure(data=[go.Bar(x=cdf["Entity"], y=cdf["Centrality"], marker=dict(color=theme["accent2"]))])
            style_fig(fig, theme, height=380)
            fig.update_layout(yaxis=dict(gridcolor=theme["grid"]))
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            st.info("No ranked entities available.")
    with c2:
        st.markdown('<div class="panel-title">District Distribution (Reported Cases)</div>', unsafe_allow_html=True)
        district_counts = Counter(c["District"] for c in fir_cases)
        fig2 = go.Figure(data=[go.Pie(
            labels=list(district_counts.keys()), values=list(district_counts.values()), hole=0.55,
            marker=dict(colors=["#6366f1", "#a855f7", "#38bdf8", "#f59e0b", "#10b981", "#ec4899", "#f97316", "#7f1d1d", "#64748b"]),
        )])
        style_fig(fig2, theme, height=380, legend=True)
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

    st.write("")
    st.markdown('<div class="panel-title">Node Type Distribution</div>', unsafe_allow_html=True)
    ntc = gs.get("node_type_counts", {})
    if ntc:
        nfig = go.Figure(data=[go.Bar(
            x=list(ntc.keys()), y=list(ntc.values()),
            marker=dict(color=[{"PERSON": "#818cf8", "PHONE": "#38bdf8", "VEHICLE": "#f59e0b",
                                 "ACCOUNT": "#a855f7", "LOCATION": "#10b981", "CASE": "#ef4444"}.get(k, "#94a3b8")
                                for k in ntc.keys()]),
        )])
        style_fig(nfig, theme, height=280)
        nfig.update_layout(yaxis=dict(gridcolor=theme["grid"]))
        st.plotly_chart(nfig, use_container_width=True, config={"displayModeBar": False})

    st.write("")
    st.markdown('<div class="panel-title">Source Data (Synthetic FIR Batch)</div>', unsafe_allow_html=True)
    source_df = fir_df[[
        "FIR_No", "District", "Case_Type", "Vulnerability_Category",
        "Connectivity_Type", "Date_Time_of_FIR", "Place_of_Occurrence",
    ]] if not fir_df.empty else pd.DataFrame()
    st.dataframe(source_df, use_container_width=True, hide_index=True)

    st.write("")
    with st.expander("Generated pipeline files (this working directory)"):
        gen_files = [
            "complete_fir_dataset.csv", "Subscriber_Detail_Records.csv", "Call_Recording.csv",
            "IP_Detail_Records.csv", "Vehicle_Summary.csv", "FASTag_Toll_Logs.csv", "ANPR_Camera_Feeds.csv",
            "Financial_Summary.csv", "Bank_Statement_Records.csv", "relationship_graph.json",
            "network_analytics_report.json", "network_map.html", "intelligence_report.json",
            "FINAL_GOVERNMENT_CASE_INVESTIGATION_REPORT.txt",
        ]
        for f in gen_files:
            exists = "✅" if os.path.exists(f) else "—"
            st.caption(f"{exists}  {f}")

# =============================================================================
# PAGE 8: AI ASSISTANT (SOP / legal RAG chatbot — unchanged)
# =============================================================================
elif page == "AI Assistant":
    st.markdown('<div class="section-title">AI Investigation Assistant</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="info-box">Ask questions about SOPs, legal rules, or evidence procedures. '
        'Answers are generated by a local RAG pipeline (Ollama + Chroma) grounded strictly in the '
        'indexed SOP/legal PDFs — the model refuses to answer if nothing relevant is indexed, '
        'instead of guessing.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    if RAG_IMPORT_ERROR:
        st.error(
            f"⚠️ RAG dependencies could not be imported: {RAG_IMPORT_ERROR}\n\n"
            "Install the required packages (`langchain-chroma`, `langchain-ollama`, `langchain-core`) "
            "in this environment to enable the AI Assistant."
        )
    else:
        with st.spinner("Initializing SOP Vector DB & Model..."):
            try:
                rag_vectorstore, rag_llm = load_rag_components()
                rag_init_error = None
            except Exception as e:
                rag_vectorstore, rag_llm = None, None
                rag_init_error = str(e)

        if rag_init_error:
            st.error(
                f"⚠️ Could not initialize the SOP model/vector DB: {rag_init_error}\n\n"
                "Check that Ollama is running and models are pulled "
                "(`ollama pull nomic-embed-text`, `ollama pull deepseek-r1:1.5b`), and that "
                "`./legal_vector_db` exists (run your indexing script on your SOP PDFs first)."
            )
        else:
            try:
                rag_doc_count = rag_vectorstore._collection.count()
            except Exception:
                rag_doc_count = None

            kb1, kb2, kb3 = st.columns(3)
            with kb1:
                st.metric("Indexed SOP Chunks", rag_doc_count if rag_doc_count is not None else "N/A")
            with kb2:
                st.metric("Embedding Model", RAG_EMBED_MODEL)
            with kb3:
                st.metric("LLM Model", RAG_LLM_MODEL)

            if rag_doc_count == 0:
                st.warning("⚠️ The legal vector database is empty. Index your SOP PDFs first.")

            st.write("")

            if "ai_assistant_chat" not in st.session_state:
                st.session_state["ai_assistant_chat"] = []

            def _process_sop_question(question: str):
                st.session_state["ai_assistant_chat"].append(
                    {"role": "user", "content": question, "strong_hits": [], "all_hits": []}
                )
                with st.spinner("Consulting SOP knowledge base..."):
                    result = run_rag_query(rag_vectorstore, rag_llm, question)

                if len(result) == 4:
                    _, _, all_hits, err = result
                    reply, strong_hits = f"⚠️ The model failed to respond: {err}", []
                else:
                    reply, strong_hits, all_hits = result

                st.session_state["ai_assistant_chat"].append(
                    {"role": "assistant", "content": reply, "strong_hits": strong_hits, "all_hits": all_hits}
                )

            if not st.session_state["ai_assistant_chat"]:
                st.caption("Try asking:")
                eq1, eq2, eq3 = st.columns(3)
                example_questions = [
                    "What are the rules for search and seizure?",
                    "What is the SOP for recording a witness statement?",
                    "What procedure applies to evidence handling?",
                ]
                for col, q in zip((eq1, eq2, eq3), example_questions):
                    with col:
                        if st.button(q, key=f"example_q_{q}", use_container_width=True):
                            _process_sop_question(q)
                            st.rerun()

            for turn in st.session_state["ai_assistant_chat"]:
                with st.chat_message(turn["role"]):
                    st.write(turn["content"])
                    if turn["role"] == "assistant" and turn.get("all_hits"):
                        used_docs = [d for d, _ in turn["strong_hits"]]
                        with st.expander(f"📚 Source excerpts ({len(turn['all_hits'])} retrieved)"):
                            for i, (doc, score) in enumerate(turn["all_hits"], start=1):
                                used = doc in used_docs
                                source = doc.metadata.get("source", "unknown file")
                                page_no = doc.metadata.get("page", "?")
                                status = "✅ used" if used else "⚠️ below threshold, not used"
                                st.caption(f"Excerpt {i} — score {score:.2f} — {status} — {source}, page {page_no}")
                                st.write(doc.page_content)
                                st.write("")

            user_query = st.chat_input("Ask a question about SOPs, legal rules, or evidence procedures...")
            if user_query:
                _process_sop_question(user_query)
                st.rerun()

            if st.session_state["ai_assistant_chat"]:
                st.write("")
                if st.button("Clear conversation", key="clear_ai_assistant_chat"):
                    st.session_state["ai_assistant_chat"] = []
                    st.rerun()

st.divider()
st.caption(
    "Prototype for academic and hackathon purposes. AI-generated insights are decision-support information "
    "and do not establish criminal guilt."
)
