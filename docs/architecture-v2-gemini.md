# Librarian v2 Architecture Proposal

**Date:** 2026-02-16

## 1. Python Library Choices with Justification

*   **Primary Language:** Python 3.11+
    *   **Justification:** Chosen for its extensive ecosystem, excellent support for asynchronous programming (essential for I/O-bound tasks like file watching and API calls), ease of integration with AI and database libraries, and rapid prototyping capabilities. This aligns with ADR-004.

*   **AI Abstraction:** `litellm`
    *   **Justification:** This library is critical for supporting the "Local-First Privacy Model" and enabling "Provider Agnosticism" (Constraints 1.1, 1.2, 1.3; ADR-005). It allows the system to seamlessly switch between local Ollama (default) and cloud-based LLM/embedding providers (OpenAI, Anthropic, etc.) without code changes, facilitating graceful degradation when AI services are unavailable (Constraint 2).

*   **HTTP Client:** `httpx`
    *   **Justification:** A modern, asynchronous HTTP client necessary for efficient communication with external AI APIs (Ollama, cloud providers) and for potential WebSocket communication.

*   **File Watching:** `watchdog`
    *   **Justification:** Provides a robust, cross-platform API for monitoring file system events. This enables the "Real-time Archive Synchronization" feature, ensuring new documents are detected and queued for processing promptly (PRD Epic 1).

*   **Data Serialization & Validation:** `pydantic`
    *   **Justification:** Essential for defining clear data schemas for API requests/responses, internal data models, and queue messages. It ensures data integrity and simplifies development.

*   **Queue Management:** (Conceptual Implementation)
    *   **Justification:** A persistent, retryable, and prioritized queue is required for managing AI-dependent tasks. This can be implemented using `SQLAlchemy` with SQLite for persistence, or a more robust solution like Redis if advanced queuing features are needed. The core requirement is resilience against LLM unavailability and service restarts (Constraint 2.2).

*   **Forbidden Libraries:** `sentence-transformers`, `transformers`, `torch`, `tensorflow`.
    *   **Justification:** To strictly adhere to Constraint 1.1 ("No In-Process AI Dependencies"). Including these would violate the goal of keeping the application lightweight, deployment flexible, and allowing users to choose their AI hardware/providers independently. All AI model interactions must occur via external HTTP APIs.

---

## 2. Data Flow Architecture

The Librarian platform employs a layered, hybrid architecture designed for privacy, flexibility, and resilience.

**2.1. Ingestion Pipeline:**
1.  **File Watching:** The `watchdog` library monitors specified directories for new or modified files.
2.  **Deduplication:** For each new file, its SHA-256 hash is computed. If the hash already exists in the SQLite metadata store, the file is considered a duplicate. The new file path is linked to the existing record, preventing redundant processing and vector pollution (PRD User Story 1.2; ADR-006).
3.  **Processing Queue:** For unique files, AI-dependent tasks (embedding, classification, OCR if cloud fallback is needed) are added to a persistent, retryable queue. This queue ensures tasks survive restarts and allows for graceful degradation when AI services are unavailable (Constraint 2.2). Tasks are prioritized (e.g., new uploads over backfill).

**2.2. Intelligence Core:**
*   **Optical Character Recognition (OCR):**
    *   **Primary:** Utilizes local OCR engines like Tesseract or PaddleOCR. This ensures that sensitive documents remain within the user's network, fulfilling the "Local-First Privacy Model" (PRD User Story 2.1; ADR-005).
    *   **Fallback:** Offers optional cloud-based OCR (AWS Textract, Google Vision API) as a fallback for improved accuracy on challenging documents. This requires explicit user opt-in and is designed to be temporary, with data purged after processing (PRD User Story 2.2; ADR-005).
*   **Embedding Generation:**
    *   Leverages `litellm` to interact with the configured embedding model. By default, this will be a local model served via Ollama (e.g., `nomic-embed-text`).
    *   Supports batch processing of documents to optimize performance, especially when dealing with large volumes.

**2.3. Agentic Layer:**
*   **Query Agent:** Orchestrates complex queries. It retrieves relevant document chunks from ChromaDB based on semantic similarity, constructs prompts (potentially using RAG techniques), and sends them to the configured LLM via `litellm`.
*   **Classification Agent:** Analyzes document content to auto-tag files or suggest categories, leveraging LLMs for intelligent interpretation (PRD Epic 4; User Story 4.1).
*   **Organization Agent:** Proposes actions for file management, such as suggesting moves to appropriate folders based on content, awaiting user confirmation (PRD Epic 4; User Story 4.2).

**2.4. Storage Layer:**
*   **SQLite:** The primary database for all structured metadata. This includes file paths, SHA-256 hashes, timestamps, OCR results, user-defined tags, processing status, and relationships between documents. Its built-in FTS5 extension provides robust keyword search capabilities (PRD Epic 1; ADR-002).
*   **ChromaDB:** Acts as the vector database, storing document text chunks alongside their generated embeddings. This is crucial for enabling efficient semantic search and retrieval (PRD Epic 3; ADR-003). `pgvector` is a supported alternative if a PostgreSQL instance is already in use.

**Data Flow Diagram:**

```mermaid
graph TD
    A[User Files (NAS/Local)] --> B(Watcher);
    B --> C{SHA-256 Hash};
    C -- New Hash --> D[Processing Queue (Persistent)];
    C -- Existing Hash --> E[SQLite Metadata DB];
    E --> F(Link to Existing Record);
    D --> G{Intelligence Core};
    G -- OCR --> H[Local OCR (Tesseract/Paddle)];
    G -- OCR Fallback --> I[Cloud OCR (AWS/GCP)];
    G -- Embeddings --> J[LLM/Embedding API (via LiteLLM)];
    H --> K[SQLite Metadata DB];
    I --> K;
    J --> L[ChromaDB (Vectors)];
    J --> M[SQLite Metadata DB];
    M --> N[Agentic Layer (Query/Classify/Organize)];
    N --> O[User Interface (CLI/Web/API)];
    L --> N;
    E --> N;
```

---

## 3. Database Schema (SQLite + ChromaDB)

**3.1. SQLite Schema (Metadata)**

The SQLite database will store comprehensive metadata for each document.

*   **`documents` Table:**
    *   `id` (INTEGER, PRIMARY KEY AUTOINCREMENT)
    *   `file_path` (TEXT, NOT NULL, UNIQUE) - Absolute path to the file.
    *   `sha256_hash` (TEXT, NOT NULL, INDEXED) - SHA-256 hash for deduplication.
    *   `filename` (TEXT, NOT NULL)
    *   `file_size` (INTEGER)
    *   `mime_type` (TEXT)
    *   `created_at` (TIMESTAMP) - Original file creation time.
    *   `modified_at` (TIMESTAMP) - Last modification time.
    *   `indexed_at` (TIMESTAMP) - When the document was first indexed.
    *   `last_processed_at` (TIMESTAMP) - Last time processing was attempted.
    *   `ocr_confidence` (REAL) - Average confidence from OCR (if applicable).
    *   `status` (TEXT) - Processing status (e.g., 'PENDING', 'PROCESSING', 'EMBEDDING', 'CLASSIFYING', 'COMPLETE', 'FAILED', 'WAITING_LLM').
    *   `error_message` (TEXT) - Details if processing failed.

*   **`document_chunks` Table:** (Optional, if not all text is stored directly in ChromaDB)
    *   `id` (INTEGER, PRIMARY KEY AUTOINCREMENT)
    *   `document_id` (INTEGER, FOREIGN KEY to `documents.id`)
    *   `chunk_text` (TEXT) - The extracted text chunk.
    *   `chunk_index` (INTEGER) - Order of the chunk within the document.
    *   `vector_id` (TEXT, UNIQUE) - Reference to the vector in ChromaDB.

*   **`tags` Table:**
    *   `id` (INTEGER, PRIMARY KEY AUTOINCREMENT)
    *   `name` (TEXT, NOT NULL, UNIQUE) - Tag name (e.g., "Invoice", "Medical", "Finance").

*   **`document_tags` Table:** (Many-to-many relationship)
    *   `document_id` (INTEGER, FOREIGN KEY to `documents.id`)
    *   `tag_id` (INTEGER, FOREIGN KEY to `tags.id`)
    *   PRIMARY KEY (`document_id`, `tag_id`)

*   **`file_properties` Table:** (For custom/auto-extracted metadata)
    *   `id` (INTEGER, PRIMARY KEY AUTOINCREMENT)
    *   `document_id` (INTEGER, FOREIGN KEY to `documents.id`)
    *   `property_name` (TEXT, NOT NULL) - e.g., "Invoice Number", "Policy Type", "Sender".
    *   `property_value` (TEXT)

**Full-Text Search (FTS5):** The `documents` table (or a dedicated `fts_documents` table) will be configured with an FTS5 virtual table to enable fast keyword searches across extracted text content.

**3.2. ChromaDB Schema (Vector Storage)**

ChromaDB will store document embeddings and their associated metadata for semantic search.

*   **Collection:** A primary collection will be used, e.g., `document_embeddings`.
*   **Documents:** Each entry in ChromaDB will represent a chunk of text from a document.
    *   **`id`:** A unique identifier for the embedding, often derived from document ID and chunk index (e.g., `doc_id_chunk_idx`).
    *   **`embedding`:** The vector representation of the text chunk.
    *   **`metadata`:** Crucial for linking back to the source document and providing context for search results. This will include:
        *   `document_id`: Reference to the SQLite `documents` table ID.
        *   `file_path`: The original file path.
        *   `chunk_index`: The sequential order of this chunk within the document.
        *   `document_name`: The filename.
        *   `source_page`: The page number where the chunk originated (if applicable).
        *   `extracted_text`: The actual text of the chunk for display/preview.
        *   `tags`: Any relevant tags associated with the document.

---

## 4. API Surface (REST + WebSocket)

The Librarian platform will expose APIs to allow programmatic interaction and real-time status updates.

*   **REST API:**
    *   **Purpose:** Management, CRUD operations on documents and metadata, configuration.
    *   **Endpoints (Examples):**
        *   `GET /documents`: List all documents with filtering (tags, status, path).
        *   `GET /documents/{id}`: Get details for a specific document.
        *   `POST /documents/upload`: Manually upload a file (though primary ingest is watch-based).
        *   `PUT /documents/{id}/tags`: Add/remove tags for a document.
        *   `GET /documents/{id}/preview`: Get a text preview or OCRed text.
        *   `POST /query`: Submit a natural language query (handled by Agentic Layer). Returns search results.
        *   `GET /config`: Retrieve current system configuration (AI providers, paths, privacy settings).
        *   `PUT /config`: Update system configuration.
        *   `GET /status`: Get overall system status (AI availability, queue status).
    *   **Authentication:** API keys or JWT for secure access.

*   **WebSocket API:**
    *   **Purpose:** Real-time notifications, streaming status updates, interactive agent communication.
    *   **Events (Examples):**
        *   `system.status_update`: Broadcasts overall system health (e.g., "LLM Available", "LLM Unavailable", "Processing X documents").
        *   `document.indexed`: Notifies when a new document is successfully processed.
        *   `document.progress`: Updates on the processing status of a specific document.
        *   `ai.model_change`: Informs about changes in the active AI models or providers.
        *   `agent.response_stream`: Streams responses from agents during complex queries or organization tasks.
    *   **Use Cases:** Enables the UI to display real-time progress, status changes, and interactive AI feedback without constant polling.

---

## 5. Key Architectural Decisions

*   **Hybrid Memory Architecture (ADR-001):** A multi-layered approach (Ingestion, Intelligence, Storage, Agentic) for modularity and flexibility.
*   **Local-First Privacy Model (ADR-005):** Prioritizes user data privacy by defaulting to local processing and requiring explicit opt-in for cloud services. Sensitive paths are enforced to be local-only.
*   **AI Externalization (Constraint 1.1, 1.2):** All AI workloads (LLMs, Embeddings, OCR) are offloaded to external services (local Ollama or cloud APIs) via `litellm`, preventing direct ML framework dependencies within the application.
*   **Provider Agnosticism (Constraint 1.3):** `litellm` ensures seamless switching between AI providers, enhancing flexibility and resilience.
*   **Graceful Degradation (Constraint 2):** The system remains functional for core tasks (browsing, keyword search) even when AI services are unavailable. AI-dependent features are queued and retried.
*   **SQLite for Metadata (ADR-002):** Chosen for its embedded nature, zero configuration, ACID compliance, and FTS5 support, making it ideal for single-user/small-scale deployments.
*   **ChromaDB for Vector Storage (ADR-003):** Offers an embedded, persistent vector database suitable for local development and deployment, with `pgvector` as a scalable alternative.
*   **Python as Primary Language (ADR-004):** Leverages the extensive AI/ML ecosystem and async capabilities.
*   **SHA-256 Deduplication (ADR-006):** A standard, efficient, and collision-resistant method for identifying duplicate files.
*   **Persistent & Retryable Queue:** Essential for handling AI task failures, service interruptions, and ensuring progress despite LLM unavailability.

---

## 6. Bottlenecks and Mitigations

*   **Bottleneck: AI Processing Speed & Availability**
    *   **Description:** Local AI models (LLMs, OCR) can be slow on consumer hardware. Cloud APIs introduce network latency and cost. LLM downtime interrupts AI-dependent features.
    *   **Mitigations:**
        *   **Provider Agnosticism (`litellm`):** Users can switch to faster cloud providers when local performance is insufficient or for specific tasks.
        *   **Ollama on Dedicated Hardware:** Users are encouraged to run Ollama on a capable machine (e.g., gaming PC with GPU) on their local network.
        *   **Batch Processing:** Optimize embedding generation by processing documents in batches.
        *   **Graceful Degradation:** Ensure keyword search and document browsing remain functional even when AI services are down (Constraint 2).
        *   **Queue Persistence & Retries:** Tasks waiting for AI are persisted and retried with backoff when services become available (Constraint 2.2).

*   **Bottleneck: Consumer Hardware Limitations (NAS/Desktop)**
    *   **Description:** Limited CPU, RAM, and disk I/O on typical NAS devices or personal computers can impact indexing speed and the ability to run local AI models.
    *   **Mitigations:**
        *   **Externalize AI:** Users can offload heavy AI computations to a separate, more powerful machine.
        *   **Efficient Libraries:** Use optimized Python libraries for file operations and data processing.
        *   **Resource Management:** Monitor resource usage and potentially throttle background processing if system performance degrades.
        *   **SQLite & Embedded ChromaDB:** Minimize the need for separate database servers, reducing overall system load.

*   **Bottleneck: Large Document Volumes (50,000+ documents)**
    *   **Description:** Initial indexing, re-indexing, and querying can become slow with a very large corpus.
    *   **Mitigations:**
        *   **Efficient Deduplication:** SHA-256 hashing prevents redundant processing of identical files.
        *   **Optimized Indexing Pipeline:** Parallelize ingestion tasks where possible.
        *   **Separated Storage:** Using SQLite for metadata and ChromaDB for vectors allows for optimized querying of each data type.
        *   **FTS5 for Keyword Search:** Provides fast, full-text search capabilities independent of vector search.
        *   **Selective Re-indexing:** Allow users to trigger re-indexing only for specific models or file types if needed.

*   **Bottleneck: Initial Indexing Time**
    *   **Description:** The first-time indexing of a large archive can take a significant amount of time.
    *   **Mitigations:**
        *   **Background Processing:** All indexing tasks run in the background, allowing users to continue using the system.
        *   **Prioritization:** New uploads are prioritized over historical backfill.
        *   **User Control:** Allow users to pause or schedule intensive indexing tasks.
        *   **Clear Status Reporting:** Provide clear UI feedback on indexing progress and estimated time remaining.

---
