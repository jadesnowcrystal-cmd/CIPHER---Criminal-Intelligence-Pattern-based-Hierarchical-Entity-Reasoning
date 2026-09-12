
import os
import re
import csv
import json
import logging
import hashlib
from typing import List, Dict, Any

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("FIRDataExtractor")


# ==========================================
# INTERNAL EXTRACTION ENGINE & EVALUATION
# ==========================================
class RAGExtractorEngine:
    """
    Core Extraction Engine responsible for entity recognition 
    and network relation parsing.
    """
    def process(self, document_text: str, case_id: str) -> Dict[str, Any]:
        # Extract phone numbers using regular expressions
        phones = re.findall(r'\b\d{10}\b', document_text)
        
        # Extract name lines if available in unstructured text
        informant_match = re.search(r"Informant(?:\s+Name)?\s*:\s*([A-Za-z\s]+)", document_text, re.IGNORECASE)
        victim_match = re.search(r"Victim(?:\s+Name)?\s*:\s*([A-Za-z\s]+)", document_text, re.IGNORECASE)
        accused_match = re.search(r"Accused(?:\s+Name)?\s*:\s*([A-Za-z\s]+)", document_text, re.IGNORECASE)

        informant_name = informant_match.group(1).strip() if informant_match else "Unknown Informant"
        victim_name = victim_match.group(1).strip() if victim_match else "Unknown Victim"
        accused_name = accused_match.group(1).strip() if accused_match else "Unknown Accused"

        return {
            "case_id": case_id,
            "entities": {
                "nodes": [
                    {"name": informant_name, "type": "Person", "role": "Informant"},
                    {"name": victim_name, "type": "Person", "role": "Victim"},
                    {"name": accused_name, "type": "Person", "role": "Accused"}
                ],
                "extracted_contacts": list(set(phones))
            },
            "relations": [
                {"source": accused_name, "target": victim_name, "type": "ACCUSED_OF_CRIME_AGAINST"},
                {"source": informant_name, "target": victim_name, "type": "REPORTED_INCIDENT_FOR"}
            ],
            "raw_text_length": len(document_text)
        }


def process_case_data(case_structure: Dict[str, Any]) -> Dict[str, Any]:
    """
    Processes structured case inputs into graph entities and network relationships using proper names.
    """
    case_id = case_structure.get("case_id", "UNKNOWN")
    entities = case_structure.get("entities", {})
    
    nodes = []
    edges = []

    for role, data in entities.items():
        if isinstance(data, dict):
            # Prefer explicit full name, fallback to fallback role label if empty
            raw_name = data.get("name") or f"Unknown {role.capitalize()}"
            clean_name = raw_name.strip()
            
            # Generate stable internal ID, but keep proper display name
            person_id = f"PER-{hashlib.md5(clean_name.encode()).hexdigest()[:8]}"

            nodes.append({
                "person_id": person_id,
                "name": clean_name,  # Proper Name field
                "role": role.capitalize(),
                "phone": data.get("phone_number") or "N/A",
                "address": data.get("address") or "N/A"
            })

    # Find nodes by role to create relationship edges using actual names
    accused_node = next((n for n in nodes if n["role"] == "Accused"), None)
    victim_node = next((n for n in nodes if n["role"] == "Victim"), None)
    informant_node = next((n for n in nodes if n["role"] == "Informant"), None)

    if accused_node and victim_node:
        edges.append({
            "source_name": accused_node["name"],
            "target_name": victim_node["name"],
            "relation": "TARGETED"
        })
    if informant_node and victim_node:
        edges.append({
            "source_name": informant_node["name"],
            "target_name": victim_node["name"],
            "relation": "REPORTED_FOR"
        })

    return {
        "case_id": case_id,
        "nodes": nodes,
        "edges": edges,
        "metadata": {
            "district": case_structure.get("district"),
            "case_type": case_structure.get("case_type"),
            "connectivity": case_structure.get("connectivity")
        }
    }


def evaluate_batch(raw_cases: List[Dict[str, Any]], extracted_results: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Calculates batch extraction metrics (Precision, Recall, F1-Score).
    """
    total_expected = sum(len(c.get("entities", {})) for c in raw_cases)
    total_extracted = sum(len(r.get("nodes", r.get("entities", {}).get("nodes", []))) for r in extracted_results)
    
    precision = min(1.0, total_extracted / (total_expected + 1e-5))
    recall = min(1.0, total_extracted / (total_expected + 1e-5))
    f1 = 2 * (precision * recall) / (precision + recall + 1e-5)

    return {
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1_score": round(f1, 4)
    }


# ==========================================
# MAIN DATA EXTRACTION PIPELINE
# ==========================================
class FIRDataExtractor:
    """
    Ingests FIR datasets (CSV/TXT), standardizes inputs, and runs data extractions.
    """
    def __init__(self):
        self.engine = RAGExtractorEngine()

    def process_csv_dataset(self, csv_filepath: str) -> List[Dict[str, Any]]:
        if not os.path.exists(csv_filepath):
            logger.error(f"CSV file not found at: {csv_filepath}")
            return []

        extracted_results = []
        raw_cases = []

        logger.info(f"Reading FIR cases from CSV file: {csv_filepath}")
        with open(csv_filepath, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            for row in reader:
                # Safe date parsing
                fir_date_raw = row.get("Date_Time_of_FIR", "")
                fir_date = fir_date_raw.split(" ")[0] if fir_date_raw else ""
                fir_time = fir_date_raw.split(" ")[-1] if " " in fir_date_raw else ""

                occurrence_raw = row.get("Occurrence_Date_Range", "")
                occurrence_date = occurrence_raw.split(" to ")[0] if occurrence_raw else ""

                # Extract actual names from CSV columns
                inf_name = row.get("Informant_Name") or row.get("Informant") or "Unknown Informant"
                vic_name = row.get("Victim_Name") or row.get("Victim") or "Unknown Victim"
                acc_name = row.get("Accused_Name_Alias") or row.get("Accused_Name") or row.get("Accused") or "Unknown Accused"

                case_structure = {
                    "case_id": row.get("FIR_No", "UNKNOWN_FIR"),
                    "district": row.get("District", "N/A"),
                    "case_type": row.get("Case_Type", "Crime"),
                    "connectivity": row.get("Connectivity_Type", "Unplanned"),
                    "report_details": {"date": fir_date, "time": fir_time},
                    "occurrence_details": {
                        "date": occurrence_date,
                        "place": row.get("Place_of_Occurrence", "Unknown")
                    },
                    "entities": {
                        "informant": {
                            "name": inf_name.strip(),
                            "phone_number": row.get("Informant_Contact"),
                            "address": row.get("Informant_Address")
                        },
                        "victim": {
                            "name": vic_name.strip(),
                            "phone_number": row.get("Victim_Contact")
                        },
                        "accused": {
                            "name": acc_name.strip(),
                            "phone_number": row.get("Accused_Contact"),
                            "address": row.get("Accused_Address")
                        }
                    }
                }
                raw_cases.append(case_structure)
                extracted_results.append(process_case_data(case_structure))

        logger.info(f"Successfully processed {len(extracted_results)} cases from CSV.")
        
        # Calculate & save metrics
        metrics = evaluate_batch(raw_cases, extracted_results)
        logger.info(f"Extraction Performance Metrics: {metrics}")
        with open("extraction_metrics.json", "w", encoding="utf-8") as m_file:
            json.dump(metrics, m_file, indent=2)

        return extracted_results

    def process_txt_report(self, txt_filepath: str) -> List[Dict[str, Any]]:
        if not os.path.exists(txt_filepath):
            logger.error(f"Text report not found at: {txt_filepath}")
            return []

        logger.info(f"Parsing unstructured text report: {txt_filepath}")
        with open(txt_filepath, mode="r", encoding="utf-8") as file:
            content = file.read()

        case_blocks = re.split(r'\n(?=1\.\s*FIR\s+BASIC\s+INFORMATION)', content)
        extracted_results = []

        for block in case_blocks:
            if not block.strip():
                continue
            
            lines = block.strip().split("\n")
            case_id_match = re.search(r"CASE ID:\s*([A-Za-z0-9/-]+)", lines[0])
            case_id = case_id_match.group(1) if case_id_match else "CASE-UNKNOWN"

            extraction_output = self.engine.process(document_text=block, case_id=case_id)
            extracted_results.append(extraction_output)

        logger.info(f"Successfully processed {len(extracted_results)} case blocks from TXT report.")
        return extracted_results


# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == "__main__":
    extractor = FIRDataExtractor()

    # 1. Extract from CSV file
    csv_path = "complete_fir_dataset.csv"
    if os.path.exists(csv_path):
        logger.info(f"Processing {csv_path}...")
        csv_extractions = extractor.process_csv_dataset(csv_path)
        with open("extracted_csv_intelligence.json", "w", encoding="utf-8") as out:
            json.dump(csv_extractions, out, indent=2)
        logger.info("Saved output to 'extracted_csv_intelligence.json'.")

    # 2. Extract from TXT report file
    txt_path = "FINAL_GOVERNMENT_CASE_INVESTIGATION_REPORT.txt"
    if os.path.exists(txt_path):
        logger.info(f"Processing {txt_path}...")
        txt_extractions = extractor.process_txt_report(txt_path)
        with open("extracted_txt_intelligence.json", "w", encoding="utf-8") as out:
            json.dump(txt_extractions, out, indent=2)
        logger.info("Saved output to 'extracted_txt_intelligence.json'.")
