
Demo Script — Plum OPD Claim Adjudication (5–7 minutes)

Purpose: A concise walkthrough that demonstrates the full upload → process → decision workflow, highlights fallback behavior (no OpenAI key), and shows approved vs rejected outcomes.

Pre-demo checklist:
- Backend running: `uvicorn app.main:app --reload --port 8000`
- Frontend running: `cd frontend && npm run dev`
- Sample files available in `scripts/` (e.g., `smoke_bill.txt`, `smoke_prescription.txt`)

Step 1 — Intro (20s)
- One-sentence problem statement: "This demo shows automated adjudication of OPD claims using OCR + optional LLM extraction and a rules engine."

Step 2 — Create a Claim (40s)
- Open `http://localhost:3000/upload`.
- Fill: `member_code` = `DEMO_EMP_001_<timestamp>` (use timestamp to avoid DB uniqueness conflicts). Enter `treatment_date` and `total_amount`.
- Attach `smoke_bill.txt` and `smoke_prescription.txt` and submit.

Step 3 — Trigger Processing (30s)
- Either click the UI Process button or invoke the endpoint:

```bash
# Replace claim id (e.g., 6) from create response
curl -X POST http://127.0.0.1:8000/api/claims/6/process
```

- Explain: Backend runs OCR/text read, attempts GPT extraction; if unavailable it runs a line-based fallback parser.

Step 4 — Show Results (40s)
- Open `http://localhost:3000/claims` and locate the claim (or call `GET /api/claims/6`).
- Open claim details and point out: `status`, `approved_amount`, `confidence_score`, `reasons` and `policy_rules_checked`.

Step 5 — Demonstrate Approved & Rejected Cases (60s)
- Run `scripts/verify_endpoints.py` which programmatically creates claims for different scenarios. Show console output for an APPROVED and a REJECTED run.

Step 6 — Wrap-up and Next Steps (30s)
- Highlight documentation in `README.md`, `architecture.md`, `decision_flowchart.md`, and `assumptions.md`.
- Mention deployment steps and artifacts in `artifacts/`.

Notes for the presenter:
- Use unique `member_code` to avoid unique constraint failures.
- If OpenAI key is not set, extraction fallback will produce deterministic but simpler results — call this out as intentional for reproducible tests.

