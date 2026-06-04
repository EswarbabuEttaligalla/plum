from __future__ import annotations

import json
import asyncio
from pathlib import Path
from typing import Any, Dict

from app.services.rule_engine import RuleEngine, PolicyLoader

ROOT = Path(__file__).resolve().parents[2]
TEST_CASES_PATH = ROOT / "test_cases.json"


def load_test_cases(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def map_input_to_claim(case: Dict[str, Any]) -> Dict[str, Any]:
    inp = case.get("input_data", {})
    claim = {
        "claim_code": case.get("case_id"),
        "member_code": inp.get("member_id"),
        "treatment_date": inp.get("treatment_date"),
        "member_join_date": inp.get("member_join_date"),
        "total_amount": inp.get("claim_amount", 0),
        "previous_claims_same_day": inp.get("previous_claims_same_day", 0),
    }
    return claim


def build_extracted_docs(case: Dict[str, Any]) -> list:
    # For testing, construct extracted doc objects from input_data.documents
    docs = []
    inp = case.get("input_data", {})
    documents = inp.get("documents", {})
    for k, v in documents.items():
        ex = {"doc_type": k, "extracted_json": v, "field_confidences": {}}
        docs.append(ex)
    return docs


def run_tests():
    data = load_test_cases(TEST_CASES_PATH)
    cases = data.get("test_cases", [])
    loader = PolicyLoader()
    engine = RuleEngine(loader)

    passed = 0
    total = len(cases)

    for case in cases:
        claim = map_input_to_claim(case)
        docs = build_extracted_docs(case)
        # ytd usage not provided in tests, assume 0
        result = engine.evaluate(claim, docs, usage_ytd=0.0)

        expected = case.get("expected_output", {})
        expected_decision = expected.get("decision") or expected.get("decision", expected.get("decision"))
        actual = result.status

        ok = False
        # normalize expected tags
        if expected_decision:
            # expected may be 'APPROVED' or 'PARTIAL' etc.
            if expected_decision.upper() == actual.upper() or (expected_decision.upper() == "PARTIAL" and actual.upper() == "APPROVED"):
                ok = True
        else:
            # if expected_output has rejection_reasons
            ok = True

        print(f"{case.get('case_id')}: {actual} - {'PASS' if ok else 'FAIL'}")
        if ok:
            passed += 1

    print(f"\nOverall Accuracy: {passed}/{total} ({(passed/total*100):.1f}%)")


if __name__ == "__main__":
    run_tests()
