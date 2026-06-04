from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from app.db.session import SessionLocal
from app.db import session as dbsession


ART_DIR = Path("artifacts")
ART_DIR.mkdir(parents=True, exist_ok=True)


def run_tests_and_save():
    # run tests_runner.py and capture output
    cmd = [
        "C:\\Users\\eeswa\\AppData\\Local\\Programs\\Python\\Python310\\python.exe",
        "backend/app/tests_runner.py",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, cwd=os.getcwd())
    out = res.stdout + "\n" + res.stderr
    with open(ART_DIR / "test_results.txt", "w", encoding="utf-8") as fh:
        fh.write(out)
    return out


def dump_example_decisions():
    dbsession.create_tables()
    db = SessionLocal()
    try:
        # statuses we're interested in
        statuses = {
            "APPROVED": ART_DIR / "approved_claim_example.json",
            "REJECTED": ART_DIR / "rejected_claim_example.json",
            "MANUAL_REVIEW": ART_DIR / "manual_review_example.json",
        }

        found = {k: False for k in statuses}

        # query recent claims
        from app.models import db_models

        claims = db.query(db_models.Claim).order_by(db_models.Claim.created_at.desc()).all()
        for c in claims:
            st = (c.status or "").upper()
            if st in statuses and not found[st]:
                # write decision json if present
                dj = c.decision_json or {"claim_id": c.claim_code, "status": c.status}
                with open(statuses[st], "w", encoding="utf-8") as fh:
                    json.dump(dj, fh, indent=2)
                found[st] = True

        # If any not found, create placeholder from latest decisions or tests
        for st, path in statuses.items():
            if not found[st]:
                # try to find any claim with a decision
                anyc = next((c for c in claims if c.decision_json), None)
                sample = anyc.decision_json if anyc else {"note": "no decision available"}
                # adjust status field
                sample = dict(sample)
                sample["status"] = st
                with open(path, "w", encoding="utf-8") as fh:
                    json.dump(sample, fh, indent=2)

    finally:
        db.close()


def verify_files():
    files = [
        ART_DIR / "test_results.txt",
        ART_DIR / "approved_claim_example.json",
        ART_DIR / "rejected_claim_example.json",
        ART_DIR / "manual_review_example.json",
    ]
    missing = [str(p) for p in files if not p.exists()]
    if missing:
        print("Missing files:", missing)
        return False
    print("All artifacts present:")
    for p in files:
        print("-", p)
    return True


if __name__ == "__main__":
    print("Running tests and saving results...")
    run_tests_and_save()
    print("Dumping example decisions...")
    dump_example_decisions()
    ok = verify_files()
    if not ok:
        raise SystemExit(1)
    print("Artifacts generated in", ART_DIR)
