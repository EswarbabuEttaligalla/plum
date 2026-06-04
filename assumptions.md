Assumptions Made in This Implementation

1. Member identification
- Claims must include a `member_code` (or `member_id`) in the payload. If missing, the claim is rejected with `MEMBER_NOT_COVERED`.

2. Extraction behavior
- LLM-based extraction (OpenAI) is optional. If the `OPENAI_API_KEY` is not provided or extraction fails, a deterministic fallback parser runs which extracts diagnosis lines and numeric amounts.

3. Doctor registration format
- Doctor registration numbers are validated against a simple regex `^[A-Z]{2}/\d{3,6}/\d{4}$`. Some valid registrations may not match and will be flagged as `DOCTOR_REG_INVALID`.

4. Document storage
- Uploaded files are stored locally under `./data/uploads` for development; production requires cloud storage (S3/GCS).

5. Database
- Uses SQLite for development. For production, migrate to PostgreSQL or equivalent and set `DATABASE_URL`.

6. Confidence & thresholds
- Per-component confidence values are averaged to a base confidence. Manual review is triggered if base confidence < 0.70.

7. Pre-authorization
- The policy loader can detect tests needing pre-authorization, but full pre-auth workflow is not implemented; the rule engine will flag `PRE_AUTH_MISSING` when detected in inputs (to be added to automated checks).

8. Time zones and dates
- Dates are parsed with ISO formats first; local formats supported. All date comparisons are done in date (no timezone) precision.

9. Fraud heuristics
- Simple heuristics are used (e.g., previous claims same day). A production system should use more robust analytics.

10. Claim items
- If structured `items` are not provided in the claim payload, the engine will try to build `line_items` from extracted document fields.
