Architecture Notes — Plum OPD Claim Adjudication

Overview:
- The system is intentionally simple and modular: a Next.js frontend for uploads and viewing, a FastAPI backend for orchestration, a small extraction layer (OCR + optional LLM), and a rules-based adjudication engine backed by SQLite.

Components:
- Frontend (Next.js): Upload UI, Claims list, Claim details.
- Backend (FastAPI): REST API, Document storage, Decision orchestration.
- OCR Service: `tesseract` wrapper; text files supported for smoke tests.
- Extractor: OpenAI Responses API wrapper with deterministic fallback parsing.
- Rule Engine: Encodes business rules from `adjudication_rules.md` and `policy_terms.json`.

Design decisions:
- Keep LLM optional: fallback deterministic extractor ensures reproducible tests.
- Store uploaded files on disk during development at `./data/uploads`.
- Use SQLite for simple persistence; recommend managed DB for production.

Data flow (short):
1. Files -> saved to disk -> OCR/text read -> extracted fields -> rule engine -> decision persisted -> UI reads decision.
