# Librarian

> Sovereign document intelligence for personal archives

## What is Librarian?

Librarian transforms unstructured personal archives (PDFs, scans, images) into a searchable, agentic database. Privacy-first by design: run fully air-gapped with local LLMs/OCR, or selectively boost accuracy with cloud APIs when needed.

## Core Features

- 📁 **Intelligent Ingestion** — Watch directories, auto-detect new files, deduplicate by hash
- 🔒 **Privacy Controls** — Local-first OCR (Tesseract/PaddleOCR) with optional cloud fallback
- 🔍 **Semantic Search** — Natural language queries across your entire document archive
- 🤖 **Agentic Organization** — Auto-tagging, smart filing suggestions, multi-document analysis

## Quick Start

```bash
# Clone and setup
git clone <repo-url>
cd librarian

# Configure watch directories
cp config/config.example.yaml config/config.yaml
# Edit config.yaml with your paths

# Run with Docker
docker-compose up -d

# Or run locally
pip install -r requirements.txt
python src/main.py
```

## Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Watcher   │────▶│  Ingestion  │────▶│  Intelligence│
│ (filesystem)│     │   Worker    │     │    Core     │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
                    ┌─────────────────────────────────────┐
                    │           STORAGE LAYER             │
                    │  SQLite (metadata) + ChromaDB       │
                    └─────────────────────────────────────┘
                                               │
                                               ▼
                    ┌─────────────────────────────────────┐
                    │          AGENTIC LAYER              │
                    │  Query • Classify • Organize        │
                    └─────────────────────────────────────┘
```

## Project Structure

```
librarian/
├── docs/               # Documentation & PRD
├── src/
│   ├── watcher/        # File system monitoring
│   ├── ingestion/      # Processing pipeline
│   ├── intelligence/   # OCR + embedding generation
│   ├── storage/        # Database & vector store
│   └── agents/         # Query & organization agents
├── config/             # Configuration files
├── tests/              # Test suite
└── docker/             # Docker/deployment files
```

## Status

🚧 **Early Development** — See [docs/PRD.md](docs/PRD.md) for full specification.

## License

TBD
