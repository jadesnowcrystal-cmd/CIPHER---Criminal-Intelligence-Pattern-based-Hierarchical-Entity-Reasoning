::: {align="center"}

CIPHER

Criminal Intelligence & Pattern-based Hierarchical Entity Reasoning

AI-Powered Criminal Investigation & Digital Forensics Platform

Smart India Hackathon 2026 · Problem Statement 26189

Team Ino_vexX

:::

 What is CIPHER?

CIPHER is a modular, AI-assisted investigation platform that
connects fragmented criminal-investigation data into one intelligence
workflow.

 Connects people, phones, vehicles, accounts, locations and cases

Detects patterns, anomalies and hidden relationships

Performs criminal-network and graph analysis

Correlates timelines and locations

Supports basic image and audio forensics

 Retrieves relevant legal/SOP information using RAG

Produces evidence-backed investigative signals

Fragmented Data → Connected Entities → Intelligence → Investigator

Architecture

flowchart LR
    A[FIR / Case Data] --> B[Investigation Pipeline]
    B --> C[Telecom]
    B --> D[Vehicle]
    B --> E[Financial]
    C --> F[Entity Resolution]
    D --> F
    E --> F
    F --> G[Relationship Graph<br/>NetworkX]
    G --> H[Network Analytics]
    G --> I[Intelligence Engine]
    G --> J[Timeline & Geospatial]
    K[Image / Audio Evidence] --> L[Forensic Analysis]
    M[Legal & SOP PDFs] --> N[RAG Pipeline]
    H --> O[Investigator Workspace]
    I --> O
    J --> O
    L --> O
    N --> O

Investigation Flow

Case → Extract → Resolve → Connect → Analyse → Correlate → Assist

Key Modules

FIR & Case Intelligence

Processes case information and provides the foundation for downstream
investigation.

Telecom Intelligence

SDR, CDR and IPDR analysis for communication relationships and activity
patterns.

Vehicle Intelligence

VAHAN, SARATHI, FASTag and ANPR correlation with people, locations and
timestamps.

Financial Intelligence

Bank, UPI, merchant, cryptocurrency and related financial-record
correlation.

Entity Resolution

Fellegi-Sunter, Levenshtein, Jaro-Winkler, Soundex and Union-Find
clustering with confidence/evidence scoring.

 Relationship & Network Analysis

NetworkX-based graphs with centrality, communities, bridges and
relationship analysis.

Intelligence Engine

Investigative signals for communication spikes, financial anomalies,
contact chains, coordinated movement, repeated locations and ANPR
mismatches.

Timeline & Geospatial Intelligence

Correlates events by time, person, case, location and source.

Digital Forensics

Image: EXIF, GPS metadata and JPEG ELA.
Audio: segmentation, mel spectrograms, MFCCs and evidence hashing.

Legal & SOP RAG

Retrieves relevant information from police manuals, SOPs and legal
documents using a local RAG pipeline.

Tech Stack

Layer                            Technologies

Language & Data              Python · Pandas · NumPy
Graph & Network              NetworkX · PyVis
AI / RAG                     LangChain · Ollama · Chroma · nomic-embed-text
Documents                    PyMuPDF · PyPDF · PyTesseract · pdf2image
Image Forensics              Pillow · ExifRead · NumPy
Audio Forensics              Librosa · Pydub · SoundFile · Matplotlib
AI-assisted FIR Processing   Groq · Llama 3.3 70B
Visualization                Plotly · PyVis

End-to-End Workflow

FIR / Case
    ↓
Data Processing
    ↓
Entity Extraction & Resolution
    ↓
Relationship Graph
    ↓
Network + Intelligence Analysis
    ↓
Timeline + Geospatial Correlation
    ↓
Forensic Analysis
    ↓
Legal / SOP RAG
    ↓
Investigator

 Example Investigation Relationship

Person
  ├── Phone ──→ CDR / IPDR
  ├── Vehicle ──→ FASTag / ANPR
  ├── Account ──→ Bank / UPI
  └── Location ──→ Timeline / Geo Analysis
                         ↓
                    Other Person / Case

CIPHER uses these relationships to support cross-source and cross-case
investigation.

 Responsible AI

CIPHER is an investigator-assistance system, not an autonomous
decision-maker.

AI outputs are investigative signals, not legal conclusions.

Confidence and evidence are retained where applicable.

Ambiguous entity matches can be reviewed by investigators.

Forensic heuristics are not treated as definitive proof.

Real-world deployment requires appropriate authorization, privacy,
security and legal controls.

Future Scope

Integration with ICJS pillars where legally authorized

Scalable graph infrastructure such as Neo4j / Spark

GNN-based network pattern recognition

Advanced multimedia forensics

Facial and biometric matching

Real-time intelligence pipelines

Production-grade security and access control

📚 Research & Inspiration

CIPHER draws inspiration from publicly documented Indian
criminal-justice systems such as CCTNS and ICJS, together with
research in:

Criminal Network Analysis · Knowledge Graphs · Entity Resolution ·
Digital Forensics · Explainable AI · Anomaly Detection

The prototype primarily uses synthetic/development data and does not
claim to reproduce government systems.

 Project Status

Type                            Working research/demo prototype

Data                            Primarily synthetic/development
datasets

Architecture                    Modular and extensible

Focus                           Criminal intelligence + network
analysis + digital forensics

::: {align="center"}

 Team Ino_vexX

CIPHER

Connect · Investigate · Correlate · Detect

Transforming fragmented investigation data into connected
intelligence.
:::
