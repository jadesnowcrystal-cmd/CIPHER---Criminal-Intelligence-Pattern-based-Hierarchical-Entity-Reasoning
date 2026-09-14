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
    register_custom_fir,
    classify_vulnerability,
    BNS_CRIME_DATABASE,
    DISTRICTS,
    NON_MEDIA_FORENSIC_UNDER_CONSTRUCTION,
    MULTIMEDIA_FORENSIC_UNDER_CONSTRUCTION,
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

# ---------------------------------------------------------------------------
# FIR PDF UPLOAD & NLP EXTRACTION — reads an uploaded FIR document, then asks
# an LLM (Groq's llama-3.3-70b-versatile) to translate it and pull out the
# structured fields the registration form needs. Guarded the same way as the
# RAG imports above: a missing `pypdf`/`requests` install only disables the
# PDF-upload tab, it never crashes the rest of the dashboard.
# ---------------------------------------------------------------------------
PDF_IMPORT_ERROR = None
try:
    import pypdf
except Exception as _pdf_import_exc:
    PDF_IMPORT_ERROR = str(_pdf_import_exc)

# -----------------------------------------------------------------------
# OCR fallback — ONLY thing that can actually fix the broken-font-cmap
# corruption (e.g. "मुंबई रेã वे" instead of "मुंबई रेल्वे"). pypdf reads the
# PDF's embedded text layer, which on these auto-generated NCRB forms maps
# to the wrong Unicode codepoints for machine-printed Devanagari. The
# glyphs still *draw* correctly on screen (that's why the page looks fine
# visually) — it's only the underlying character codes that are wrong. No
# LLM, local or hosted, can recover that; you have to bypass the text
# layer entirely and read the rendered pixels instead.
#
# Install: pip install pdf2image pytesseract
#          + the tesseract binary itself, with Marathi/Hindi language data:
#          Ubuntu/Debian: sudo apt install tesseract-ocr tesseract-ocr-mar tesseract-ocr-hin poppler-utils
#          macOS:         brew install tesseract tesseract-lang poppler
# Guarded the same way as every other optional dependency in this file —
# if it's missing, the dashboard just falls back to the pypdf text layer
# for those fields (still garbled, but nothing crashes).
# -----------------------------------------------------------------------
OCR_IMPORT_ERROR = None
try:
    import pytesseract
    from pdf2image import convert_from_bytes
except Exception as _ocr_import_exc:
    OCR_IMPORT_ERROR = str(_ocr_import_exc)

# -----------------------------------------------------------------------
# GROQ API — replaces the local Ollama call for FIR field extraction only.
# The sidebar "AI Assistant" SOP/RAG page still uses local Ollama
# (RAG_LLM_MODEL further down) — untouched, separate concern. This is
# free-tier, hosted, no local model/RAM needed. Get a key at
# https://console.groq.com/keys and set it as an environment variable
# (see the run steps) — never hardcode it in this file.
# -----------------------------------------------------------------------
GROQ_IMPORT_ERROR = None
try:
    from groq import Groq as _Groq
except Exception as _groq_import_exc:
    GROQ_IMPORT_ERROR = str(_groq_import_exc)

GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
FIR_EXTRACTION_LLM_MODEL = "llama-3.3-70b-versatile"


def _get_groq_client():
    """Returns a Groq client, or None + reason if unavailable. Cached per
    Streamlit session so we don't rebuild it on every rerun."""
    if GROQ_IMPORT_ERROR:
        return None, f"`groq` package not installed: {GROQ_IMPORT_ERROR}"
    if not GROQ_API_KEY:
        return None, "GROQ_API_KEY environment variable is not set."
    try:
        return _Groq(api_key=GROQ_API_KEY), None
    except Exception as e:
        return None, f"Could not initialize Groq client: {e}"


def render_and_ocr_page(pdf_bytes, page_number=0, lang="mar+hin+eng"):
    """Rasterizes one PDF page to an image and OCRs it directly — this is
    what actually reads the correct Devanagari, bypassing pypdf's broken
    text layer entirely. Returns "" on any failure (missing deps, missing
    tesseract binary, bad page index) rather than raising, so a caller can
    always fall back to the regex/pypdf fields."""
    if OCR_IMPORT_ERROR:
        return ""
    try:
        pages = convert_from_bytes(pdf_bytes, dpi=300, first_page=page_number + 1, last_page=page_number + 1)
        if not pages:
            return ""
        return pytesseract.image_to_string(pages[0], lang=lang)
    except Exception:
        return ""

FIR_EXTRACTION_SCHEMA_FIELDS = [
    "District", "Police_Station", "Case_Type", "Acts_Sections", "Place_of_Occurrence",
    "Informant_Name", "Informant_Contact", "Informant_Address",
    "Victim_Name", "Victim_Contact", "Accused_Name_Alias", "Accused_Contact",
    "Accused_Address", "FIR_Narrative_Statement",
]





def _parse_llm_json_loose(text):
    """
    Small local models frequently emit JSON that's *almost* valid but breaks
    Python's strict json.loads(), most commonly because a text field contains
    a literal newline/tab instead of an escaped "\\n"/"\\t". This tries
    progressively more forgiving parse strategies instead of failing outright.
    """
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(text, strict=False)
    except json.JSONDecodeError:
        pass
    no_trailing_commas = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(no_trailing_commas, strict=False)
    except json.JSONDecodeError:
        pass
    repaired = []
    in_string = False
    escape_next = False
    for ch in no_trailing_commas:
        if escape_next:
            repaired.append(ch)
            escape_next = False
            continue
        if ch == "\\" and in_string:
            repaired.append(ch)
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            repaired.append(ch)
            continue
        if in_string and ch == "\n":
            repaired.append("\\n")
        elif in_string and ch == "\r":
            repaired.append("\\r")
        elif in_string and ch == "\t":
            repaired.append("\\t")
        else:
            repaired.append(ch)
    return json.loads("".join(repaired))


# =============================================================================
# REGEX-FIRST FIELD EXTRACTION
# -----------------------------------------------------------------------------
# These NCRB I.I.F.-I FIR forms are auto-generated with a very consistent
# bilingual layout: an English label, a parenthetical vernacular translation
# of that label, a colon, then the actual value. The English labels extract
# cleanly and reliably through pypdf every time; some auto-filled Devanagari
# VALUES (e.g. a machine-printed District name) come from a subsetted font
# with a broken character map and extract as genuinely corrupted Unicode —
# no amount of prompting an LLM can "translate" scrambled codepoints back to
# real text. Human-typed fields (informant name, phone, address, narrative),
# by contrast, extract correctly.
#
# So: pull every field we can locate structurally with regex FIRST — this is
# deterministic, instant, and can't hallucinate. Only hand the LLM a small,
# focused job afterwards (translate/transliterate a few short snippets and
# names + fully translate the narrative + classify the case type, deferring
# to the deterministic section-code lookup when one exists). If the LLM is
# slow, unavailable, or misbehaves, we still return everything regex found —
# including Name and Phone, which is what actually matters most.
# =============================================================================

# A few ultra-common fixed phrases that appear near-verbatim on almost every
# Indian FIR — safe to hardcode, no LLM guesswork needed.
_COMMON_TERM_TRANSLATIONS = {
    "अनोळखी": "Unknown",
    "अज्ञात": "Unknown",
}


def _translate_common_terms(text):
    if not text:
        return text
    for hi, en in _COMMON_TERM_TRANSLATIONS.items():
        text = text.replace(hi, en)
    return text.strip()


def _label_value(text, label_pattern):
    """Find 'Label (vernacular translation): VALUE' — tolerant of the
    parenthetical and colon being split across several lines, which pypdf
    does constantly on these forms — and return the first non-empty line
    after the colon."""
    pattern = label_pattern + r"\s*\n?\(.*?\)\s*:\s*"
    m = re.search(pattern, text, re.DOTALL)
    if not m:
        return ""
    for line in text[m.end():].split("\n"):
        line = line.strip()
        if line:
            return line
    return ""


def _extract_acts_section(text):
    """Pulls the Act name + Section code out of the item-2 table."""
    idx = text.find("Sections")
    if idx == -1:
        return "", ""
    lines = text[idx:].split("\n")
    i = 0
    while i < len(lines) and not re.match(r"^\s*\d+\s*$", lines[i]):
        i += 1
    i += 1  # skip the serial-number row
    act_lines, section_code = [], ""
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue
        if re.match(r"^\d{1,4}\s*(\(\d{1,3}\))?$", line):
            section_code = line
            break
        act_lines.append(line)
    return " ".join(act_lines), section_code


def _extract_current_address(text):
    """Pulls row 1 (current address) out of the informant's address table."""
    m = re.search(r"Address\s*\n?\(.*?\)::\s*", text, re.DOTALL)
    if not m:
        return ""
    lines = text[m.end():].split("\n")
    i = 0
    while i < len(lines) and not re.match(r"^\s*\d+\s*$", lines[i]):
        i += 1
    i += 1  # skip serial number
    if i < len(lines):
        i += 1  # skip the address-type label (e.g. "current address")
    addr_lines = []
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if re.match(r"^\s*\d+\s*$", line):
            break
        if line:
            addr_lines.append(line)
    return " ".join(addr_lines)


def _extract_accused_name(text):
    """Pulls the first accused's Name from the item-7 table."""
    idx = text.find("Details of known")
    if idx == -1:
        return ""
    m = re.search(r"Present Address\(.*?\)\)\s*", text[idx:], re.DOTALL)
    if not m:
        return ""
    lines = [l.strip() for l in text[idx:][m.end():].split("\n") if l.strip()]
    return lines[1] if len(lines) > 1 else ""


def _extract_narrative(text):
    """Pulls the full item-12 narrative statement (raw script)."""
    m = re.search(r"First Information contents\s*\n?\(.*?\)\s*:\s*", text, re.DOTALL)
    if not m:
        return ""
    rest = text[m.end():]
    end = re.search(r"\n\s*13\.", rest)
    narrative = rest[:end.start()] if end else rest[:1500]
    return re.sub(r"\s+", " ", narrative).strip()


def _extract_mobile(text):
    val = _label_value(text, r"Mobile")
    if val:
        return val
    # Fallback: any phone-looking digit run near "Phone number"/"Mobile".
    m = re.search(r"(\+?\d[\d\-\s]{8,14}\d)", text)
    return m.group(1).strip() if m else ""


def _regex_extract_fir_fields(raw_text):
    """Deterministic, LLM-free extraction of every field this form's layout
    makes locatable. Always returns a dict with all schema keys (possibly
    empty strings) — this is the reliable floor the LLM enrichment builds on
    top of, never something the LLM's failure can erase."""
    district = _label_value(raw_text, r"District\s*\n")
    police_station = _label_value(raw_text, r"P\.S\.")
    place_of_occurrence = _label_value(raw_text, r"\(b\) Address")
    informant_name = _label_value(raw_text, r"\(a\)\s*\nName")
    informant_contact = _extract_mobile(raw_text)
    informant_address = _extract_current_address(raw_text)
    act_name, section_code = _extract_acts_section(raw_text)
    acts_sections = (f"{act_name} Section {section_code}".strip()
                     if section_code else act_name)
    accused_name = _translate_common_terms(_extract_accused_name(raw_text))
    narrative = _extract_narrative(raw_text)

    return {
        "District": district,
        "Police_Station": police_station,
        "Case_Type": "",  # needs judgement — left for the LLM enrichment step
        "Acts_Sections": acts_sections,
        "Place_of_Occurrence": place_of_occurrence,
        "Informant_Name": informant_name,
        "Informant_Contact": informant_contact,
        "Informant_Address": informant_address,
        # This form has no separate "victim" section for theft-type FIRs —
        # the informant IS the victim. Default to that; a real victim
        # section (if the form has one) would override this.
        "Victim_Name": informant_name,
        "Victim_Contact": informant_contact,
        "Accused_Name_Alias": accused_name,
        "Accused_Contact": "",
        "Accused_Address": "",
        "FIR_Narrative_Statement": narrative,
    }


def _looks_like_garbled_devanagari(s):
    """Detects TWO different corruption patterns seen from pypdf on these
    forms — a model swap fixes neither, only OCR does:
      1. Broken font-cmap: odd Latin lookalike glyphs mixed into Devanagari
         (e.g. 'मǕंबई रेã वे').
      2. Matra/anusvara reordering: real Devanagari codepoints, but a
         combining mark (ं, ा, े, etc.) lands after the wrong consonant,
         often with a stray space (e.g. 'अंधेरी' extracted as 'अधं ेरी').
         This keeps every original character, just out of order, so it
         does NOT contain any Latin-lookalike glyph and pattern #1 alone
         misses it entirely — which is why PS/Place kept failing silently.
    """
    if not s:
        return False
    suspicious_chars = set("ǕãȨĤǒȭÛĐ")
    if any(ch in suspicious_chars for ch in s):
        return True
    # Pattern 2: a combining mark (Devanagari vowel sign/anusvara/etc.)
    # preceded by whitespace, or immediately followed by whitespace then
    # another combining mark run — real, correctly-ordered Devanagari text
    # never puts a space directly before/after a bare combining mark.
    if re.search(r"[\u0900-\u0903\u093A-\u094F\u0955-\u0963]\s", s) and re.search(r"\s[\u0900-\u0903\u093A-\u094F]", s):
        return True
    return False


def _fuzzy_match_canonical(value, choices, cutoff=0.55):
    """Matches a possibly-corrupted extracted string against a fixed,
    known vocabulary (district names, police station names, etc.) by
    similarity rather than exact equality. This is the practical fix for
    matra-reordering corruption: the corrupted string still shares almost
    every character with the correct one, just shuffled, so a similarity
    match finds it even when an exact `in choices` check (see the old
    `DISTRICTS.index(...) if x in DISTRICTS else 0` pattern) fails and
    silently falls back to whatever option happens to sit at index 0.
    Returns the best match, or "" if nothing clears the cutoff."""
    if not value or not choices:
        return ""
    import difflib
    matches = difflib.get_close_matches(value, choices, n=1, cutoff=cutoff)
    return matches[0] if matches else ""


# Reverse lookup built from your OWN BNS_CRIME_DATABASE (each entry already
# stores its section under the "bns" key) — e.g. "Section 303(2)" -> pulls
# out "303" -> maps back to whichever Case_Type key that entry belongs to.
# This makes Case_Type classification a DETERMINISTIC TABLE LOOKUP off the
# numeric section code (which extracts perfectly via regex — it's plain
# digits, nothing Devanagari to corrupt) instead of an LLM guess. BNS 2023
# is only ~2 years old; even a 70B model is unreliable mapping section
# numbers to offense categories from general knowledge, which is exactly
# how you got "Acid Attack" out of a mobile-phone-theft narrative.
def _build_bns_section_lookup():
    lookup = {}
    for case_type, info in BNS_CRIME_DATABASE.items():
        m = re.search(r"\b(\d{1,3})\b", str(info.get("bns", "")))
        if m:
            lookup[m.group(1)] = case_type
    return lookup


BNS_SECTION_TO_CASE_TYPE = _build_bns_section_lookup()


def _case_type_from_section_code(section_code):
    """section_code looks like '303(2)' or '303' — pull the base section
    number and look it up deterministically. Returns "" if no match, so
    the caller can still fall back to the LLM for genuinely novel codes
    not yet in BNS_CRIME_DATABASE."""
    if not section_code:
        return ""
    m = re.search(r"\b(\d{1,3})\b", section_code)
    return BNS_SECTION_TO_CASE_TYPE.get(m.group(1), "") if m else ""


def extract_fir_fields_local(uploaded_file):
    """
    Reads the uploaded PDF's text, extracts every locatable field with
    regex FIRST (deterministic, always correct when the layout matches,
    never dependent on any model), then calls the Groq API to do the
    residual job regex can't: translate/transliterate short native-script
    snippets and names into English, fully translate the narrative (not a
    summary), and classify Case_Type — deferring to the deterministic
    BNS-section-code lookup whenever one exists. Returns
    (extracted_dict, error_message) — exactly one of the two is None.
    If the LLM step fails for any reason, the regex-extracted fields
    (Name, Phone, Address, etc.) are still returned rather than lost.
    Connectivity_Type is deliberately NOT part of the schema: the pipeline
    always derives it from Case_Type / Acts_Sections / occurrence spread
    (see determine_connectivity_type() in main_investigation_pipeline.py).
    """
    try:
        pdf_bytes = uploaded_file.getvalue() if hasattr(uploaded_file, "getvalue") else uploaded_file.read()
        reader = pypdf.PdfReader(uploaded_file)
        raw_text = "".join(page.extract_text() or "" for page in reader.pages)
    except Exception as e:
        return None, f"Could not open this PDF: {e}"

    if not raw_text.strip():
        return None, "No readable text found in this PDF — it may be a scanned image without OCR text."

    fields = _regex_extract_fir_fields(raw_text)

    # DETERMINISTIC Case_Type — try the section-code table lookup first.
    # section_code was captured separately inside _extract_acts_section();
    # re-derive it here from the combined Acts_Sections string since that's
    # all _regex_extract_fir_fields returns.
    _section_match = re.search(r"(\d{1,3})(?:\(\d{1,3}\))?\s*$", fields.get("Acts_Sections", ""))
    if _section_match:
        _looked_up_case_type = _case_type_from_section_code(_section_match.group(0))
        if _looked_up_case_type:
            fields["Case_Type"] = _looked_up_case_type

    # OCR REPAIR PASS — the District/Police_Station/Place_of_Occurrence
    # values above come from pypdf's text layer, which on these forms is
    # frequently a scrambled font-cmap for machine-printed Devanagari (see
    # _looks_like_garbled_devanagari). If any of them trip that check,
    # re-read just page 1 as an image and OCR it directly, then re-run the
    # same regexes against the OCR'd text. This is what actually fixes the
    # corruption — no LLM step can. Silently no-ops if pytesseract/pdf2image
    # aren't installed, or if OCR doesn't do any better.
    garbled_keys = [k for k in ("District", "Police_Station", "Place_of_Occurrence")
                     if _looks_like_garbled_devanagari(fields.get(k, ""))]
    if garbled_keys and not OCR_IMPORT_ERROR:
        ocr_text = render_and_ocr_page(pdf_bytes, page_number=0)
        if ocr_text.strip():
            ocr_fields = _regex_extract_fir_fields(ocr_text)
            for k in garbled_keys:
                if ocr_fields.get(k) and not _looks_like_garbled_devanagari(ocr_fields[k]):
                    fields[k] = ocr_fields[k]

    groq_client, groq_error = _get_groq_client()
    if groq_error:
        # No Groq access — still return everything regex found (Name/Phone/
        # Address/etc. are already correct English-or-native-script values),
        # just without translation/classification.
        if fields.get("District"):
            best = _fuzzy_match_canonical(fields["District"], DISTRICTS)
            fields["District"] = best if best else ""
        return {k: v for k, v in fields.items() if str(v).strip()}, None

    # Build a focused enrichment prompt: short field snippets + names to
    # translate/transliterate, plus the full narrative for FULL English
    # translation (not a summary — the earlier one-sentence summary dropped
    # details like the phone model/IMEI/amount that investigators need).
    to_translate = {
        "District": fields["District"],
        "Police_Station": fields["Police_Station"],
        "Place_of_Occurrence": fields["Place_of_Occurrence"],
        "Informant_Address": fields["Informant_Address"],
        "Acts_Sections": fields["Acts_Sections"],
        "Informant_Name": fields["Informant_Name"],
        "Victim_Name": fields["Victim_Name"],
        "Accused_Name_Alias": fields["Accused_Name_Alias"],
    }
    to_translate = {k: v for k, v in to_translate.items() if v}

    enrich_prompt = (
        "Translate each of these short Indian police-form field values from "
        "Hindi/Marathi into natural English. For Informant_Name, Victim_Name "
        "and Accused_Name_Alias, transliterate the person's name into its "
        "standard English spelling (e.g. 'सबीर अली शेख' -> 'Sabir Ali "
        "Shaikh') rather than translating word-for-word; for place names, "
        "use the standard English spelling (e.g. 'Andheri', 'Mumbai'). Also "
        "translate the full narrative into clear, complete English — this "
        "must be a full translation, NOT a summary: keep every fact "
        "(dates, times, amounts, phone/IMEI numbers, descriptions) exactly "
        "as stated, just in English. Also pick the single best Case_Type "
        f"from this exact list: {', '.join(sorted(BNS_CRIME_DATABASE.keys()))}.\n\n"
        "Respond with ONLY a valid JSON object with exactly these keys: "
        + ", ".join(f'"{k}"' for k in list(to_translate.keys()) + ["Case_Type", "Narrative_English"])
        + ". No markdown fences, no commentary.\n\n"
        f"FIELDS TO TRANSLATE:\n{json.dumps(to_translate, ensure_ascii=False, indent=2)}\n\n"
        f"NARRATIVE TO TRANSLATE IN FULL:\n{fields['FIR_Narrative_Statement'][:2500]}"
    )

    extracted_llm = None
    last_error = None
    last_raw_response = ""
    try:
        completion = groq_client.chat.completions.create(
            model=FIR_EXTRACTION_LLM_MODEL,
            temperature=0.1,
            max_tokens=1800,
            messages=[{"role": "user", "content": enrich_prompt}],
        )
        raw_response = completion.choices[0].message.content
        last_raw_response = raw_response

        clean_response = re.sub(r"<think>.*?</think>", "", raw_response, flags=re.DOTALL).strip()
        clean_response = re.sub(r"^```(?:json)?|```$", "", clean_response.strip(), flags=re.MULTILINE).strip()
        match = re.search(r"\{.*\}", clean_response, re.DOTALL)
        json_str = match.group(0) if match else clean_response

        try:
            extracted_llm = _parse_llm_json_loose(json_str)
        except Exception as e:
            last_error = e
    except Exception as e:
        # Network error, invalid/expired key, rate limit, etc. — fall back
        # to the regex fields below rather than failing the whole upload.
        last_error = e

    # Merge: LLM translations enrich the regex floor, but never replace it
    # with something empty/nonsensical, and regex values are the guaranteed
    # fallback if the LLM failed entirely.
    _case_type_is_deterministic = bool(fields.get("Case_Type")) and (
        _section_match is not None and _case_type_from_section_code(_section_match.group(0)) == fields.get("Case_Type")
    )
    if extracted_llm:
        for key in ("District", "Police_Station", "Place_of_Occurrence", "Informant_Address", "Acts_Sections",
                    "Informant_Name", "Victim_Name", "Accused_Name_Alias"):
            val = str(extracted_llm.get(key, "")).strip()
            # Guard: an address field is never allowed to become an email.
            # This is exactly the "-851502 @ gmail.com" bug — a weak model
            # confusing the informant's email with their postal address.
            # Reject and keep whatever regex already found instead.
            if key == "Informant_Address" and ("@" in val or "gmail" in val.lower()):
                continue
            if val:
                fields[key] = val
        # Only trust the LLM's Case_Type guess when we had no deterministic
        # section-code match — a table lookup off a clean numeric code beats
        # an LLM guessing offense categories from a ~2-year-old legal code.
        if not _case_type_is_deterministic:
            case_type = str(extracted_llm.get("Case_Type", "")).strip()
            if case_type in BNS_CRIME_DATABASE:
                fields["Case_Type"] = case_type
        narrative_en = str(extracted_llm.get("Narrative_English", "")).strip()
        if narrative_en:
            fields["FIR_Narrative_Statement"] = narrative_en
    # else: last_error / last_raw_response are available for debugging but
    # we deliberately do NOT fail the whole extraction — regex fields stand.

    # District fuzzy-match — the form's dropdown needs an EXACT string match
    # against DISTRICTS to pre-select anything (see _render_fir_form's
    # `DISTRICTS.index(prefill["District"]) if ... in DISTRICTS else 0`).
    # Any leftover corruption, or even a slightly different phrasing than
    # your canonical list, silently falls back to index 0 ("Thane") instead
    # of erroring — which is exactly what you saw. Fuzzy-match first so the
    # dropdown gets pre-selected correctly whenever a close-enough option
    # exists, and only leaves the field blank (honest "we don't know") when
    # nothing is close.
    if fields.get("District"):
        best = _fuzzy_match_canonical(fields["District"], DISTRICTS)
        fields["District"] = best if best else ""

    return {k: v for k, v in fields.items() if str(v).strip()}, None



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
if "fir_refresh_nonce" not in st.session_state:
    st.session_state["fir_refresh_nonce"] = 0
if "fir_extracted_data" not in st.session_state:
    st.session_state["fir_extracted_data"] = {}
if "fir_last_registration" not in st.session_state:
    st.session_state["fir_last_registration"] = None
if "selected_map_case" not in st.session_state:
    st.session_state["selected_map_case"] = None
if "analysis_uploads" not in st.session_state:
    # Keyed by "{case_id}||{tab_name}||{module_name}" -> list of
    # {"name", "size", "uploaded_at"} dicts. Session-only (in-memory) store
    # for files uploaded through each forensic tab's Analysis sub-tab.
    st.session_state["analysis_uploads"] = {}

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

        .subsection-title {{
            font-size: 15px; font-weight: 600; color: {t['muted']};
            text-transform: uppercase; letter-spacing: 0.8px; margin: 4px 0 14px 0;
        }}
        .construction-card {{
            background-color: {t['panel']}; border: 1.5px dashed {t['panel_border']};
            border-radius: 14px; padding: 48px 24px; text-align: center; margin-top: 6px;
        }}
        .construction-icon {{ font-size: 42px; margin-bottom: 12px; }}
        .construction-title {{
            font-size: 17px; font-weight: 700; color: {t['text_strong']}; margin-bottom: 6px;
        }}
        .construction-sub {{ font-size: 13px; color: {t['muted']}; margin-bottom: 16px; }}
        .construction-pill {{
            display: inline-block; background-color: {t['warn_bg']}; color: {t['warn']};
            border: 1px solid {t['warn']}; border-radius: 999px; padding: 4px 14px;
            font-size: 12px; font-weight: 600; letter-spacing: 0.5px;
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
def generate_base_pipeline_data(num_cases: int, _nonce: int = 0):
    """
    Generates a brand-new synthetic batch and OVERWRITES every pipeline CSV.
    Cached on (num_cases, _nonce) -- only reruns when the batch-size slider
    changes or the sidebar "Regenerate dataset" button bumps the nonce, so it
    is never triggered by a manual/PDF FIR registration.
    """
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
    return True


@st.cache_data(show_spinner="Refreshing relationship graph & network analytics...")
def build_analytics_from_disk(_base_nonce: int, _refresh_nonce: int):
    """
    Rebuilds the relationship graph / network analytics / intelligence report
    purely from whatever is currently in the CSVs on disk. It never calls the
    batch generators, so it's safe (and cheap) to rerun right after
    register_custom_fir() appends a new FIR's records -- the synthetic batch
    already on disk is left untouched.

    Cache key includes both nonces: a base-pipeline regenerate invalidates it
    (new data on disk) and so does a fresh FIR registration.
    """
    graph, cross_case_links, entity_resolution = build_relationship_graph(base_dir=".")
    net_report = run_network_analytics(graph=graph, base_dir=".")
    intel_report = run_full_intelligence_analysis(base_dir=".")

    tables = load_pipeline_tables(".")
    anpr_df = pd.read_csv("ANPR_Camera_Feeds.csv") if os.path.exists("ANPR_Camera_Feeds.csv") else pd.DataFrame()
    fir_df = pd.read_csv("complete_fir_dataset.csv") if os.path.exists("complete_fir_dataset.csv") else pd.DataFrame()
    fir_cases = fir_df.to_dict("records")

    return {
        "fir_cases": fir_cases,
        "fir_df": fir_df,
        "graph": graph,
        "graph_summary": summarize_graph(graph),
        "cross_case_links": cross_case_links,
        "entity_resolution": entity_resolution,
        "net_report": net_report,
        "intel_report": intel_report,
        "tables": tables,
        "anpr_df": anpr_df,
    }


def load_pipeline_data(num_cases: int, base_nonce: int, refresh_nonce: int):
    generate_base_pipeline_data(num_cases, base_nonce)
    return build_analytics_from_disk(base_nonce, refresh_nonce)


# =============================================================================
# SIDEBAR — navigation, theme toggle, pipeline controls
# =============================================================================
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Select View",
    ["Overview Dashboard", "FIR Registration", "Network Analysis", "Timeline & Event Correlation",
     "Suspicious Activity", "Persons and Witnesses", "Analytics",
     "Report Analysis", "AI Assistant"],
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
    data = load_pipeline_data(num_cases, st.session_state["pipeline_nonce"], st.session_state["fir_refresh_nonce"])

fir_cases = data["fir_cases"]
fir_df = data["fir_df"]
G = data["graph"]
net_report = data["net_report"]
intel_report = data["intel_report"]
tables = data["tables"]
anpr_df = data["anpr_df"]
entity_resolution = data.get("entity_resolution", {"merged_clusters": [], "possible_duplicates": []})
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


def _render_fir_form(key_prefix, prefill=None):
    """
    Renders the FIR registration form (shared by the Manual Registration and
    Upload FIR Document tabs). `prefill` optionally pre-populates fields from
    a PDF extraction, for the officer to review/correct before submitting.
    There is deliberately NO Connectivity Type input anywhere in this form —
    main_investigation_pipeline.register_custom_fir() derives it automatically
    from the crime classification.

    Returns a dict ready for register_custom_fir() once "Register FIR" is
    clicked and the required fields are present, otherwise None.
    """
    prefill = prefill or {}
    case_type_options = sorted(BNS_CRIME_DATABASE.keys())

    st.subheader("1. Primary Details")
    c1, c2, c3 = st.columns(3)
    with c1:
        district = st.selectbox(
            "District *", DISTRICTS,
            index=DISTRICTS.index(prefill["District"]) if prefill.get("District") in DISTRICTS else 0,
            key=f"{key_prefix}_district",
        )
    with c2:
        police_station = st.text_input(
            "Police Station *", value=prefill.get("Police_Station") or f"{district} PS", key=f"{key_prefix}_ps"
        )
    with c3:
        state = st.text_input("State *", value=prefill.get("State_UT") or "Maharashtra", key=f"{key_prefix}_state")

    c1, c2 = st.columns(2)
    with c1:
        fir_number = st.text_input(
            "FIR Number", placeholder="Leave blank to auto-generate", key=f"{key_prefix}_fir_no"
        )
    with c2:
        reporting_datetime = st.text_input(
            "Date & Time of FIR", value=datetime.now().strftime("%Y-%m-%d %H:%M"), key=f"{key_prefix}_dt"
        )

    st.divider()
    st.subheader("2. Details of the Incident")
    case_type = st.selectbox(
        "Case Type *", case_type_options,
        index=case_type_options.index(prefill["Case_Type"]) if prefill.get("Case_Type") in case_type_options else 0,
        key=f"{key_prefix}_case_type",
    )
    acts_sections = st.text_input(
        "Acts / Sections",
        value=prefill.get("Acts_Sections") or BNS_CRIME_DATABASE[case_type]["bns"],
        help="Leave as the default for the selected Case Type unless the PDF/extraction found something more specific.",
        key=f"{key_prefix}_acts",
    )
    occurrence_place = st.text_input(
        "Place of Occurrence", value=prefill.get("Place_of_Occurrence", ""), placeholder="e.g. Kharghar",
        key=f"{key_prefix}_occ_place",
    )
    st.caption(
        "Connectivity Type is no longer entered manually — it's classified automatically from the crime type, "
        "BNS section, and whether the incident spans more than one district."
    )

    st.divider()
    st.subheader("3. Complainant / Informant")
    c1, c2, c3 = st.columns(3)
    with c1:
        informant_name = st.text_input("Informant Name *", value=prefill.get("Informant_Name", ""), key=f"{key_prefix}_inf_name")
    with c2:
        informant_contact = st.text_input("Informant Contact", value=prefill.get("Informant_Contact", ""), key=f"{key_prefix}_inf_contact")
    with c3:
        informant_address = st.text_input("Informant Address", value=prefill.get("Informant_Address", ""), key=f"{key_prefix}_inf_addr")

    st.divider()
    st.subheader("4. Victim")
    c1, c2, c3 = st.columns(3)
    with c1:
        victim_name = st.text_input("Victim Name *", value=prefill.get("Victim_Name", ""), key=f"{key_prefix}_vic_name")
    with c2:
        victim_age = st.number_input("Victim Age", min_value=0, max_value=120, value=25, key=f"{key_prefix}_vic_age")
    with c3:
        victim_gender = st.selectbox("Victim Gender", ["Male", "Female"], key=f"{key_prefix}_vic_gender")
    victim_contact = st.text_input("Victim Contact", value=prefill.get("Victim_Contact", ""), key=f"{key_prefix}_vic_contact")

    st.divider()
    st.subheader("5. Accused")
    default_accused = prefill.get("Accused_Name_Alias", "")
    accused_known = st.radio(
        "Is the accused known?", ["Known", "Unknown"], horizontal=True,
        index=1 if not default_accused or "unknown" in default_accused.lower() else 0,
        key=f"{key_prefix}_acc_known",
    )
    accused_name = st.text_input(
        "Accused Name / Alias",
        value="Unknown Accused" if accused_known == "Unknown" else default_accused,
        key=f"{key_prefix}_acc_name",
    )
    accused_contact = st.text_input("Accused Contact", value=prefill.get("Accused_Contact", ""), key=f"{key_prefix}_acc_contact")
    accused_address = st.text_input("Accused Address", value=prefill.get("Accused_Address", ""), key=f"{key_prefix}_acc_addr")

    st.divider()
    st.subheader("6. Investigating Officer & Narrative")
    io_name = st.text_input("Investigating Officer Name", value="Inspector (Unassigned)", key=f"{key_prefix}_io")
    narrative = st.text_area(
        "Narrative / Statement", value=prefill.get("FIR_Narrative_Statement", ""), height=180,
        placeholder="Chronological description of the incident.", key=f"{key_prefix}_narrative",
    )

    st.write("")
    if st.button("Register FIR", type="primary", use_container_width=True, key=f"{key_prefix}_submit"):
        if not informant_name:
            st.error("Please enter the Informant Name.")
            return None
        if not victim_name:
            st.error("Please enter the Victim Name.")
            return None
        return {
            "District": district, "Police_Station": police_station, "State_UT": state,
            "FIR_No": fir_number.strip() or None, "Date_Time_of_FIR": reporting_datetime,
            "Case_Type": case_type, "Acts_Sections": acts_sections, "Place_of_Occurrence": occurrence_place,
            "Informant_Name": informant_name, "Informant_Contact": informant_contact, "Informant_Address": informant_address,
            "Victim_Name": victim_name, "Victim_Age": victim_age, "Victim_Gender": victim_gender, "Victim_Contact": victim_contact,
            "Accused_Name_Alias": accused_name, "Accused_Contact": accused_contact, "Accused_Address": accused_address,
            "Investigating_Officer_Name": io_name, "FIR_Narrative_Statement": narrative,
        }
    return None


def _submit_fir(collected):
    """Calls register_custom_fir(), bumps the refresh nonce so the graph/analytics
    reload from disk on rerun, stashes a one-shot confirmation, and reruns."""
    result = register_custom_fir(collected)
    st.session_state["fir_refresh_nonce"] += 1
    st.session_state["fir_extracted_data"] = {}
    st.session_state["fir_last_registration"] = {
        "fir_no": result["fir_case"]["FIR_No"],
        "connectivity": result["connectivity_type"],
        "tier": result["financial_tier"],
        "anomaly_count": len(result["anomalies"]),
    }
    st.rerun()


# =============================================================================
# REPORTS & ANALYSIS — case-file catalog + modal report viewer
# -----------------------------------------------------------------------------
# Every CSV the pipeline writes to disk (main_investigation_pipeline.py) is
# either keyed by "FIR_No" (the master FIR table) or "Case_ID" (every
# downstream record type — telecom, vehicle, financial, crypto, medico-legal,
# etc., which all store the *same* FIR number under that column name — see
# save_csv() calls in main_investigation_pipeline.py). REPORT_CATALOG below is
# just that file list, grouped the same way the forensic-record reference
# sheet groups them, with the column to filter each one on.
# =============================================================================
REPORT_CATALOG = {
    "Case File": [
        ("FIR Master Record", "complete_fir_dataset.csv", "FIR_No"),
    ],
    "Telecom Intelligence": [
        ("Subscriber Detail Records (SDR)", "Subscriber_Detail_Records.csv", "Case_ID"),
        ("Call Detail Records (CDR)", "Call_Recording.csv", "Case_ID"),
        ("Internet Protocol Detail Records (IPDR)", "IP_Detail_Records.csv", "Case_ID"),
    ],
    "Vehicle & Location Intelligence": [
        ("Vehicle Summary", "Vehicle_Summary.csv", "Case_ID"),
        ("VAHAN Registration Database", "VAHAN_Database.csv", "Case_ID"),
        ("SARATHI Driving License Database", "SARATHI_Database.csv", "Case_ID"),
        ("FASTag Toll Logs", "FASTag_Toll_Logs.csv", "Case_ID"),
        ("ANPR Camera Feeds", "ANPR_Camera_Feeds.csv", "Case_ID"),
    ],
    "Financial & Banking Intelligence": [
        ("Financial Intelligence Summary", "Financial_Summary.csv", "Case_ID"),
        ("Bank Statement Records", "Bank_Statement_Records.csv", "Case_ID"),
        ("UPI Payment Gateway Logs", "UPI_Payment_Gateway_Logs.csv", "Case_ID"),
        ("Merchant Gateway Transaction Logs", "Merchant_Gateway_Transaction_Logs.csv", "Case_ID"),
    ],
    "Cryptocurrency Intelligence": [
        ("On-Chain Crypto Transactions", "Crypto_OnChain_Transactions.csv", "Case_ID"),
        ("Crypto Exchange KYC Records", "Crypto_Exchange_KYC_Records.csv", "Case_ID"),
        ("Crypto Exchange On/Off-Ramp Logs", "Crypto_Exchange_OnOffRamp_Logs.csv", "Case_ID"),
    ],
    "Corporate & Tax Intelligence": [
        ("ITR Forensic Profile", "ITR_Forensic_Profile.csv", "Case_ID"),
        ("GST E-Way Bill Records", "GST_EWayBill_Records.csv", "Case_ID"),
        ("CIBIL Commercial Credit Report", "CIBIL_Commercial_Credit_Report.csv", "Case_ID"),
        ("RoC Shell Company Filings", "RoC_Shell_Company_Filings.csv", "Case_ID"),
    ],
    "Medico-Legal & Forensic Reports": [
        ("Medical Forensic Summary", "Medical_Forensic_Summary.csv", "Case_ID"),
        ("MLC / Clinical Assault Reports", "MLC_Clinical_Assault_Reports.csv", "Case_ID"),
        ("Post-Mortem / Autopsy Reports", "PostMortem_Autopsy_Reports.csv", "Case_ID"),
        ("Forensic Toxicology Reports", "Forensic_Toxicology_Reports.csv", "Case_ID"),
        ("DNA Profiling Reports", "DNA_Profiling_Reports.csv", "Case_ID"),
        ("SAFE Reports", "SAFE_Reports.csv", "Case_ID"),
        ("Forensic Odontology Reports", "Forensic_Odontology_Reports.csv", "Case_ID"),
        ("Skeletal Identification Reports", "Skeletal_Identification_Reports.csv", "Case_ID"),
        ("Forensic Psychiatric Reports", "Forensic_Psychiatric_Reports.csv", "Case_ID"),
    ],
}

# -----------------------------------------------------------------------------
# REPORT ANALYSIS — TAB GROUPING
# -----------------------------------------------------------------------------
# The "Report Analysis" page (formerly "Reports & Analysis") groups the same
# REPORT_CATALOG data into 5 tabs, in the order the case file is actually
# worked in an investigation: Case File -> Medical Forensic -> Financial
# Forensic -> Non-Media Forensic -> Multimedia Digital Forensic. Each tab
# lists the REPORT_CATALOG categories that belong to it ("sections") plus any
# forensic modules that are on the roadmap but not yet wired to a real data
# source ("under_construction" — rendered as disabled placeholder cards
# instead of a working report button).
# -----------------------------------------------------------------------------
REPORT_TABS = {
    "Case File": {
        "sections": ["Case File"],
        "under_construction": [],
    },
    "Medical Forensic": {
        "sections": ["Medico-Legal & Forensic Reports"],
        "under_construction": [],
    },
    "Financial Forensic": {
        "sections": [
            "Financial & Banking Intelligence",
            "Cryptocurrency Intelligence",
            "Corporate & Tax Intelligence",
        ],
        "under_construction": [],
    },
    "Non-Media Forensic": {
        # Telecom & Vehicle/Location Intelligence already have real generated
        # reports (left exactly as they were). The remaining digital-forensics
        # artifact categories are on the roadmap only, so they render as
        # "under construction" placeholders instead of report buttons.
        "sections": [
            "Telecom Intelligence",
            "Vehicle & Location Intelligence",
        ],
        # Single source of truth shared with main_investigation_pipeline.py's
        # unified report generator (section 7) — see the import at the top of
        # this file.
        "under_construction": NON_MEDIA_FORENSIC_UNDER_CONSTRUCTION,
    },
    "Multimedia Digital Forensic": {
        "sections": [],
        # Shared with main_investigation_pipeline.py's unified report
        # generator (section 8) — see the import at the top of this file.
        "under_construction": MULTIMEDIA_FORENSIC_UNDER_CONSTRUCTION,
    },
}

# Flat list of every "under construction" forensic module across all tabs —
# used to annotate the Full Unified Investigation Report section so it's
# clear those artifact types are not yet part of the generated report either.
UNDER_CONSTRUCTION_MODULES = [
    item
    for tab in REPORT_TABS.values()
    for item in tab["under_construction"]
]

# -----------------------------------------------------------------------------
# ANALYSIS SUB-TAB — evidence upload modules + accepted file types
# -----------------------------------------------------------------------------
# Each of the 4 forensic tabs (Medical / Financial / Non-Media / Multimedia)
# gets an "Analysis" sub-tab where raw evidence can be uploaded per module.
# Accepted extensions below are taken directly from the forensic reference
# sheet's "Accepted File Formats for Analysis" table where that module
# appears in it. Modules the sheet doesn't cover fall back to PDF (or, for
# clearly tabular financial records, PDF/CSV/XLSX) as instructed.
# Format: (module_name, icon, [accepted extensions, no dots]).
# -----------------------------------------------------------------------------
ANALYSIS_MODULES = {
    "Medical Forensic": [
        ("Medical Forensic Summary", "🩺", ["pdf"]),
        ("MLC / Clinical Assault Reports", "🤕", ["pdf"]),
        ("Post-Mortem / Autopsy Reports", "⚰️", ["pdf"]),
        ("Forensic Toxicology Reports", "🧪", ["pdf"]),
        ("DNA Profiling Reports", "🧬", ["pdf"]),
        ("SAFE Reports", "🛡️", ["pdf"]),
        ("Forensic Odontology Reports", "🦷", ["pdf"]),
        ("Skeletal Identification Reports", "🦴", ["pdf"]),
        ("Forensic Psychiatric Reports", "🧠", ["pdf"]),
    ],
    "Financial Forensic": [
        # Not covered by the reference sheet — bank/UPI/GST/ITR style records
        # are most commonly shared as statements (PDF) or exports (CSV/XLSX).
        ("Financial & Banking Intelligence", "💳", ["pdf", "csv", "xlsx"]),
        ("Cryptocurrency Intelligence", "🪙", ["pdf", "csv", "xlsx"]),
        ("Corporate & Tax Intelligence", "🏢", ["pdf", "csv", "xlsx"]),
    ],
    "Non-Media Forensic": [
        # Telecom / Vehicle & Location already have live synthetic reports;
        # closest sheet matches used for their accepted upload types.
        ("Telecom Intelligence", "📡", ["csv", "xml", "json"]),
        ("Vehicle & Location Intelligence", "🚗", ["csv", "xlsx", "kml", "gpx", "json"]),
        ("Volatile Memory Forensics", "🧠", ["raw", "dmp", "mem", "lime", "vmem"]),
        ("OS & Registry Artifacts", "🗂️", ["dat", "lnk", "pf", "reg"]),
        ("Network & Internet Logs", "🌐", ["pcap", "pcapng", "log", "txt", "csv"]),
        ("Location & Sensor Data", "📍", ["csv", "xlsx", "kml", "gpx", "json"]),
        ("File System Artifacts", "📁", ["e01", "raw", "dd", "aff4"]),
        # Not covered by the sheet — browser/app artifacts are typically
        # SQLite databases or exported JSON.
        ("Browser & App Artifacts", "🧭", ["db", "sqlite", "json"]),
        ("Hardware & Peripheral Logs", "🔌", ["log", "spl", "shd"]),
    ],
    "Multimedia Digital Forensic": [
        ("Chats Analysis", "💬", ["db", "sqlite", "crypt14", "crypt15", "xml", "json", "ufdr"]),
        ("Audio Analysis", "🔊", ["wav", "mp3", "opus", "m4a", "aac", "amr", "flac"]),
        ("Video Analysis", "🎥", ["mp4", "mov", "avi", "dav"]),
        ("Image Analysis", "🖼️", ["jpg", "jpeg", "png", "heic", "dng", "raw", "cr2", "nef"]),
    ],
}

# Streamlit's real modal ("small window") API is st.dialog — added in 1.31.
# Older installs only have st.experimental_dialog; older still have neither,
# so fall back to an inline expander that behaves the same way for the user.
if hasattr(st, "dialog"):
    _dialog_decorator = st.dialog
elif hasattr(st, "experimental_dialog"):
    _dialog_decorator = st.experimental_dialog
else:
    _dialog_decorator = None


def _render_report_table(display_name, case_id, filename, case_col):
    """Loads one report CSV, filters it to the selected case, and renders it
    as a table with a download button. Shared by the modal and the
    no-dialog-available fallback below."""
    if not os.path.exists(filename):
        st.warning(
            f"`{filename}` hasn't been generated yet in this working directory. "
            "Use the 'Regenerate dataset' button in the sidebar to run the pipeline."
        )
        return
    try:
        df = pd.read_csv(filename)
    except Exception as e:
        st.error(f"Could not read `{filename}`: {e}")
        return

    if case_col and case_col in df.columns:
        df = df[df[case_col].astype(str) == str(case_id)]

    st.caption(f"Source file: `{filename}`  •  {len(df)} record(s) matched for **{case_id}**")
    if df.empty:
        st.info(f"No {display_name} records exist for case {case_id}.")
        return

    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button(
        "⬇️ Download this table (CSV)",
        df.to_csv(index=False).encode("utf-8"),
        file_name=f"{str(case_id).replace('/', '_')}__{filename}",
        mime="text/csv",
        use_container_width=True,
        key=f"dl_{case_id}_{filename}",
    )


if _dialog_decorator is not None:
    @_dialog_decorator("Case Report Viewer", width="large")
    def _open_report_window(display_name, case_id, filename, case_col):
        st.markdown(f"#### {display_name}")
        _render_report_table(display_name, case_id, filename, case_col)
else:
    def _open_report_window(display_name, case_id, filename, case_col):
        # No modal API available on this Streamlit version — render the same
        # content inline in an expanded expander directly under the button.
        with st.expander(f"📄 {display_name} — {case_id}", expanded=True):
            _render_report_table(display_name, case_id, filename, case_col)


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
        st.metric("Active Investigations", len(fir_cases))
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
        '<div class="info-box">Register a case manually, or upload a scanned/typed FIR document and let the '
        'local deepseek-r1 model extract it for you to verify. Either way, submitting here immediately appends '
        'the FIR plus its full telecom, vehicle and financial intelligence trail to disk and refreshes the '
        'relationship graph / network analytics — no separate "regenerate dataset" step needed. For academic '
        'demonstrations, use fictional or sample identity information.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    if st.session_state["fir_last_registration"]:
        info = st.session_state.pop("fir_last_registration")
        st.success(
            f"FIR **{info['fir_no']}** registered. Connectivity auto-classified as **{info['connectivity']}**. "
            f"Financial forensic tier: **{info['tier']}**. {info['anomaly_count']} anomaly flag(s) raised across "
            "telecom, vehicle and financial intelligence. Graph & network analytics refreshed."
        )

    tab_manual, tab_upload = st.tabs(["📝 Manual Registration", "📄 Upload FIR Document (PDF)"])

    with tab_manual:
        collected = _render_fir_form("manual")
        if collected:
            _submit_fir(collected)

    with tab_upload:
        if PDF_IMPORT_ERROR:
            st.warning(f"PDF reading isn't available: {PDF_IMPORT_ERROR}")
        else:
            _groq_client_check, _groq_error_check = _get_groq_client()
            if _groq_error_check:
                st.info(
                    f"Groq translation/classification is off ({_groq_error_check}). "
                    "Regex-extracted fields (name, phone, address, narrative) will still work — "
                    "set the GROQ_API_KEY environment variable to also get auto-translation and "
                    "Case_Type classification."
                )
            else:
                st.caption(
                    f"Translation/classification runs on the free Groq API (`{FIR_EXTRACTION_LLM_MODEL}`). "
                    "Name/phone/address/narrative are read locally by regex — only short field "
                    "snippets and the narrative summary are sent to Groq."
                )
            uploaded_pdf = st.file_uploader("Upload FIR document (PDF)", type=["pdf"], key="fir_pdf_uploader")

            if uploaded_pdf is not None:
                if st.button("🧠 Extract fields", key="fir_pdf_extract_btn"):
                    with st.spinner(f"Reading PDF and extracting fields with {FIR_EXTRACTION_LLM_MODEL}..."):
                        extracted, err = extract_fir_fields_local(uploaded_pdf)
                    if err:
                        st.error(err)
                    else:
                        st.session_state["fir_extracted_data"] = extracted
                        st.success("Fields extracted — review and correct them below before registering.")

            if st.session_state["fir_extracted_data"]:
                st.divider()
                st.markdown("**Extracted fields — verify before submitting:**")
                collected = _render_fir_form("pdf", prefill=st.session_state["fir_extracted_data"])
                if collected:
                    _submit_fir(collected)

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
    tabs = st.tabs(["Persons", "Entities by Type", "🧬 Possible Same Person"])

    all_cases = fir_cases
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

    with tabs[2]:
        merged = entity_resolution.get("merged_clusters", [])
        possible = entity_resolution.get("possible_duplicates", [])

        st.markdown(
            '<div class="info-box">'
            "Entity resolution compares every person, victim, informant, and accused name "
            "across ALL cases using name-similarity, phone, address, and vehicle matching "
            "(Fellegi-Sunter probabilistic linkage). Names the system is confident are the "
            "same individual are merged automatically in the graph below. Names that look "
            "similar but lack enough corroborating evidence are listed separately for an "
            "investigator to confirm or reject &mdash; they are <b>not</b> auto-merged."
            "</div>", unsafe_allow_html=True,
        )
        st.write("")

        st.markdown(
            f'<div class="panel-title">✅ Confirmed same person — {len(merged)} cluster(s) auto-merged</div>',
            unsafe_allow_html=True,
        )
        if merged:
            for cluster in merged:
                aliases = cluster.get("aliases_merged", [])
                with st.expander(
                    f"**{cluster['canonical_name']}** — merged with: {', '.join(aliases)}  "
                    f"(confidence {cluster.get('confidence', 0):.2f})"
                ):
                    ev_rows = []
                    for ev in cluster.get("evidence", []):
                        feat = ev.get("features", {})
                        ev_rows.append({
                            "Name A": ev.get("record_a"), "Name B": ev.get("record_b"),
                            "Match score": ev.get("score"),
                            "Name similarity": feat.get("name_similarity"),
                            "Phone match": feat.get("phone_agree"),
                            "Address match": feat.get("address_agree"),
                            "Vehicle match": feat.get("vehicle_agree"),
                        })
                    if ev_rows:
                        st.dataframe(pd.DataFrame(ev_rows), use_container_width=True, hide_index=True)
        else:
            st.info("No confirmed alias merges in the current batch.")

        st.write("")
        st.markdown(
            f'<div class="panel-title">⚠️ Possible duplicates — {len(possible)} pair(s) need investigator review</div>',
            unsafe_allow_html=True,
        )
        if possible:
            review_rows = []
            for p in possible:
                feat = p.get("features", {})
                review_rows.append({
                    "Name A": p.get("name_a"), "Name B": p.get("name_b"),
                    "Match score": p.get("score"),
                    "Name similarity": feat.get("name_similarity"),
                    "Phone match": feat.get("phone_agree"),
                    "Address match": feat.get("address_agree"),
                    "Vehicle match": feat.get("vehicle_agree"),
                })
            st.dataframe(pd.DataFrame(review_rows), use_container_width=True, hide_index=True)
            st.caption(
                "These pairs share some evidence (name similarity, phone, address, or vehicle) "
                "but not enough to auto-merge with confidence. Confirm manually if you know "
                "them to be the same person."
            )
        else:
            st.info("No ambiguous name pairs flagged for review in the current batch.")

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
# PAGE 8: REPORTS & ANALYSIS — per-case forensic record browser
# =============================================================================
elif page == "Report Analysis":
    st.markdown('<div class="section-title">Report Analysis</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="info-box">Select a Case / FIR number to open its case file, shown below. Then '
        'work through the 4 forensic tabs — <b>Medical Forensic</b>, <b>Financial Forensic</b>, '
        '<b>Non-Media Forensic</b>, and <b>Multimedia Digital Forensic</b> — each split into a '
        '<b>Reports</b> sub-tab (everything generated or uploaded for this case) and an '
        '<b>Analysis</b> sub-tab (upload raw evidence per module). The '
        '<b>Full Unified Investigation Report</b> sits at the bottom. Modules still on the roadmap '
        'are clearly marked 🚧 Under Construction instead of showing broken or empty reports.</div>',
        unsafe_allow_html=True,
    )
    st.write("")

    if fir_df.empty or "FIR_No" not in fir_df.columns:
        st.warning("No FIR dataset is loaded yet — use 'Regenerate dataset' in the sidebar.")
    else:
        all_fir_numbers = sorted(fir_df["FIR_No"].dropna().astype(str).unique().tolist())
        c1, c2 = st.columns([2, 3])
        with c1:
            dropdown_case = st.selectbox("Select Case / FIR No.", all_fir_numbers, key="reports_case_select")
        with c2:
            typed_case = st.text_input(
                "…or type a Case / FIR No. directly (overrides the dropdown)",
                value="", placeholder="e.g. FIR/2026/0007", key="reports_case_typed",
            )
        active_case = typed_case.strip() if typed_case.strip() else dropdown_case

        case_row = fir_df[fir_df["FIR_No"].astype(str) == str(active_case)]
        if case_row.empty:
            st.error(f"No case found for '{active_case}'. Check the Case / FIR number and try again.")
        else:
            row = case_row.iloc[0]
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("District", row.get("District", "—"))
            m2.metric("Case Type", row.get("Case_Type", "—"))
            m3.metric("Vulnerability", row.get("Vulnerability_Category", "—"))
            m4.metric("Connectivity", row.get("Connectivity_Type", "—"))
            st.write("")
            st.divider()

            def _render_report_section(category, reports, case_id):
                """Renders one REPORT_CATALOG category as a row of report buttons."""
                st.markdown(f'<div class="panel-title">{category}</div>', unsafe_allow_html=True)
                cols = st.columns(3)
                for i, (display_name, filename, case_col) in enumerate(reports):
                    with cols[i % 3]:
                        exists = os.path.exists(filename)
                        label = f"📄 {display_name}" if exists else f"🚫 {display_name} (not generated)"
                        clicked = st.button(
                            label, key=f"rpt_{category}_{filename}",
                            use_container_width=True, disabled=not exists,
                        )
                        if clicked:
                            _open_report_window(display_name, case_id, filename, case_col)
                st.write("")

            def _render_under_construction_section(tab_name, modules):
                """Renders a tab's not-yet-implemented forensic modules as
                disabled placeholder cards, clearly labeled Under Construction."""
                if not modules:
                    return
                st.markdown(
                    f'<div class="panel-title">🚧 Additional {tab_name} Modules (Under Construction)</div>',
                    unsafe_allow_html=True,
                )
                cols = st.columns(3)
                for i, module_name in enumerate(modules):
                    with cols[i % 3]:
                        st.button(
                            f"🚧 {module_name} — Under Construction",
                            key=f"uc_{tab_name}_{module_name}",
                            use_container_width=True, disabled=True,
                        )
                st.caption(
                    "These forensic modules are planned but not yet wired to a data source in this build."
                )
                st.write("")

            def _render_uploaded_files_section(tab_name, case_id):
                """Renders every file uploaded (this session) via the Analysis
                sub-tab of `tab_name`, grouped by module, inside the matching
                Reports sub-tab."""
                prefix = f"{case_id}||{tab_name}||"
                matches = {
                    key: files for key, files in st.session_state["analysis_uploads"].items()
                    if key.startswith(prefix) and files
                }
                if not matches:
                    return
                st.markdown(
                    '<div class="panel-title">📤 Uploaded Evidence Files (this session)</div>',
                    unsafe_allow_html=True,
                )
                for key, files in matches.items():
                    module_name = key.split("||", 2)[2]
                    st.caption(f"**{module_name}**")
                    for f in files:
                        st.markdown(f"- 📎 `{f['name']}` — {f['size']/1024:.1f} KB — uploaded {f['uploaded_at']}")
                st.write("")

            def _render_analysis_section(tab_name, case_id):
                """Renders the Analysis sub-tab for one forensic tab: an
                uploader per module (accepted types from ANALYSIS_MODULES),
                plus disabled 'Analysis' and 'Connect to AI' buttons, each
                with an (i) tooltip explaining they're under construction."""
                modules = ANALYSIS_MODULES.get(tab_name, [])
                if not modules:
                    st.info("No analysis modules configured for this tab yet.")
                    return
                for module_name, icon, extensions in modules:
                    with st.expander(f"{icon} {module_name}", expanded=False):
                        st.caption(
                            "Accepted file types: " + ", ".join(f".{e}" for e in extensions)
                        )
                        upload_key = f"upload_{tab_name}_{module_name}_{case_id}"
                        uploaded = st.file_uploader(
                            f"Upload evidence for {module_name}",
                            type=extensions,
                            key=upload_key,
                            label_visibility="collapsed",
                        )
                        if uploaded is not None:
                            store_key = f"{case_id}||{tab_name}||{module_name}"
                            existing = st.session_state["analysis_uploads"].setdefault(store_key, [])
                            if not any(f["name"] == uploaded.name and f["size"] == uploaded.size for f in existing):
                                existing.append({
                                    "name": uploaded.name,
                                    "size": uploaded.size,
                                    "uploaded_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
                                })
                            st.success(
                                f"'{uploaded.name}' attached to this case. It now appears under this "
                                f"tab's Reports sub-tab and in the Full Unified Investigation Report list below."
                            )

                        ac1, ac2 = st.columns(2)
                        with ac1:
                            st.button(
                                "🔬 Run Analysis", key=f"run_analysis_{tab_name}_{module_name}_{case_id}",
                                use_container_width=True, disabled=True,
                                help="Under construction — automated analysis for this module isn't wired up yet.",
                            )
                        with ac2:
                            st.button(
                                "🤖 Connect to AI", key=f"connect_ai_{tab_name}_{module_name}_{case_id}",
                                use_container_width=True, disabled=True,
                                help="Under construction — AI-assisted review for this module isn't wired up yet.",
                            )

            # ---- CASE FILE — shown above the 4 forensic tabs, not as a tab -----
            st.markdown('<div class="subsection-title">📁 Case File</div>', unsafe_allow_html=True)
            st.caption("FIR master record for the selected case.")
            for category in REPORT_TABS["Case File"]["sections"]:
                _render_report_section(category, REPORT_CATALOG[category], active_case)
            _render_under_construction_section(
                "Case File", REPORT_TABS["Case File"]["under_construction"]
            )
            st.divider()

            tab_medical, tab_financial, tab_nonmedia, tab_multimedia = st.tabs(
                [
                    "🩺 Medical Forensic",
                    "💰 Financial Forensic",
                    "🖥️ Non-Media Forensic",
                    "🎞️ Multimedia Digital Forensic",
                ]
            )

            with tab_medical:
                sub_reports, sub_analysis = st.tabs(["📄 Reports", "🔬 Analysis"])
                with sub_reports:
                    st.caption(
                        "All Medico-Legal & Forensic Reports generated for this case "
                        "(MLC, post-mortem, toxicology, DNA, SAFE, odontology, skeletal, psychiatric)."
                    )
                    for category in REPORT_TABS["Medical Forensic"]["sections"]:
                        _render_report_section(category, REPORT_CATALOG[category], active_case)
                    _render_under_construction_section(
                        "Medical Forensic", REPORT_TABS["Medical Forensic"]["under_construction"]
                    )
                    _render_uploaded_files_section("Medical Forensic", active_case)
                with sub_analysis:
                    _render_analysis_section("Medical Forensic", active_case)

            with tab_financial:
                sub_reports, sub_analysis = st.tabs(["📄 Reports", "🔬 Analysis"])
                with sub_reports:
                    st.caption(
                        "Financial & Banking Intelligence, Cryptocurrency Intelligence, and "
                        "Corporate & Tax Intelligence reports for this case."
                    )
                    for category in REPORT_TABS["Financial Forensic"]["sections"]:
                        _render_report_section(category, REPORT_CATALOG[category], active_case)
                    _render_under_construction_section(
                        "Financial Forensic", REPORT_TABS["Financial Forensic"]["under_construction"]
                    )
                    _render_uploaded_files_section("Financial Forensic", active_case)
                with sub_analysis:
                    _render_analysis_section("Financial Forensic", active_case)

            with tab_nonmedia:
                sub_reports, sub_analysis = st.tabs(["📄 Reports", "🔬 Analysis"])
                with sub_reports:
                    st.caption(
                        "Non-media digital forensic findings for this case — Telecom Intelligence and "
                        "Vehicle & Location Intelligence are live; the remaining digital-forensics "
                        "artifact categories below are under construction."
                    )
                    for category in REPORT_TABS["Non-Media Forensic"]["sections"]:
                        _render_report_section(category, REPORT_CATALOG[category], active_case)
                    _render_under_construction_section(
                        "Non-Media Forensic", REPORT_TABS["Non-Media Forensic"]["under_construction"]
                    )
                    _render_uploaded_files_section("Non-Media Forensic", active_case)
                with sub_analysis:
                    _render_analysis_section("Non-Media Forensic", active_case)

            with tab_multimedia:
                sub_reports, sub_analysis = st.tabs(["📄 Reports", "🔬 Analysis"])
                with sub_reports:
                    st.caption(
                        "Multimedia & digital media analysis for this case — chats, audio, video, and "
                        "image forensics. This tab is entirely under construction until evidence is "
                        "uploaded via Analysis."
                    )
                    for category in REPORT_TABS["Multimedia Digital Forensic"]["sections"]:
                        _render_report_section(category, REPORT_CATALOG[category], active_case)
                    _render_under_construction_section(
                        "Multimedia Digital Forensic",
                        REPORT_TABS["Multimedia Digital Forensic"]["under_construction"],
                    )
                    _render_uploaded_files_section("Multimedia Digital Forensic", active_case)
                with sub_analysis:
                    _render_analysis_section("Multimedia Digital Forensic", active_case)

            st.divider()
            st.markdown('<div class="panel-title">Full Unified Investigation Report</div>', unsafe_allow_html=True)
            unified_path = "FINAL_GOVERNMENT_CASE_INVESTIGATION_REPORT.txt"
            if os.path.exists(unified_path):
                with open(unified_path, "r", encoding="utf-8", errors="ignore") as f:
                    full_text = f.read()
                if active_case in full_text:
                    idx = full_text.find(active_case)
                    snippet = full_text[max(0, idx - 200): idx + 4000]
                    with st.expander(f"Preview around {active_case}", expanded=False):
                        st.text(snippet)
                else:
                    with st.expander("Preview (case marker not found — showing report head)", expanded=False):
                        st.text(full_text[:4000])
                st.download_button(
                    "⬇️ Download full unified report (.txt)", full_text.encode("utf-8"),
                    file_name=unified_path, mime="text/plain", key="dl_unified_report",
                )
                with st.expander("🚧 Modules marked Under Construction in this report", expanded=False):
                    st.caption(
                        "The Full Unified Investigation Report includes a section for these modules, "
                        "labeled UNDER CONSTRUCTION, since they are not yet wired to a real data source:"
                    )
                    for module_name in UNDER_CONSTRUCTION_MODULES:
                        st.markdown(f"- 🚧 {module_name}")
            else:
                st.info("The unified report hasn't been generated yet.")

            case_uploads = {
                key.split("||", 2)[1] + " — " + key.split("||", 2)[2]: files
                for key, files in st.session_state["analysis_uploads"].items()
                if key.startswith(f"{active_case}||") and files
            }
            if case_uploads:
                with st.expander("📤 Evidence files uploaded this session (all tabs)", expanded=False):
                    for label, files in case_uploads.items():
                        for f in files:
                            st.markdown(f"- **{label}** — `{f['name']}` ({f['size']/1024:.1f} KB, {f['uploaded_at']})")

# =============================================================================
# PAGE 9: AI ASSISTANT (SOP / legal RAG chatbot — unchanged)
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
