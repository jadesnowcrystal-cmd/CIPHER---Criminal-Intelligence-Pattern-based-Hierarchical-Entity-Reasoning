# CIPHER

## Criminal Intelligence & Pattern-based Hierarchical Entity Reasoning

### Smart India Hackathon 2026

**Problem Statement ID:** 26189
**Problem Statement:** AI-Powered Criminal Network Analysis
**Theme:** Blockchain & Cybersecurity
**Category:** Software
**Team:** Ino_vexX

---

# 1. Abstract

CIPHER is an AI-powered criminal investigation and intelligence platform designed to help investigators analyse fragmented information from multiple sources through a unified workspace.

Criminal investigations often involve large volumes of FIR, telecom, vehicle, financial, geospatial and forensic information. CIPHER connects these different sources using entity resolution, relationship graphs, network analytics and intelligent pattern detection.

The platform identifies relationships between persons, phone numbers, vehicles, bank accounts, locations and cases. It can detect communication surges, financial anomalies, contact chains, coordinated movements, repeated location patterns and other investigative signals.

CIPHER also provides timeline and geospatial analysis, basic image and audio forensic analysis, and a RAG-based assistant for retrieving relevant information from legal documents and police SOPs.

The objective is to **connect fragmented information, uncover meaningful relationships and patterns, and provide investigators with actionable intelligence to support faster and more informed investigations.**

---

# 2. Problem Statement

Modern criminal investigations generate information from many independent sources. FIR records, telecom records, vehicle databases, financial transactions, surveillance information and forensic evidence are often stored or analysed separately.

This makes it difficult for investigators to:

* Connect information across different cases
* Identify hidden relationships between individuals
* Detect patterns across large datasets
* Correlate events occurring at different locations and times
* Identify links between financial, telecom and physical activities
* Analyse large volumes of information manually
* Quickly retrieve relevant legal and procedural information

The SIH problem focuses on using AI to support criminal network analysis and help investigators discover relationships that may not be obvious through conventional investigation methods.

---

# 3. Existing Problems and Challenges

The major challenges addressed by CIPHER are:

* Fragmented investigation data
* Large volumes of unstructured and structured information
* Difficulty in cross-case correlation
* Duplicate or inconsistent entity information
* Hidden relationships between suspects and other entities
* Manual identification of suspicious patterns
* Difficulty in correlating events across time and location
* Limited integration of forensic information with investigation data
* Time-consuming retrieval of relevant SOPs and legal information
* Risk of human error during large-scale data analysis

---

# 4. Proposed Solution

CIPHER provides a unified investigation platform that brings together information from multiple investigation domains.

A case enters the investigation pipeline, where relevant entities and information are extracted and structured. Entity resolution is then used to identify possible connections between records.

The connected information is represented through a relationship graph. Network analytics and an intelligence engine analyse this graph to identify important connections, communities and suspicious patterns.

Timeline and geospatial analysis provide additional context by correlating activities according to time and location.

The platform also provides digital forensic analysis for selected image and audio evidence and a RAG-based legal/SOP assistant that retrieves relevant information from police manuals and legal documents.

The overall approach is:

**Collect → Structure → Resolve → Connect → Analyse → Correlate → Investigate**

---

# 5. Objectives

The main objectives of CIPHER are:

1. Integrate fragmented investigation data into a unified platform.
2. Establish relationships between entities across different datasets.
3. Identify hidden connections across cases.
4. Detect suspicious patterns and anomalies automatically.
5. Provide network-based analysis of criminal relationships.
6. Correlate events through timeline and geospatial analysis.
7. Support basic digital forensic analysis.
8. Provide relevant legal and SOP information through RAG.
9. Reduce manual effort in large-scale data analysis.
10. Help investigators make faster and more informed decisions.

---

# 6. Key Features

CIPHER provides the following major capabilities:

* FIR and case intelligence
* Telecom intelligence
* Vehicle intelligence
* Financial intelligence
* Entity resolution
* Relationship graph generation
* Network analytics
* Suspicious activity detection
* Timeline correlation
* Geospatial analysis
* Image forensic analysis
* Audio forensic analysis
* Legal and SOP RAG assistant
* Cross-case relationship analysis
* Investigator-focused intelligence dashboard

---

# 7. System Architecture

The CIPHER architecture consists of multiple interconnected layers.

Investigation data such as FIR, telecom, vehicle and financial records first enters the data processing pipeline.

The processed information is passed to the entity-resolution layer, which identifies and connects potentially matching entities.

The resulting information is used to build a relationship graph containing entities such as persons, phones, vehicles, accounts, locations and cases.

The graph is then analysed using network analytics and the intelligence engine.

In parallel, forensic evidence is processed through the digital forensics modules, while legal and SOP documents are processed through the RAG pipeline.

The resulting intelligence is presented to the investigator through the application layer. The architecture described in the project presentation follows this flow from case data through entity extraction, investigation, graph/geo analysis, historical correlation, forensic evidence and RAG-based SOP support. 

---

# 8. Detailed Working / Workflow

### Step 1 – Case Input

A new FIR or investigation case enters the system along with available investigation data.

### Step 2 – Data Processing

The system processes information from different sources and converts it into structured datasets.

### Step 3 – Entity Identification

Important entities such as:

* Persons
* Phone numbers
* Vehicles
* Bank accounts
* Locations
* Cases

are identified from the available records.

### Step 4 – Entity Resolution

CIPHER compares records and identifies possible matches between entities appearing in different datasets or cases.

### Step 5 – Relationship Mapping

The resolved entities are connected through a relationship graph.

For example:

**Person → Phone → Call → Location → Vehicle → Account → Transaction**

### Step 6 – Network Analysis

The relationship graph is analysed to identify:

* Highly connected entities
* Important intermediary entities
* Communities
* Bridges between groups
* Network-level patterns

### Step 7 – Intelligence Analysis

The intelligence engine identifies statistical and behavioural signals such as communication spikes, financial anomalies, contact chains, coordinated movements and repeated location patterns.

### Step 8 – Timeline and Geospatial Analysis

Events are correlated according to time and location to provide additional investigation context.

### Step 9 – Digital Forensics

Available image and audio evidence can be processed for relevant metadata and forensic indicators.

### Step 10 – Legal/SOP Assistance

The RAG system retrieves relevant information from legal and police SOP documents.

### Step 11 – Investigator Workspace

The combined results are presented to investigators for further analysis and verification.

---

# 9. Major Modules

## 9.1 FIR & Case Intelligence

The FIR module forms the foundation of the investigation workflow.

It organises information such as:

* FIR number
* Police station
* District
* Case type
* Legal sections
* Informant
* Victim
* Accused
* Contact information
* Locations
* Vehicles
* Case narrative

---

## 9.2 Telecom Intelligence

The telecom module connects subscriber, communication and internet activity.

It works with:

* Subscriber Detail Records
* Call Detail Records
* IP Detail Records

This allows relationships between persons and communication endpoints to be incorporated into the investigation graph.

---

## 9.3 Vehicle Intelligence

Vehicle intelligence combines information from:

* VAHAN
* SARATHI
* FASTag
* ANPR

This enables investigators to correlate vehicles with persons, locations and timestamps.

For example, a vehicle appearing in multiple locations or an ANPR-related inconsistency can become an investigative signal.

---

## 9.4 Financial Intelligence

The financial module analyses relationships between people, accounts and transactions.

The investigation flow can include:

**Person → Bank Account → UPI → Merchant → Financial Entity**

The system can identify unusual transaction behaviour and financial anomalies for further investigation.

---

## 9.5 Entity Resolution

Entity resolution is used to determine whether records from different sources may represent the same real-world entity.

CIPHER uses techniques including:

* Name normalization
* Soundex blocking
* Levenshtein similarity
* Jaro-Winkler similarity
* Fellegi-Sunter probabilistic matching
* Union-Find clustering
* Confidence scoring

Ambiguous matches can be surfaced for human verification instead of automatically treating every possible match as confirmed.

---

## 9.6 Relationship Graph

CIPHER uses a graph-based representation to connect entities across datasets.

Major entity types include:

* PERSON
* PHONE
* VEHICLE
* ACCOUNT
* LOCATION
* CASE

Canonical identifiers such as phone numbers, vehicle registrations and account numbers help establish relationships across different records and cases.

---

## 9.7 Network Analytics

Network analytics helps identify important structural relationships within the investigation graph.

The system uses:

* Degree centrality
* Betweenness centrality
* Eigenvector centrality
* Community detection
* Bridge identification
* Network statistics

These results are intended to help investigators prioritise areas for further examination.

---

## 9.8 Intelligence Engine

The intelligence engine identifies investigative signals using statistical and relationship-based analysis.

Examples include:

* Communication spikes
* Financial anomalies
* Contact chains
* Coordinated movements
* Repeated location patterns
* ANPR plate mismatch signals

The resulting alerts contain information such as severity, score, confidence, entities and supporting evidence.

---

## 9.9 Timeline & Geospatial Analysis

CIPHER correlates investigation events according to:

* Date and time
* Person
* Case
* Location
* Event
* Source

Geospatial analysis helps investigators understand the movement and geographical relationships between entities and events.

---

## 9.10 Digital Forensics

The current prototype provides basic image and audio forensic capabilities.

### Image Analysis

The image module supports:

* SHA-256 hashing
* EXIF metadata extraction
* GPS information
* Capture timestamp
* Camera information
* JPEG Error Level Analysis

### Audio Analysis

The audio module supports:

* SHA-256 hashing
* Audio metadata extraction
* Speech/silence segmentation
* Mel spectrogram generation
* MFCC analysis
* Forensic result storage

Advanced multimedia forensics are planned as future enhancements.

---

## 9.11 Legal & SOP RAG

CIPHER includes a Retrieval-Augmented Generation pipeline for legal and procedural documents.

The process is:

**Legal/SOP Documents → Text Extraction → Chunking → Embeddings → Vector Database → Retrieval → AI Assistant**

This allows investigators to retrieve relevant information from police manuals, SOPs and legal documents while analysing a case.

---

# 10. Technology Stack

### Programming & Data Processing

* Python
* Pandas
* NumPy

### AI & RAG

* LangChain
* Ollama
* ChromaDB
* Ollama Embeddings
* Groq
* Llama-based models

### Graph & Network Analysis

* NetworkX
* PyVis

### Document Processing

* PyMuPDF
* PyPDF
* Tesseract OCR
* pdf2image

### Digital Forensics

* Pillow
* ExifRead
* Librosa
* Pydub
* SoundFile
* Matplotlib

### Visualization

* Plotly
* PyVis
* Matplotlib

---

# 11. Feasibility & Viability

CIPHER is feasible because it is built using established AI, data-processing, graph-analysis and document-processing technologies.

### Technical Feasibility

* Proven AI technologies
* Python-based modular architecture
* Automated data processing
* Multi-source data integration
* Graph-based relationship analysis
* Local RAG capability
* Expandable forensic modules

### Integration Feasibility

The modular architecture allows additional data sources and investigation systems to be integrated through standardised interfaces.

### Scalability

The current prototype is designed so that individual components can be replaced or upgraded as the system scales. Future development can introduce scalable graph databases and larger distributed processing systems.

### Operational Feasibility

The platform is designed around an investigator-centric workflow, allowing investigators to review relationships, patterns, alerts and supporting information in one workspace.

---

# 12. Risks & Mitigation

| Risk                    | Mitigation                                    |
| ----------------------- | --------------------------------------------- |
| Data Privacy & Security | Encryption and access control                 |
| Poor Data Quality       | Data cleaning and validation                  |
| Incorrect AI Results    | Human-in-the-loop verification                |
| Entity Matching Errors  | Probabilistic matching and confidence scoring |
| Integration Complexity  | Standardised APIs and data formats            |
| Cybersecurity Threats   | Regular security audits                       |
| Model Bias              | Bias testing and model validation             |
| Evidence Tracking       | Audit logs and evidence tracking              |
| User Adoption           | Role-based user training                      |
| System Scalability      | Modular and scalable architecture             |
| Legal/Compliance Issues | Legal and SOP compliance                      |

The project presentation identifies data privacy, legal/compliance requirements, integration complexity and cybersecurity as major risks, with mitigation through access control, validation, human verification, confidence scoring, standardised interfaces, audits and evidence tracking. 

---

# 13. Impact & Benefits

CIPHER is designed to provide the following benefits:

### Faster Investigation

Automated processing and cross-source correlation reduce the need for investigators to manually search multiple datasets.

### Hidden Relationship Discovery

Graph-based analysis can expose relationships that may not be immediately visible when records are examined independently.

### Better Pattern Detection

Large datasets can be analysed for communication, financial, movement and location patterns.

### Improved Evidence Correlation

Information from different investigation sources can be connected through common entities and timelines.

### Reduced Manual Effort

Automated extraction, entity matching and analysis can reduce repetitive investigative work.

### Better Decision Support

Investigators receive structured intelligence and supporting evidence that can assist further investigation.

### Legal & SOP Support

The RAG assistant provides easier access to relevant procedural and legal information.

---

# 14. Uniqueness / Innovation

CIPHER combines several investigation capabilities into one integrated platform.

Its key differentiators include:

* Cross-domain investigation data fusion
* Probabilistic entity resolution
* Relationship graph analysis
* Timeline correlation
* Pattern and anomaly detection
* Geospatial intelligence
* Digital forensic analysis
* AI-assisted legal and SOP retrieval
* Investigator-focused intelligence workflow

The project presentation specifically positions CIPHER around network graph analysis, cross-domain data fusion, probabilistic entity resolution, timeline correlation, pattern detection, RAG-based law/SOP assistance and forensic analysis. 

---

# 15. Future Scope

Future development of CIPHER can include:

* Integration with ICJS pillars for authorised real-world data flow
* Scalable graph databases such as Neo4j
* Distributed processing using technologies such as Spark
* GNN-based criminal network analysis
* Facial recognition and biometric matching
* Advanced multimedia forensics
* Evidence verification
* Large-scale cross-state pattern recognition
* Real-time intelligence processing

These future directions are also identified in the project's technical approach, including ICJS integration, scalable graph infrastructure, GNN-based analysis, biometric matching and advanced multimedia forensics. 

---

# 16. Research & References

The project is informed by research and publicly available material related to:

* FIR and criminal case data
* CDR and telecom intelligence
* Financial investigation
* Surveillance and investigation workflows
* CCTNS
* ICJS
* BNSS and relevant legal frameworks
* Police SOPs
* BPR&D publications
* Criminal network analysis
* Knowledge graphs
* Entity resolution
* Digital forensics
* AI-based investigation systems

The project also references existing investigation and intelligence platforms such as **Palantir Gotham** and **IBM i2 Analyst's Notebook** for comparative understanding of capabilities. 

---

# 17. Project Status

CIPHER currently exists as a working prototype with multiple integrated investigation modules.

### Current Status

* Investigation pipeline — Working
* FIR/case data processing — Implemented
* Entity resolution — Implemented
* Relationship graph — Implemented
* Network analytics — Implemented
* Intelligence engine — Implemented
* Timeline analysis — Prototype
* Geospatial analysis — Prototype
* Image forensics — Basic implementation
* Audio forensics — Basic implementation
* Legal/SOP RAG — Prototype

The project presentation estimates the overall prototype at approximately **75–80% readiness**, while production readiness is currently estimated at approximately **15–20%**, reflecting the additional requirements for real-world deployment, integration, security and validation. 

---

# 18. Team

## Ino_vexX

**Smart India Hackathon 2026**

**Problem Statement ID:** 26189
**Problem Statement:** AI-Powered Criminal Network Analysis
**Theme:** Blockchain & Cybersecurity
**Category:** Software

---

# 19. Disclaimer

CIPHER is a research and demonstration prototype designed to support criminal investigation and intelligence analysis.

Its AI predictions, network scores, anomaly alerts, entity-resolution results and forensic indicators are intended as **investigative support signals** and should not be treated as automatic proof of criminal activity or as legal findings.

Real-world deployment would require appropriate authorisation, data governance, privacy and security controls, legal review, operational validation and human oversight.
