from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.services.rule_engine import PolicyLoader, RuleEngine, RuleResult


class DecisionService:
    """Orchestrates extraction and rule evaluation to produce final decisions."""

    def __init__(self, gpt_extractor: Optional[Any] = None, rule_engine: Optional[RuleEngine] = None):
        self.pl = PolicyLoader()
        self.rule_engine = rule_engine or RuleEngine(self.pl)

    async def process_claim(self, claim: Dict[str, Any], ocr_texts: List[Dict[str, Any]], member_record: Optional[Dict[str, Any]] = None, ytd_used: float = 0.0) -> Dict[str, Any]:
        """Given claim payload and list of OCR texts (each: {doc_type, text}), run extraction and evaluation.

        Returns a decision dict suitable for persistence/return.
        """
        extracted_docs: List[Dict[str, Any]] = []
        for doc in ocr_texts:
            doc_type = doc.get("doc_type", "prescription")
            text = doc.get("text", "")
            extracted = self._fallback_extract_from_text(text, doc_type=doc_type)
            extracted_docs.append(extracted)

        # call rule engine
        result: RuleResult = self.rule_engine.evaluate(claim, extracted_docs, usage_ytd=ytd_used)

        return {
            "claim_id": claim.get("claim_code") or claim.get("id"),
            "decision": result.status,
            "status": result.status,
            "confidence_score": result.confidence_score,
            "approved_amount": result.approved_amount,
            "rejection_reasons": result.reason_codes,
            "reasons": result.reasons,
            "policy_rules_checked": result.reason_codes,
            "deductions": result.deductions or {},
            "cashless_approved": bool(getattr(result, "cashless_approved", False)),
            "rejected_items": result.rejected_items or [],
        }

    def _fallback_extract_from_text(self, ocr_text: str, doc_type: str = "prescription") -> Dict[str, Any]:
        extracted_json: Dict[str, Any] = {}
        field_confidences: Dict[str, float] = {}

        lines = [line.strip() for line in (ocr_text or "").splitlines() if line.strip()]
        normalized_text = "\n".join(lines)

        def extract_label_value(patterns: List[str]) -> Optional[str]:
            for pattern in patterns:
                match = re.search(pattern, normalized_text, flags=re.IGNORECASE | re.MULTILINE)
                if match:
                    value = match.group(1).strip(" .:-\t")
                    if value:
                        return value
            return None

        def extract_line_after_label(label_patterns: List[str]) -> Optional[str]:
            for index, line in enumerate(lines):
                for pattern in label_patterns:
                    if re.search(pattern, line, flags=re.IGNORECASE):
                        parts = re.split(r"\s*[:\-]\s*", line, maxsplit=1)
                        if len(parts) > 1 and parts[1].strip():
                            return parts[1].strip()
                        if index + 1 < len(lines):
                            next_line = lines[index + 1].strip()
                            if next_line:
                                return next_line
            return None

        diagnosis = extract_line_after_label([r"^diagnosis\b", r"^dx\b"])
        if diagnosis:
            extracted_json["diagnosis"] = diagnosis
            field_confidences["diagnosis"] = 0.95

        doctor_reg = extract_label_value([
            r"\b(?:reg\.?\s*no\.?|registration\s*no\.?)\s*[:\-]?\s*([^\n\r]+)",
        ])
        if doctor_reg:
            extracted_json["doctor_reg"] = doctor_reg
            extracted_json["doctor_registration"] = doctor_reg
            field_confidences["doctor_reg"] = 0.95
            field_confidences["doctor_registration"] = 0.95

        patient_name = extract_label_value([
            r"\bpatient\s*name\s*[:\-]?\s*([^\n\r]+)",
        ])
        if patient_name:
            extracted_json["patient_name"] = patient_name
            field_confidences["patient_name"] = 0.95

        line_items = []
        for line in lines:
            amount_match = re.search(r"(\d+[\d,]*\.?\d*)", line)
            if amount_match:
                amount_text = amount_match.group(1).replace(",", "")
                try:
                    amount = float(amount_text)
                except Exception:
                    continue
                line_items.append({"description": line[:80], "amount": amount})

        if line_items:
            extracted_json["line_items"] = line_items
            field_confidences["line_items"] = 0.7

        return {
            "doc_type": doc_type,
            "extracted_json": extracted_json,
            "field_confidences": field_confidences,
            "raw_text": ocr_text,
        }
