# Librarian - Project Status

**Last Updated:** 2026-02-15
**Phase:** Planning

## Current State

Project initialized with:
- ✅ PRD documented
- ✅ Architecture decisions recorded
- ✅ Example configuration created
- ✅ Project structure defined

## Next Steps

### M1: Project Skeleton + Watcher MVP
- [ ] Initialize Python project (pyproject.toml)
- [ ] Set up basic logging
- [ ] Implement file watcher using `watchdog`
- [ ] Test watching a directory for changes

### M2: Ingestion Pipeline
- [ ] Design file queue system
- [ ] Implement SHA-256 hashing
- [ ] Create SQLite schema for metadata
- [ ] Basic file metadata extraction

### M3: Local OCR
- [ ] Integrate Tesseract
- [ ] Test OCR on sample PDFs/images
- [ ] Store extracted text in database

## Blockers

None currently.

## Notes

- Target hardware: Synology NAS (16GB RAM) or equivalent
- Privacy-first: local processing by default
- Start simple, add cloud fallback later
