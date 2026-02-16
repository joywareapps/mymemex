# Project Librarian: Product Requirements Document (PRD)

**Version:** 1.0
**Status:** Draft / Phase 4 - Functional Specification
**Codename:** Librarian

---

## 1. Executive Summary

Librarian is a sovereign document intelligence platform designed to transform unstructured personal archives (PDFs, scans, images) into a searchable, agentic database. Unlike cloud-first solutions, Librarian prioritizes privacy by allowing users to toggle between cloud-based high-fidelity models and local, air-gapped LLMs/OCR engines.

---

## 2. System Architecture Overview

The system follows a **"Hybrid Memory"** architecture:

### Components

| Component | Responsibility |
|-----------|----------------|
| **Watcher** | Monitors local/NAS directories for new files |
| **Ingestion Worker** | Handles file queuing, hashing (deduplication), and metadata extraction |
| **Intelligence Core** | Executes OCR (Tesseract vs. Cloud Vision) and Embedding generation |
| **Storage Layer** | SQLite (metadata/relationships) + ChromaDB/pgvector (semantic chunks) |
| **Agentic Layer** | Manages multi-hop queries and autonomous file organization |

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                          │
│  (CLI / Web UI / API)                                           │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                       AGENTIC LAYER                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Query Agent  │  │ Classify     │  │ Organize     │          │
│  │              │  │ Agent        │  │ Agent        │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     INTELLIGENCE CORE                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐          │
│  │ Local OCR    │  │ Cloud OCR    │  │ Embedding    │          │
│  │ (Tesseract)  │  │ (Vision API) │  │ (nomic/etc)  │          │
│  └──────────────┘  └──────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      STORAGE LAYER                              │
│  ┌──────────────────┐  ┌──────────────────┐                    │
│  │ SQLite           │  │ ChromaDB/        │                    │
│  │ (metadata)       │  │ pgvector         │                    │
│  └──────────────────┘  └──────────────────┘                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    INGESTION PIPELINE                           │
│  ┌──────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Watcher  │──│ Deduplication│──│ Processing   │              │
│  │          │  │ (SHA-256)    │  │ Queue        │              │
│  └──────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Epic 1: Intelligent Ingestion & Monitoring

### Feature: Real-time Archive Synchronization
The system must maintain a 1:1 reflection of the physical file state on the NAS.

### User Story 1.1: New Document Discovery
**Scenario:** Immediate indexing of new records.
- **Given:** The Librarian service is running and pointed at `/mnt/nas/documents`
- **When:** A user saves `medical_report_2024.pdf` to the folder
- **Then:** The system detects the file change, generates a unique SHA-256 hash, and queues it for processing within 5 seconds

### User Story 1.2: Duplicate Management
**Scenario:** Prevent redundant vector pollution.
- **Given:** `invoice_001.pdf` is already indexed
- **When:** The user uploads the same file into a different sub-folder
- **Then:** Librarian identifies the hash collision and links the new file path to the existing database entry rather than re-running OCR

---

## 4. Epic 2: Sovereign OCR & Privacy Control

### Feature: Configurable Intelligence
Users must have granular control over where their data is processed.

### User Story 2.1: Local-First Processing
**Scenario:** Air-gapped financial indexing.
- **Given:** A document is tagged as "Sensitive" or the global policy is set to "Local"
- **When:** Processing starts
- **Then:** Librarian utilizes PaddleOCR or Llama-3-Vision (local) for text extraction and `nomic-embed-text` for vectors, ensuring zero data egress

### User Story 2.2: Cloud-Enhanced Accuracy
**Scenario:** Difficult-to-read handwritten notes.
- **Given:** Local OCR confidence is below a defined threshold (e.g., < 70%)
- **When:** The user explicitly approves a "Cloud Boost" for this specific file
- **Then:** The file is temporarily sent to AWS Textract or Google Vision API for high-fidelity extraction before being purged from the cloud

---

## 5. Epic 3: Semantic Discovery & Agentic Search

### Feature: RAG-Powered Natural Language Interface
Users should interact with their archive as if it were a knowledgeable person.

### User Story 3.1: Specific Detail Retrieval
**Scenario:** Finding hidden policy details.
- **Given:** Multiple insurance documents are indexed
- **When:** The user asks, "Does my car insurance cover rental cars in Europe?"
- **Then:** The LLM agent retrieves the specific "Coverage" section, cites the exact document and page number, and summarizes the answer

### User Story 3.2: Multi-Document Analysis
**Scenario:** Annual spending summary.
- **Given:** 12 months of utility bills
- **When:** The user asks, "Which month had the highest energy consumption last year?"
- **Then:** An agent identifies all files categorized as "Utility Bill," extracts the "Total kWh" value from each, and provides a comparative answer

---

## 6. Epic 4: Autonomous Organization

### Feature: Agentic Rule Engine
The system should suggest (or execute) organizational structures based on content.

### User Story 4.1: Semantic Auto-Tagging
**Scenario:** Automated labeling.
- **Given:** A document containing terms like "Premium," "Policy Number," and "Beneficiary" is scanned
- **When:** The Classification Agent analyzes the text
- **Then:** It automatically applies the tags `#Insurance` and `#Legal`

### User Story 4.2: Proactive Filing
**Scenario:** Maintaining folder hygiene.
- **Given:** A user has a folder structure `/Taxes/{Year}`
- **When:** A document is identified as a 2024 Tax Statement
- **Then:** Librarian suggests moving the file from `/Inbox` to `/Taxes/2024` and waits for user confirmation

---

## 7. Technical Constraints & Non-Functionals

| Constraint | Requirement |
|------------|-------------|
| **Latency** | Semantic search responses under 3 seconds for local queries |
| **Scalability** | Handle up to 50,000 documents without significant indexing degradation |
| **Portability** | Entire stack deployable via `docker-compose` |
| **Target Hardware** | Synology NAS (16GB RAM) or dedicated local server |

---

## 8. Technology Stack (Proposed)

### Core
- **Language:** Python 3.11+ or Rust
- **Watcher:** `watchdog` (Python) or `notify` (Rust)
- **Queue:** Redis or SQLite-based job queue

### OCR
- **Local:** Tesseract, PaddleOCR
- **Cloud:** AWS Textract, Google Vision API

### Embeddings & Vector Store
- **Local Models:** `nomic-embed-text`, `bge-small-en`
- **Vector DB:** ChromaDB (embedded) or pgvector (PostgreSQL)

### LLM Integration
- **Local:** Ollama (Llama 3, Mistral)
- **Cloud:** OpenAI API, Anthropic API

### Database
- **Metadata:** SQLite
- **Relationships:** SQLite with FTS5

---

## 9. Milestones

| Phase | Deliverable | Status |
|-------|-------------|--------|
| **M1** | Project skeleton + watcher MVP | 🔲 Not Started |
| **M2** | Ingestion pipeline + SQLite metadata | 🔲 Not Started |
| **M3** | Local OCR integration + deduplication | 🔲 Not Started |
| **M4** | Vector storage + semantic search | 🔲 Not Started |
| **M5** | RAG query interface | 🔲 Not Started |
| **M6** | Auto-tagging + classification agents | 🔲 Not Started |
| **M7** | Cloud OCR fallback + privacy controls | 🔲 Not Started |
| **M8** | Docker compose + deployment docs | 🔲 Not Started |
