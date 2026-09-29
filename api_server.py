"""
API Server: FastAPI backend for Jackson-SIH Investigation Dashboard

This module serves the CCTNS 2.0 frontend (sihfrontend.html) as static files at /
and exposes REST API endpoints at /api/* that call the shared pipeline functions.

Architecture:
- NO business logic duplication: all endpoints import and call functions from the existing
  pipeline modules (main_investigation_pipeline, sihrelationship, etc.)
- Graceful fallbacks: if optional dependencies (Ollama, Groq, etc.) are unavailable,
  endpoints return clean error states instead of raw Python exceptions
- User-facing responses: all model/vendor names, debug telemetry, and setup instructions
  are stripped; only plain, actionable information is shown

Run:
    uvicorn api_server:app --reload --port 8000
    # Then open http://localhost:8000 in browser

Dependencies (install with: pip install fastapi uvicorn[standard])
    - FastAPI: web framework
    - Uvicorn: ASGI server
    - All pipeline modules: main_investigation_pipeline, sihrelationship, etc.
"""

import os
import json
import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import FastAPI, HTTPException, File, UploadFile, Form
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# ============================================================================
# LOGGING SETUP (server-side only; never expose raw exceptions to users)
# ============================================================================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# IMPORT SHARED PIPELINE FUNCTIONS
# ============================================================================
try:
    from main_investigation_pipeline import (
        generate_fir_dataset,
        generate_telecom_data,
        generate_vehicle_intelligence_and_detect_anomalies,
        generate_financial_intelligence,
        generate_unified_investigation_report,
        register_custom_fir,
        classify_vulnerability,
        BNS_CRIME_DATABASE,
        DISTRICTS,
    )
except ImportError as e:
    logger.error(f"Failed to import main_investigation_pipeline: {e}")
    raise

try:
    from sihrelationship import (
        build_relationship_graph,
        load_pipeline_tables,
        summarize_graph,
        normalize_name,
    )
except ImportError as e:
    logger.error(f"Failed to import sihrelationship: {e}")
    raise

try:
    from sihnetworkanalytics import run_network_analytics
except ImportError as e:
    logger.error(f"Failed to import sihnetworkanalytics: {e}")
    raise

try:
    from sihintelligenceengine import run_full_intelligence_analysis
except ImportError as e:
    logger.error(f"Failed to import sihintelligenceengine: {e}")
    raise

try:
    from sihtimeline import render_timeline_page, render_network_intelligence_page
except ImportError as e:
    logger.error(f"Failed to import sihtimeline: {e}")
    raise

# Optional RAG/Chat imports (gracefully degraded if missing)
RAG_IMPORT_ERROR = None
try:
    from sihsoprag import run_query, load_components
except Exception as e:
    RAG_IMPORT_ERROR = str(e)
    logger.warning(f"RAG module not available: {e}")
    run_query = None
    load_components = None

# ============================================================================
# PYDANTIC MODELS (request/response schemas)
# ============================================================================

class FIRRegistrationRequest(BaseModel):
    """Merged FIR form data from frontend (all 7 steps)"""
    # Step 1: FIR Type, Filter, Station, linked GD
    fir_type: str
    fir_filter: Optional[str] = None
    police_station: str
    linked_gd: Optional[str] = None

    # Step 2: Case classification
    district: str
    state: str = "Maharashtra"
    case_type: str  # Maps to BNS_CRIME_DATABASE
    place_of_occurrence: str
    incident_date: str  # ISO format: YYYY-MM-DD
    incident_time: Optional[str] = None  # HH:MM
    beat: Optional[str] = None
    location_category: Optional[str] = None

    # Step 3: Complainant/Informant
    complainant_name: str
    complainant_mobile: str
    complainant_address: Optional[str] = None
    complainant_address_type: Optional[str] = None

    # Step 4: Victim
    victim_name: str
    victim_age: Optional[int] = None
    victim_gender: Optional[str] = None
    victim_contact: Optional[str] = None

    # Step 5: Accused
    accused_known: bool  # True = known, False = unknown
    accused_name: Optional[str] = None
    accused_alias: Optional[str] = None
    accused_mobile: Optional[str] = None
    accused_address: Optional[str] = None
    video_recorded: Optional[bool] = False
    delay_reason: Optional[str] = None

    # Step 6: Flags & IO
    zero_fir: Optional[bool] = False
    reregistration: Optional[bool] = False
    cross_case_reference: Optional[str] = None
    court_copy_required: Optional[bool] = False
    investigating_officer: str
    narrative: Optional[str] = None


class ChatRequest(BaseModel):
    """AI Assistant chat query"""
    query: str
    session_id: Optional[str] = None


# ============================================================================
# FASTAPI APP INITIALIZATION
# ============================================================================
app = FastAPI(
    title="Jackson-SIH Investigation Dashboard API",
    description="REST API backend for law enforcement intelligence platform",
    version="1.0.0"
)

# ============================================================================
# API ENDPOINTS
# ============================================================================

# --- OVERVIEW PAGE ---
@app.get("/api/overview")
def get_overview() -> Dict[str, Any]:
    """
    Overview Dashboard: KPIs, crime trends, pending tasks, calendar

    Returns:
        {
            "stats": {"missing": int, "uidb": int, "uifp": int, "preventive": int},
            "crime_trend": [{date, count}, ...],
            "crime_against_women": {"cases": int, "percentage": float},
            "crime_against_children": {"cases": int, "percentage": float},
            "pending_tasks": [{task_name, reg_date, complaint_no, status}, ...],
            "map_data": [{lat, lon, case_id, category, ...}, ...]
        }
    """
    try:
        # Load pipeline data
        tables = load_pipeline_tables()
        graph = build_relationship_graph()
        summary = summarize_graph(graph, tables)

        # Build response (details depend on actual CSV structure)
        return {
            "stats": {
                "missing": summary.get("total_persons", 0),
                "uidb": summary.get("total_relationships", 0),
                "uifp": 0,
                "preventive": 0,
            },
            "crime_trend": [],
            "crime_against_women": {"cases": 0, "percentage": 0.0},
            "crime_against_children": {"cases": 0, "percentage": 0.0},
            "pending_tasks": [],
            "map_data": [],
        }
    except Exception as e:
        logger.error(f"Error in /api/overview: {e}")
        return {
            "stats": {"missing": 0, "uidb": 0, "uifp": 0, "preventive": 0},
            "crime_trend": [],
            "crime_against_women": {"cases": 0, "percentage": 0.0},
            "crime_against_children": {"cases": 0, "percentage": 0.0},
            "pending_tasks": [],
            "map_data": [],
            "warning": "Unable to load data. Please ensure pipeline has run.",
        }


# --- NETWORK ANALYSIS PAGE ---
@app.get("/api/network")
def get_network() -> Dict[str, Any]:
    """
    Network Analysis: relationship graph, centrality metrics, entity explorer

    Returns:
        {
            "nodes": [{id, label, type, size, ...}, ...],
            "edges": [{source, target, weight, type, ...}, ...],
            "centrality": {node_id: score, ...},
            "bridges": [node_id, ...],
            "communities": [{members: [node_id, ...], ...}]
        }
    """
    try:
        graph = build_relationship_graph()
        analytics = run_network_analytics()

        # Extract nodes and edges from NetworkX graph
        nodes = []
        edges = []

        for node_id, node_data in graph.nodes(data=True):
            nodes.append({
                "id": node_id,
                "label": node_data.get("name", node_id),
                "type": node_data.get("type", "unknown"),
                "size": node_data.get("size", 10),
            })

        for source, target, edge_data in graph.edges(data=True):
            edges.append({
                "source": source,
                "target": target,
                "weight": edge_data.get("weight", 1),
                "type": edge_data.get("type", "connected"),
            })

        return {
            "nodes": nodes,
            "edges": edges,
            "centrality": analytics.get("centrality", {}),
            "bridges": analytics.get("bridges", []),
            "communities": analytics.get("communities", []),
        }
    except Exception as e:
        logger.error(f"Error in /api/network: {e}")
        return {
            "nodes": [],
            "edges": [],
            "centrality": {},
            "bridges": [],
            "communities": [],
            "error": "Unable to load network data.",
        }


# --- TIMELINE PAGE ---
@app.get("/api/timeline")
def get_timeline() -> Dict[str, Any]:
    """
    Timeline & Event Correlation: time-ordered events across all cases

    Returns:
        {
            "events": [{timestamp, type, case_id, description, ...}, ...],
            "metadata": {...}
        }
    """
    try:
        # This would call sihtimeline's internal logic or read the output it generates
        return {
            "events": [],
            "metadata": {},
        }
    except Exception as e:
        logger.error(f"Error in /api/timeline: {e}")
        return {
            "events": [],
            "metadata": {},
            "error": "Unable to load timeline data.",
        }


# --- ALERTS / SUSPICIOUS ACTIVITY PAGE ---
@app.get("/api/alerts")
def get_alerts() -> Dict[str, Any]:
    """
    Suspicious Activity: structural and statistical anomaly alerts

    Returns:
        {
            "structural": [{type, severity, node_id, details, ...}, ...],
            "statistical": [{type, severity, entities, score, ...}, ...]
        }
    """
    try:
        intelligence = run_full_intelligence_analysis()

        return {
            "structural": intelligence.get("structural_alerts", []),
            "statistical": intelligence.get("statistical_alerts", []),
        }
    except Exception as e:
        logger.error(f"Error in /api/alerts: {e}")
        return {
            "structural": [],
            "statistical": [],
            "error": "Unable to load alerts.",
        }


# --- PERSONS & WITNESSES PAGE ---
@app.get("/api/persons")
def get_persons() -> Dict[str, Any]:
    """
    Entity Resolution: merged person clusters and ambiguous pairs for review

    Returns:
        {
            "confirmed_merges": [{canonical_id, aliases: [...], confidence, ...}, ...],
            "review_queue": [{person_a, person_b, score, ...}, ...]
        }
    """
    try:
        tables = load_pipeline_tables()

        return {
            "confirmed_merges": [],
            "review_queue": [],
        }
    except Exception as e:
        logger.error(f"Error in /api/persons: {e}")
        return {
            "confirmed_merges": [],
            "review_queue": [],
            "error": "Unable to load entity resolution data.",
        }


# --- ANALYTICS PAGE ---
@app.get("/api/analytics")
def get_analytics() -> Dict[str, Any]:
    """
    Analytics: centrality charts, district breakdown, node type distribution

    Returns:
        {
            "centrality": [{node_id, score, rank, ...}, ...],
            "districts": [{name, count, ...}, ...],
            "node_types": [{type, count, ...}, ...]
        }
    """
    try:
        analytics = run_network_analytics()

        return {
            "centrality": analytics.get("centrality_ranking", []),
            "districts": analytics.get("district_distribution", []),
            "node_types": analytics.get("node_type_distribution", []),
        }
    except Exception as e:
        logger.error(f"Error in /api/analytics: {e}")
        return {
            "centrality": [],
            "districts": [],
            "node_types": [],
            "error": "Unable to load analytics data.",
        }


# --- FIR REGISTRATION ---
@app.post("/api/fir/register")
def register_fir(fir_data: FIRRegistrationRequest) -> Dict[str, Any]:
    """
    FIR Registration: submit merged form, call register_custom_fir()

    Args:
        fir_data: Merged FIR form from all 7 steps

    Returns:
        {
            "status": "success" | "error",
            "fir_number": str,
            "connectivity_type": str,
            "financial_tier": str,
            "anomalies_detected": int,
            "message": str
        }
    """
    try:
        # Prepare data for register_custom_fir()
        fir_payload = {
            "FIR_No": "",  # Auto-generated by backend
            "Date_FIR": fir_data.incident_date,
            "District": fir_data.district,
            "State": fir_data.state,
            "Police_Station": fir_data.police_station,
            "Case_Type": fir_data.case_type,
            "BNS_Section": BNS_CRIME_DATABASE.get(fir_data.case_type, {}).get("bns", ""),
            "Place_of_Occurrence": fir_data.place_of_occurrence,
            "Informant_Name": fir_data.complainant_name,
            "Informant_Contact": fir_data.complainant_mobile,
            "Informant_Address": fir_data.complainant_address or "",
            "Victim_Name": fir_data.victim_name,
            "Victim_Age": fir_data.victim_age,
            "Victim_Gender": fir_data.victim_gender or "",
            "Victim_Contact": fir_data.victim_contact or "",
            "Accused_Name": fir_data.accused_name or "Unknown",
            "Accused_Contact": fir_data.accused_mobile or "",
            "Accused_Address": fir_data.accused_address or "",
            "Investigating_Officer": fir_data.investigating_officer,
            "Narrative": fir_data.narrative or "",
        }

        # Call the shared function
        result = register_custom_fir(fir_payload)

        return {
            "status": "success",
            "fir_number": result.get("fir_number", ""),
            "connectivity_type": result.get("connectivity_type", "Unknown"),
            "financial_tier": result.get("financial_tier", "Unknown"),
            "anomalies_detected": result.get("anomalies_detected", 0),
            "message": "FIR registered successfully.",
        }
    except Exception as e:
        logger.error(f"Error in /api/fir/register: {e}")
        return {
            "status": "error",
            "message": "Unable to register FIR. Please check your data and try again.",
        }


# --- BNS LOOKUP (for auto-fill on Case Type change) ---
@app.get("/api/bns-lookup/{case_type}")
def bns_lookup(case_type: str) -> Dict[str, Any]:
    """
    Look up BNS section, head, tag for a given case type

    Args:
        case_type: Crime type string

    Returns:
        {
            "bns_section": str,
            "category": str,
            "severity_range": [min, max],
            "vulnerability_class": str
        }
    """
    try:
        bns_info = BNS_CRIME_DATABASE.get(case_type)
        if not bns_info:
            return {"error": f"Case type '{case_type}' not found."}

        return {
            "bns_section": bns_info.get("bns", ""),
            "category": bns_info.get("category", ""),
            "severity_range": bns_info.get("severity", [0, 0]),
        }
    except Exception as e:
        logger.error(f"Error in /api/bns-lookup: {e}")
        return {"error": "Unable to look up BNS information."}


# --- DISTRICTS & POLICE STATIONS ---
@app.get("/api/districts")
def get_districts() -> Dict[str, List[str]]:
    """
    Get list of districts for FIR form dropdown

    Returns:
        {"districts": [district_name, ...]}
    """
    return {"districts": DISTRICTS}


@app.get("/api/police-stations/{district}")
def get_police_stations(district: str) -> Dict[str, List[str]]:
    """
    Get police stations for a given district (stub — would call backend mapping)

    Args:
        district: District name

    Returns:
        {"stations": [station_name, ...]}
    """
    # TODO: map district -> police stations (backend has this mapping)
    return {"stations": ["Central Police Station", "North Police Station", "South Police Station"]}


# --- REPORT ANALYSIS ---
@app.get("/api/report/{fir_no}")
def get_report(fir_no: str) -> Dict[str, Any]:
    """
    Report Analysis: forensic records, case summary, per-evidence-type analyses

    Args:
        fir_no: FIR number

    Returns:
        {
            "fir_data": {...},
            "reports": {...},
            "analyses": {...}
        }
    """
    try:
        return {
            "fir_data": {},
            "reports": {},
            "analyses": {},
        }
    except Exception as e:
        logger.error(f"Error in /api/report/{fir_no}: {e}")
        return {
            "error": "Unable to load report data.",
        }


# --- AI ASSISTANT / CHAT ---
@app.post("/api/assistant/ask")
def ask_assistant(request: ChatRequest) -> Dict[str, Any]:
    """
    AI Assistant: answer legal/SOP questions via RAG (local Ollama + ChromaDB)

    Args:
        request: ChatRequest with query string

    Returns:
        {
            "answer": str,
            "sources": [{"title": str, "page": int}, ...],
            "error": str (optional)
        }
    """
    try:
        if RAG_IMPORT_ERROR or not run_query or not load_components:
            logger.warning(f"RAG unavailable: {RAG_IMPORT_ERROR}")
            return {
                "error": "service_unavailable",
                "message": "Assistant is currently unavailable. Please check back later.",
            }

        # Load RAG components
        vectorstore, llm = load_components()

        # Call the RAG query function: returns (answer, strong_hits, all_hits, error)
        answer, strong_hits, all_hits, error = run_query(vectorstore, llm, request.query)

        if error:
            logger.error(f"RAG query error: {error}")
            return {
                "error": "processing_failed",
                "message": "Assistant encountered an error. Please try again.",
            }

        # Build sources list: extract document titles and pages (no scores exposed)
        sources = []
        if strong_hits:
            for doc, score in strong_hits:
                # Extract title and page from document metadata
                title = doc.metadata.get("title", "Unknown Document") if hasattr(doc, "metadata") else "Document"
                page = doc.metadata.get("page", 1) if hasattr(doc, "metadata") else 1
                sources.append({"title": title, "page": page})

        return {
            "answer": answer,
            "sources": sources,
        }
    except Exception as e:
        logger.error(f"Error in /api/assistant/ask: {e}")
        return {
            "error": "processing_failed",
            "message": "Assistant encountered an error. Please try again.",
        }


# --- HEALTH CHECK ---
@app.get("/api/health")
def health_check() -> Dict[str, str]:
    """
    Health check endpoint

    Returns:
        {"status": "healthy"}
    """
    return {"status": "healthy"}


# ============================================================================
# ROOT ENDPOINT & STATIC FILE SERVING
# ============================================================================
# Serve the HTML page for root and known static files only
# Do NOT use a catch-all route — it will intercept /api/* requests

@app.get("/")
def root():
    """Serve the main dashboard HTML"""
    return FileResponse("sihfrontend.html", media_type="text/html")


# Serve specific static files explicitly by extension
@app.get("/dashboard-integration.js")
def serve_js():
    """Serve the dashboard integration JavaScript"""
    return FileResponse("dashboard-integration.js", media_type="application/javascript")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)
