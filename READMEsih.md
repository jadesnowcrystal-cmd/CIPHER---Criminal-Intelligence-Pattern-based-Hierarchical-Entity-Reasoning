CIPHER --- AI-Powered Criminal Investigation & Digital Forensics Platform

CIPHER is a modular, AI-assisted criminal intelligence and
digital-forensics platform designed to help investigators connect
fragmented evidence, discover hidden relationships, detect suspicious
patterns, and organize case intelligence in one investigation
workspace.

Problem Statement

Criminal investigations involve fragmented information across FIR/case
records, telecom data, vehicle intelligence, financial transactions,
medical/forensic records, multimedia evidence, and legal/SOP documents.
The core challenge is connecting these sources into meaningful
investigative relationships.

Case → Person → Phone → Location → Vehicle → Bank Account
     → Transaction → Other Person → Other Case

Solution

CIPHER provides an AI-powered investigation workstation that:

Integrates heterogeneous investigative datasets

Resolves entities across records

Builds relationship graphs

Performs network and anomaly analysis

Correlates events through timelines and geospatial views

Supports basic image and audio forensic analysis

Provides legal/SOP retrieval through local RAG

Produces explainable intelligence signals with confidence and
evidence

Keeps investigators in the decision loop

Core Value Proposition

CIPHER uniquely unifies FIR, telecom, financial, vehicle,
geospatial, network intelligence, and multimedia forensics into one
explainable, AI-assisted investigation platform.

Architecture

FIR / CASE DATA
       ↓
INVESTIGATION PIPELINE
       ↓
┌────────────┬────────────┬────────────┐
│  TELECOM   │  VEHICLE   │  FINANCIAL │
│ SDR/CDR/   │ VAHAN/     │ BANK/UPI/  │
│ IPDR       │ SARATHI/   │ MERCHANT/  │
│            │ FASTag/ANPR│ CRYPTO     │
└─────┬──────┴─────┬──────┴─────┬──────┘
      └────────────┼────────────┘
                   ↓
          ENTITY RESOLUTION
                   ↓
          RELATIONSHIP GRAPH
              (NetworkX)
                   ↓
      ┌────────────┼────────────┐
      ↓            ↓            ↓
 NETWORK       INTELLIGENCE   TIMELINE &
 ANALYTICS       ENGINE       GEOSPATIAL
      └────────────┼────────────┘
                   ↓
          INVESTIGATION WORKSPACE

MULTIMEDIA EVIDENCE ──→ FORENSIC MODULES
LEGAL/SOP PDFs ──→ EMBEDDINGS → CHROMA → RAG

Core Modules

1. FIR & Crime Intelligence

The prototype supports FIR/case information such as:

FIR number

District and police station

Case type and sections

Place of occurrence

Informant, victim and accused

Contact/address information

Vehicle information

Case narrative

Vulnerability/connectivity indicators

Crime categories represented include women/children-related crime,
violent crime, property crime, financial/cyber crime and organized
crime.

2. Telecom Intelligence

SDR

Connects:

Person ↔ Phone Number

CDR

Represents communication relationships:

Person A ↔ Phone ↔ Person B

IPDR

Adds internet activity and time-based correlation.

3. Vehicle Intelligence

Integrates concepts from:

VAHAN

SARATHI

FASTag

ANPR

Example:

Person → Vehicle → FASTag Event → Location → Timestamp

The intelligence engine can surface ANPR vehicle-information mismatch
signals.

4. Financial Intelligence

The prototype connects financial entities through paths such as:

Person → Bank Account → UPI → Merchant → Crypto Exchange → Blockchain Transaction → Corporate Entity

Financial anomaly signals are generated using statistical behaviour.

5. Entity Resolution

The entity-resolution module includes:

Normalization

Soundex blocking

Levenshtein similarity

Jaro-Winkler similarity

Fellegi-Sunter probabilistic record linkage

Union-Find clustering

Confidence scoring

Evidence tracking

Ambiguity surfaced for investigator review

Entity-resolution results are investigative signals and require
calibration before production use.

6. Relationship Graph

Built directly from CSV datasets using NetworkX.

Node types

PERSON

PHONE

VEHICLE

ACCOUNT

LOCATION

CASE

Canonical identifiers such as phone numbers, vehicle registrations and
bank accounts can connect records across datasets.

The graph is persisted as JSON and visualized using PyVis.

7. Network Analytics

The prototype calculates:

Degree centrality

Betweenness centrality

Eigenvector centrality

Community detection

Bridge identification

Network statistics

Network prioritization/risk signals

These scores are analytical signals, not legal findings.

8. Intelligence Engine

Current signals include:

Communication spikes using z-scores

Financial anomalies using z-scores

Short contact chains such as A → B → C

Coordinated movement around toll locations

Repeated location loops

ANPR mismatch alerts

Alerts contain:

Alert ID · Type · Severity · Score · Confidence · Summary · Entities · Evidence

Severity levels:

LOW · MEDIUM · HIGH · CRITICAL

9. Timeline & Geospatial Intelligence

Events can be correlated by:

Case

Date/time

Event

Person

Location

Source

Risk/intelligence signal

Geospatial views can include incident locations, toll plazas, ANPR
cameras, telecom towers and financial counterparties.

10. Multimedia Digital Forensics

Audio --- BASIC

Current implementation includes:

SHA-256 evidence hash

UTC timestamp

Duration

Sample rate

Channels

Speech/silence segmentation

Mel spectrogram

MFCC extraction

JSON result persistence

Technologies include Librosa, Pydub, NumPy and SoundFile.

Speaker identity claims, speaker diarization and ENF matching are not
part of the current basic implementation.

Image --- BASIC

Current implementation includes:

SHA-256 evidence hash

EXIF extraction

GPS extraction

Capture timestamp

Camera make/model

Software tag

JPEG Error Level Analysis (ELA)

JSON result persistence

ELA is a heuristic and is not definitive proof of image manipulation.

Advanced PRNU and JPEG DCT analysis are future scope.

11. Legal & SOP RAG

Legal PDFs
   ↓
PyMuPDFLoader
   ↓
RecursiveCharacterTextSplitter
   ↓
Ollama Embeddings
   ↓
Chroma
   ↓
Semantic Retrieval
   ↓
RAG Assistant

Current configuration:

Embedding model: nomic-embed-text

Chunk size: 1500

Overlap: 150

Vector database: Chroma

Local embedding runtime: Ollama

12. FIR PDF Processing

The prototype also includes a document-processing path using:

PyPDF

PyTesseract

pdf2image

Groq

Llama 3.3 70B

This supports extraction and structuring of information from
unstructured FIR PDFs.

Data & Storage

CSV

Representative datasets:

complete_fir_dataset.csv
Subscriber_Detail_Records.csv
Call_Recording.csv
IP_Detail_Records.csv
Vehicle_Summary.csv
VAHAN_Database.csv
SARATHI_Database.csv
FASTag_Toll_Logs.csv
ANPR_Camera_Feeds.csv
Financial_Summary.csv
Bank_Statement_Records.csv

JSON

relationship_graph.json
network_analytics_report.json
intelligence_report.json
Audio_Analysis_results.json
Image_Analysis_results.json

Other outputs

network_map.html
FINAL_GOVERNMENT_CASE_INVESTIGATION_REPORT.txt

Case-level forensic results are stored under:

case_analysis/<Case_ID>/

Technology Stack

Programming & Data

Python

Pandas

NumPy

Graph & Network Intelligence

NetworkX

PyVis

AI / RAG

LangChain

Ollama

Chroma

nomic-embed-text

Documents

PyMuPDF

PyPDF

PyTesseract

pdf2image

Digital Forensics

Pillow

ExifRead

Librosa

Pydub

SoundFile

Matplotlib

AI-assisted FIR Processing

Groq

Llama 3.3 70B

Visualization

Plotly

PyVis

Project Structure

CIPHER/
├── main_investigation_pipeline.py
├── sihrelationship.py
├── sihentityresolution.py
├── sihnetworkanalytics.py
├── sihintelligenceengine.py
├── sihaudioanalysis.py
├── sihimageanalysis.py
├── sihforensicanalysis.py
├── sihindex.py
├── sihsoprag.py
├── sihdashboard.py
│
├── legal_docs/
├── legal_vector_db/
├── sample_evidence/
├── case_analysis/
├── data/
│
├── relationship_graph.json
├── network_analytics_report.json
├── intelligence_report.json
├── network_map.html
└── FINAL_GOVERNMENT_CASE_INVESTIGATION_REPORT.txt

Exact files can vary by project version/branch.

End-to-End Workflow

Register / Load Case
        ↓
FIR Processing
        ↓
Investigation Data
        ↓
Telecom + Vehicle + Financial Correlation
        ↓
Entity Resolution
        ↓
Relationship Graph
        ↓
Network Analytics
        ↓
Intelligence / Anomaly Detection
        ↓
Timeline + Geospatial Correlation
        ↓
Multimedia Forensics
        ↓
Legal / SOP RAG
        ↓
Investigator Review
        ↓
Investigation Report

Synthetic Data

The current prototype primarily uses synthetic/development datasets for
demonstration.

This enables testing of:

Cross-source relationships

Case linking

Entity resolution

Network analysis

Anomaly detection

Timeline correlation

Forensic processing

without requiring operational access to sensitive police databases.

The investigation pipeline also supports registering a custom FIR/case
and generating downstream intelligence without overwriting the
demonstration dataset.

Risk Assessment & Mitigation

Risk                        Mitigation

Data Privacy & Security     Encryption + Access Control
Data Quality Issues         Data Cleaning + Validation
False AI Predictions        Human-in-the-Loop Verification
Entity Matching Errors      Entity Resolution + Confidence Scoring
Integration Complexity      Standardized APIs + Data Formats
Large Data Volumes          Modular Processing + Graph Analytics
Legal / Compliance Issues   Legal & SOP Compliance
Model Bias                  Bias Testing + Model Validation
Cybersecurity Threats       Security Audits + Secure Access
Limited Real-Time Data      Modular Data Connectors
User Adoption               Investigator-Centric Training
Scalability                 Modular & Scalable Infrastructure
Evidence Integrity          Hashing + Audit Trail
Explainability              Evidence-backed Intelligence Signals

Responsible AI

CIPHER is an investigator-assistance system, not an autonomous
decision-maker.

Key principles:

AI outputs are investigative signals.

Confidence scores communicate uncertainty.

Evidence accompanies generated alerts where available.

Ambiguous entity matches are surfaced for review.

Network scores are not legal conclusions.

Forensic heuristics are not treated as definitive proof.

Sensitive data requires appropriate access controls.

Legal/SOP answers should be grounded in authorized source documents.

Human investigators remain responsible for interpretation and
decisions.

Research & Inspiration

CIPHER was conceptually inspired by publicly documented Indian
criminal-justice information systems and research in:

Government / Indian Systems

CCTNS --- Crime & Criminal Tracking Network & Systems

ICJS --- Interoperable Criminal Justice System

Maharashtra CID / CCTNS implementation

Public Ministry of Home Affairs and PIB material

Research Areas

Criminal network analysis

Graph embeddings

Knowledge graphs

Entity resolution

Digital forensics

Financial cybercrime investigation

Explainable AI

Human-in-the-loop AI

Anomaly detection

Multimedia forensics

Privacy and responsible AI

Key References

Graph Embeddings in Criminal Investigation --- Springer

Knowledge Graph-Based Digital Forensic Model for Criminal Network
Analysis

Deep Learning and Social Network-Based Forensic Data Mining

Modular AI Framework for Financial Cybercrime Investigation

AI, Cybercrime and Computer Forensics in the Indian Context

Explainable AI for Digital Investigations

The project uses these areas as research inspiration and does not claim
to reproduce the architecture or capabilities of government systems.

What Makes CIPHER Different?

CIPHER combines multiple investigative intelligence layers into one
workflow:

FIR
 │
 ├── Telecom
 │
 ├── Vehicle
 │
 ├── Financial
 │
 ├── Geospatial
 │
 ├── Relationship Graph
 │
 ├── Network Analytics
 │
 ├── Intelligence Engine
 │
 ├── Multimedia Forensics
 │
 └── Legal / SOP RAG
          ↓
  Investigator Support

Core uniqueness

One investigation workspace connecting structured crime data,
telecom, vehicles, finance, graph intelligence, geospatial evidence,
multimedia forensics and legal/SOP knowledge.

Future Scope

Production-grade secure APIs

Legally authorized live data connectors

Advanced graph machine learning

Speaker diarization

Advanced audio forensics / ENF analysis

PRNU image analysis

Advanced JPEG DCT analysis

Video forensic analysis

Chat/messaging forensic analysis

Deepfake detection

Advanced geospatial trajectory analysis

Real-time streaming intelligence

Calibrated ML risk models

Human feedback loops

Role-based investigation workflows

Immutable evidence audit trails

Large-scale distributed data infrastructure

Production authentication and authorization

Disclaimer

CIPHER is a prototype / research-oriented demonstration platform.

Demonstration datasets are synthetic or development datasets unless
explicitly stated otherwise.

AI outputs, anomaly scores, entity-resolution results, network scores
and forensic heuristics are intended to support investigation and
prioritization. They should not be treated as automatic proof of
criminal activity, legal findings, or a substitute for trained
investigators, forensic experts or judicial processes.

Deployment with real criminal-justice data would require appropriate
authorization, security controls, privacy safeguards, legal review, data
governance, validation and operational testing.

Project Vision

CIPHER

Connect. Investigate. Correlate. Detect.

Transform fragmented investigative evidence into connected,
explainable intelligence.
