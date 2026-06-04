from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class RuleResult:
    status: str
    reason_codes: List[str]
    reasons: List[str]
    confidence_score: float
    approved_amount: float
    deductions: Dict[str, float] = None
    cashless_approved: bool = False
    rejected_items: List[str] = None
    item_approvals: List[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class PolicyLoader:
    """Load and provide accessors for policy_terms.json and adjudication_rules.md

    Assumes files live in the repository root next to this package. Keeps parsing lightweight
    and exposes policy parts used by the rule engine.
    """

    def __init__(self, policy_path: Optional[str] = None, rules_path: Optional[str] = None):
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
        self.policy_path = policy_path or os.path.join(base, "policy_terms.json")
        self.rules_path = rules_path or os.path.join(base, "adjudication_rules.md")
        self.policy = self._load_policy()
        self.raw_rules = self._load_rules_markdown()

    def _load_policy(self) -> Dict[str, Any]:
        if not os.path.exists(self.policy_path):
            raise FileNotFoundError(f"policy file not found: {self.policy_path}")
        with open(self.policy_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _load_rules_markdown(self) -> str:
        if not os.path.exists(self.rules_path):
            return ""
        with open(self.rules_path, "r", encoding="utf-8") as f:
            return f.read()

    # Simple accessors
    def get_annual_limit(self) -> float:
        return float(self.policy.get("coverage_details", {}).get("annual_limit", 0))

    def get_per_claim_limit(self) -> float:
        return float(self.policy.get("coverage_details", {}).get("per_claim_limit", 0))

    def get_sub_limits(self) -> Dict[str, float]:
        details = self.policy.get("coverage_details", {})
        sub_limits = {}
        for k, v in details.items():
            if isinstance(v, dict) and "sub_limit" in v:
                sub_limits[k] = float(v.get("sub_limit", 0))
        return sub_limits

    def get_exclusions(self) -> List[str]:
        return self.policy.get("exclusions", [])

    def get_waiting_periods(self) -> Dict[str, Any]:
        return self.policy.get("waiting_periods", {})

    def get_covered_categories(self) -> List[str]:
        # categories correspond to keys in coverage_details
        return list(self.policy.get("coverage_details", {}).keys())

    def requires_pre_auth(self, test_name: str) -> bool:
        diag = self.policy.get("coverage_details", {}).get("diagnostic_tests", {})
        covered_tests = diag.get("covered_tests", [])
        # if test is listed with '(with pre-auth)' mark, treat accordingly
        for t in covered_tests:
            if isinstance(t, str) and test_name.lower() in t.lower():
                return "pre-auth" in t.lower() or "pre auth" in t.lower() or "with pre-auth" in t.lower()
        # fallback: MRI/CT require pre-auth per policy mention
        if "mri" in test_name.lower() or "ct" in test_name.lower():
            return True
        return False


class RuleEngine:
    """Evaluates claims against dynamic policy and rules.

    Methods accept simple python dicts for claims and extracted documents. This module
    does not call external services; it focuses on deterministic/heuristic rule checks.
    """

    DOCTOR_REG_REGEX = re.compile(r"^[A-Z]{2}/\d{3,6}/\d{4}$")

    def __init__(self, policy_loader: Optional[PolicyLoader] = None):
        self.loader = policy_loader or PolicyLoader()

    def evaluate(self, claim: Dict[str, Any], extracted_documents: List[Dict[str, Any]], usage_ytd: float = 0.0) -> RuleResult:
        """Run full evaluation pipeline and return RuleResult.

        claim: dict with keys like member_code, treatment_date, submission_date, total_amount, hospital
        extracted_documents: list of dicts with extracted_json and field_confidences
        usage_ytd: YTD used amount for member
        """
        reason_codes: List[str] = []
        reasons: List[str] = []
        confidence_modifiers: List[float] = []

        # Eligibility
        elig_ok, elig_reasons, elig_codes, elig_conf = self.evaluate_eligibility(claim, extracted_documents)
        reason_codes.extend(elig_codes)
        reasons.extend(elig_reasons)
        confidence_modifiers.append(elig_conf)

        # Document validation
        docs_ok, docs_reasons, docs_codes, docs_conf = self.evaluate_documents(claim, extracted_documents)
        reason_codes.extend(docs_codes)
        reasons.extend(docs_reasons)
        confidence_modifiers.append(docs_conf)

        # Normalize common bill keys into `line_items` so evaluate_coverage can consume them
        for d in extracted_documents:
            ej = d.get("extracted_json") or {}
            line_items = ej.get("line_items") or []
            # map common numeric fields into line_items
            if ej.get("consultation_fee") is not None:
                try:
                    line_items.append({"description": "consultation_fee", "amount": float(ej.get("consultation_fee")), "category": "consultation"})
                except Exception:
                    pass
            if ej.get("consultation") is not None:
                try:
                    line_items.append({"description": "consultation", "amount": float(ej.get("consultation")), "category": "consultation"})
                except Exception:
                    pass
            if ej.get("medicines") is not None:
                try:
                    if isinstance(ej.get("medicines"), dict):
                        # sum numeric values
                        total = 0.0
                        for v in ej.get("medicines", {}).values():
                            try:
                                total += float(v)
                            except Exception:
                                continue
                        if total > 0:
                            line_items.append({"description": "medicines", "amount": total, "category": "pharmacy"})
                    else:
                        line_items.append({"description": "medicines", "amount": float(ej.get("medicines")), "category": "pharmacy"})
                except Exception:
                    pass
            for diag_key in ("mri_scan", "xray", "ct_scan", "ultrasound", "ecg", "mri", "ct"):
                if ej.get(diag_key) is not None:
                    try:
                        line_items.append({"description": diag_key, "amount": float(ej.get(diag_key)), "category": "diagnostic_tests"})
                    except Exception:
                        pass
            if line_items:
                ej["line_items"] = line_items
                d["extracted_json"] = ej

        # Coverage
        cov_ok, cov_reasons, cov_codes, cov_conf, item_approvals = self.evaluate_coverage(claim, extracted_documents)
        reason_codes.extend(cov_codes)
        reasons.extend(cov_reasons)
        confidence_modifiers.append(cov_conf)

        # Limits
        lim_ok, lim_reasons, lim_codes, lim_conf = self.evaluate_limits(claim, item_approvals, usage_ytd)
        reason_codes.extend(lim_codes)
        reasons.extend(lim_reasons)
        confidence_modifiers.append(lim_conf)

        # Medical necessity
        med_ok, med_reasons, med_codes, med_conf = self.evaluate_medical_necessity(claim, extracted_documents)
        reason_codes.extend(med_codes)
        reasons.extend(med_reasons)
        confidence_modifiers.append(med_conf)

        # Fraud
        fraud_ok, fraud_reasons, fraud_codes, fraud_conf = self.evaluate_fraud_flags(claim, extracted_documents)
        reason_codes.extend(fraud_codes)
        reasons.extend(fraud_reasons)
        confidence_modifiers.append(fraud_conf)

        # Aggregate confidence
        base_conf = float(sum(confidence_modifiers) / max(1, len(confidence_modifiers)))

        total_amount = float(claim.get("total_amount", 0.0))

        # Determine final status
        # If any hard rejection codes present -> REJECTED
        hard_rejection_codes = {
            "POLICY_INACTIVE",
            "WAITING_PERIOD",
            "MEMBER_NOT_COVERED",
            "MISSING_DOCUMENTS",
            "INVALID_PRESCRIPTION",
            "SERVICE_NOT_COVERED",
            "EXCLUDED_CONDITION",
            "PRE_AUTH_MISSING",
            "ANNUAL_LIMIT_EXCEEDED",
            "PER_CLAIM_EXCEEDED",
            "NOT_MEDICALLY_NECESSARY",
        }

        if any(code in hard_rejection_codes for code in reason_codes):
            status = "REJECTED"
        else:
            # If partial approvals exist (some items rejected) -> PARTIAL treated as APPROVED with adjustments
            # Manual review conditions
            manual_conditions = []
            if base_conf < 0.70:
                manual_conditions.append("LOW_CONFIDENCE")
            if total_amount > 25000:
                manual_conditions.append("HIGH_VALUE")
            if any(code.startswith("FRAUD_") or code == "DUPLICATE_CLAIM" for code in reason_codes):
                manual_conditions.append("FRAUD_FLAGS")

            if manual_conditions:
                status = "MANUAL_REVIEW"
                # add a reason code for manual review
                reason_codes.append("MANUAL_REVIEW_TRIGGER")
                reasons.append(f"Manual review triggers: {manual_conditions}")
            else:
                status = "APPROVED"


        # compute approved_amount from item_approvals (items that passed coverage & limits)
        approved_amount = sum(item.get("approved_amount", item.get("amount", 0.0)) for item in item_approvals)

        # apply copay for consultation if present
        policy = self.loader.policy
        try:
            consultation_cfg = policy.get("coverage_details", {}).get("consultation_fees", {})
            copay_pct = float(consultation_cfg.get("copay_percentage", 0))
        except Exception:
            copay_pct = 0.0

        # if hospital in network, apply network discount if configured
        network_discount_amt = 0.0
        try:
            if claim.get("hospital") and claim.get("hospital") in policy.get("network_hospitals", []):
                network_discount_pct = float(consultation_cfg.get("network_discount", 0))
                network_discount_amt = approved_amount * (network_discount_pct / 100.0)
        except Exception:
            network_discount_amt = 0.0

        copay_amt = 0.0
        if copay_pct > 0:
            # apply copay only to consultation portion if present in approvals
            consult_sum = sum(i.get("approved_amount", i.get("amount", 0.0)) for i in item_approvals if i.get("category") == "consultation" or (i.get("category") is None and "consult" in (i.get("description") or "").lower()))
            copay_amt = consult_sum * (copay_pct / 100.0)

        # final approved after deductions
        final_approved = max(0.0, approved_amount - copay_amt - network_discount_amt)

        # compute rejected_items list
        rejected_items = [i.get("description") or "" for i in item_approvals if float(i.get("approved_amount", 0.0)) <= 0]

        # cashless approval logic: instant approval if cashless_request true and hospital is network and approved amount <= instant_approval_limit
        cashless_approved = False
        try:
            if claim.get("cashless_request") and claim.get("hospital") and claim.get("hospital") in policy.get("network_hospitals", []):
                instant_limit = float(policy.get("cashless_facilities", {}).get("instant_approval_limit", 0))
                if final_approved <= instant_limit:
                    cashless_approved = True
        except Exception:
            cashless_approved = False

        deductions = {"copay": round(float(copay_amt), 2), "network_discount": round(float(network_discount_amt), 2)}

        # assemble unique reason codes & reasons
        unique_codes = list(dict.fromkeys(reason_codes))
        unique_reasons = list(dict.fromkeys(reasons))

        result = RuleResult(
            status=status,
            reason_codes=unique_codes,
            reasons=unique_reasons,
            confidence_score=round(float(base_conf), 3),
            approved_amount=round(float(final_approved), 2),
            deductions=deductions,
            cashless_approved=cashless_approved,
            rejected_items=rejected_items,
            item_approvals=item_approvals,
        )

        return result
        # aggregate items and diagnosis from extracted docs
        items: List[Dict[str, Any]] = []
        diagnosis = claim.get("diagnosis_text") or ""
        for d in extracted_documents:
            ej = d.get("extracted_json") or {}
            # line items may be directly present or in claim payload
            if ej.get("line_items"):
                items.extend(ej.get("line_items"))
            # also handle common bill structures (consultation_fee, medicines, test names)
            # convert known numeric fields to line items for rule checks
            for key in ("consultation_fee", "consultation", "consultation_fees", "consult_fee"):
                if ej.get(key) is not None:
                    try:
                        amt = float(ej.get(key))
                        items.append({"description": key, "amount": amt, "category": "consultation"})
                    except Exception:
                        pass
            # medicines may be nested
            if ej.get("medicines") is not None:
                try:
                    amt = float(ej.get("medicines"))
                    items.append({"description": "medicines", "amount": amt, "category": "pharmacy"})
                except Exception:
                    # if medicines is dict with totals
                    if isinstance(ej.get("medicines"), dict):
                        total = sum(float(v) for v in ej.get("medicines").values() if isinstance(v, (int, float, str)) and str(v).replace('.', '', 1).isdigit())
                        if total:
                            items.append({"description": "medicines", "amount": total, "category": "pharmacy"})

            # handle diagnostic keys like mri_scan, xray etc.
            for diag_key in ("mri_scan", "xray", "ct_scan", "ultrasound", "ecg", "diagnostic_tests"):
                if ej.get(diag_key) is not None:
                    try:
                        amt = float(ej.get(diag_key))
                        items.append({"description": diag_key, "amount": amt, "category": "diagnostic_tests"})
                    except Exception:
                        pass

            if not diagnosis and ej.get("diagnosis"):
                diagnosis = ej.get("diagnosis")

    def evaluate_eligibility(self, claim: Dict[str, Any], extracted_documents: Optional[List[Dict[str, Any]]] = None) -> Tuple[bool, List[str], List[str], float]:
        codes: List[str] = []
        reasons: List[str] = []
        conf = 1.0

        policy = self.loader.policy
        # check policy effective date vs treatment date
        treatment_date = self._parse_date(claim.get("treatment_date"))
        effective = policy.get("effective_date")
        if effective:
            try:
                eff_date = self._parse_date(effective)
                if treatment_date and eff_date and treatment_date < eff_date:
                    codes.append("POLICY_INACTIVE")
                    reasons.append("Policy not effective on treatment date")
                    conf = 1.0
                    return False, reasons, codes, conf
            except Exception:
                pass

        # waiting periods
        waiting = self.loader.get_waiting_periods()
        # if specific ailments waiting applies, need member data in claim
        member_join_date = self._parse_date(claim.get("member_join_date"))
        docs_for_diag = extracted_documents if extracted_documents is not None else claim.get("extracted_documents", [])
        diagnosis = self._extract_diagnosis_from_docs(docs_for_diag)
        if diagnosis:
            for ailment, days in waiting.get("specific_ailments", {}).items():
                if ailment.lower() in diagnosis.lower():
                    if member_join_date and treatment_date and (treatment_date - member_join_date).days < int(days):
                        codes.append("WAITING_PERIOD")
                        reasons.append(f"{ailment} has waiting period of {days} days")
                        conf = 0.95
                        return False, reasons, codes, conf

        # minimum initial waiting
        initial_wait = int(waiting.get("initial_waiting", 0))
        if initial_wait and member_join_date and treatment_date and (treatment_date - member_join_date).days < initial_wait:
            codes.append("WAITING_PERIOD")
            reasons.append(f"Initial waiting period of {initial_wait} days not satisfied")
            conf = 0.95
            return False, reasons, codes, conf

        # member coverage - assume claim contains a member_covered boolean or member_code present
        if not claim.get("member_code"):
            codes.append("MEMBER_NOT_COVERED")
            reasons.append("Member information missing or not covered")
            conf = 1.0
            return False, reasons, codes, conf

        return True, reasons, codes, conf

    def evaluate_documents(self, claim: Dict[str, Any], extracted_documents: List[Dict[str, Any]]) -> Tuple[bool, List[str], List[str], float]:
        codes: List[str] = []
        reasons: List[str] = []
        confidences: List[float] = []

        required = self.loader.policy.get("claim_requirements", {}).get("documents_required", [])

        present_types = [d.get("doc_type") for d in extracted_documents]
        # check presence
        for req in required:
            # map human-readable requirement to doc_type keyword
            if "prescription" in req.lower() and "prescription" not in present_types:
                codes.append("MISSING_DOCUMENTS")
                reasons.append("Prescription missing")
            if "original bills" in req.lower() and not any(t for t in present_types if "bill" in t.lower() or "invoice" in t.lower()):
                codes.append("MISSING_DOCUMENTS")
                reasons.append("Original bill or receipt missing")

        # basic legibility check: require field_confidences average > threshold
        for doc in extracted_documents:
            confs = doc.get("field_confidences") or {}
            if confs:
                avg = sum(confs.values()) / max(1, len(confs))
                confidences.append(avg)
                if avg < 0.5:
                    codes.append("ILLEGIBLE_DOCUMENTS")
                    reasons.append(f"Document {doc.get('doc_code')} appears low-quality")
            else:
                # No confidences available; assume medium confidence
                confidences.append(0.7)

            # check doctor reg format presence for prescriptions
            if doc.get("doc_type") and "prescription" in doc.get("doc_type"):
                extracted = doc.get("extracted_json") or {}
                reg = extracted.get("doctor_reg") or extracted.get("doctor_registration")
                if not reg or not self.DOCTOR_REG_REGEX.match(str(reg)):
                    codes.append("DOCTOR_REG_INVALID")
                    reasons.append("Doctor registration number missing or invalid")

        avg_conf = float(sum(confidences) / max(1, len(confidences))) if confidences else 0.0

        ok = not any(c in ("MISSING_DOCUMENTS", "ILLEGIBLE_DOCUMENTS") for c in codes)
        return ok, reasons, codes, avg_conf

    def evaluate_coverage(self, claim: Dict[str, Any], extracted_documents: List[Dict[str, Any]]) -> Tuple[bool, List[str], List[str], float, List[Dict[str, Any]]]:
        """Check each claim item against policy coverage; return item_approvals list with approved_amounts assigned."""
        policy = self.loader.policy
        coverage = policy.get("coverage_details", {})
        exclusions = set(self.loader.get_exclusions())

        reason_codes: List[str] = []
        reasons: List[str] = []
        confs: List[float] = []

        # Quick diagnosis-based exclusion mapping (e.g., obesity -> weight loss treatments exclusion)
        diagnosis = claim.get("diagnosis_text") or self._extract_diagnosis_from_docs(extracted_documents) or ""
        if diagnosis:
            for excl in exclusions:
                if "weight" in excl.lower() or "weight loss" in excl.lower():
                    if any(x in diagnosis.lower() for x in ("obes", "weight", "bariatric", "bmi")):
                        reason_codes.append("EXCLUDED_CONDITION")
                        reasons.append(f"Condition excluded by policy (mapped): {excl} matches diagnosis {diagnosis}")
                        return False, reasons, reason_codes, 0.9, []

        # Gather items from claim or extracted documents
        items: List[Dict[str, Any]] = claim.get("items") or []

        # If no explicit items, try to extract line items from documents
        if not items:
            for doc in extracted_documents:
                ex = doc.get("extracted_json") or {}
                if ex.get("line_items"):
                    items.extend(ex.get("line_items", []))

        item_approvals: List[Dict[str, Any]] = []

        for it in items:
            desc = (it.get("description") or "").lower()
            category = it.get("category")
            amount = float(it.get("amount", 0.0))
            approved = 0.0
            item_reasons: List[str] = []
            item_codes: List[str] = []

            # Determine category if missing by keyword matching
            if not category:
                if any(k in desc for k in ("consult", "doctor", "visit")):
                    category = "consultation_fees"
                elif any(k in desc for k in ("blood", "x-ray", "mri", "ct", "ecg", "ultrasound")):
                    category = "diagnostic_tests"
                elif any(k in desc for k in ("pharm", "drug", "tablet", "syrup", "med")):
                    category = "pharmacy"
                elif any(k in desc for k in ("tooth", "root", "whiten", "dental")):
                    category = "dental"
                elif any(k in desc for k in ("vision", "glass", "lasik")):
                    category = "vision"
                else:
                    category = "other"

            # Check exclusion keywords
            if any(excl.lower() in desc for excl in exclusions):
                item_reasons.append("Item falls under policy exclusions")
                item_codes.append("EXCLUDED_CONDITION")
                approved = 0.0
            else:
                # Pre-authorization check for diagnostic tests (e.g., MRI/CT)
                try:
                    if category == "diagnostic_tests" or any(k in desc for k in ("mri", "ct", "scan")):
                        # if policy requires pre-auth for this test and claim did not provide it -> reject
                        if self.loader.requires_pre_auth(desc) and not claim.get("pre_auth_obtained", False):
                            item_reasons.append("Pre-authorization required but missing")
                            item_codes.append("PRE_AUTH_MISSING")
                            approved = 0.0
                            # mark as hard rejection immediately
                            reason_codes.append("PRE_AUTH_MISSING")
                            reasons.append(f"Pre-authorization missing for {desc}")
                            # return early since pre-auth missing is a hard stop for diagnostics
                            return False, reasons, reason_codes, 0.95, []
                except Exception:
                    pass
                # Check if category covered
                if category in coverage and coverage.get(category, {}).get("covered", False):
                    # Apply sub-limit if exists
                    sub_limit = coverage.get(category, {}).get("sub_limit")
                    if sub_limit is not None:
                        sub_limit = float(sub_limit)
                        approved = min(amount, sub_limit)
                        if amount > sub_limit:
                            item_reasons.append(f"Sub-limit exceeded for {category}")
                            item_codes.append("SUB_LIMIT_EXCEEDED")
                    else:
                        approved = amount
                else:
                    # if not present explicitly, try to map by common coverage keys
                    if category in coverage:
                        if not coverage.get(category, {}).get("covered", False):
                            item_reasons.append(f"Category {category} not covered")
                            item_codes.append("SERVICE_NOT_COVERED")
                            approved = 0.0
                        else:
                            approved = amount
                    else:
                        # unknown category -> treat as not covered
                        item_reasons.append(f"Unknown or uncategorized item: {category}")
                        item_codes.append("SERVICE_NOT_COVERED")
                        approved = 0.0

            item_approvals.append({
                "category": category,
                "description": it.get("description"),
                "amount": amount,
                "approved_amount": round(approved, 2),
                "reason_codes": item_codes,
                "reasons": item_reasons,
            })

        # coverage ok if at least one item approved
        cov_ok = any(i.get("approved_amount", 0.0) > 0 for i in item_approvals)
        return cov_ok, reasons, reason_codes, 0.9, item_approvals

    def evaluate_limits(self, claim: Dict[str, Any], item_approvals: List[Dict[str, Any]], usage_ytd: float) -> Tuple[bool, List[str], List[str], float]:
        codes: List[str] = []
        reasons: List[str] = []
        conf = 0.9

        policy = self.loader.policy
        annual_limit = float(policy.get("coverage_details", {}).get("annual_limit", 0))
        per_claim = float(policy.get("coverage_details", {}).get("per_claim_limit", 0))

        approved_total = sum(i.get("approved_amount", 0.0) for i in item_approvals)

        # per-claim limit
        if per_claim and approved_total > per_claim:
            codes.append("PER_CLAIM_EXCEEDED")
            reasons.append(f"Approved amount {approved_total} exceeds per-claim limit of {per_claim}")

        # annual limit
        remaining = max(0.0, annual_limit - float(usage_ytd))
        if annual_limit and approved_total > remaining:
            codes.append("ANNUAL_LIMIT_EXCEEDED")
            reasons.append(f"Annual limit exceeded. Remaining {remaining}")

        # Sub-limits already applied per item; detect if any item had SUB_LIMIT_EXCEEDED in reason_codes
        for i in item_approvals:
            if i.get("reason_codes") and "SUB_LIMIT_EXCEEDED" in i.get("reason_codes"):
                codes.append("SUB_LIMIT_EXCEEDED")
                reasons.append("One or more category sub-limits exceeded")

        ok = not any(c in ("PER_CLAIM_EXCEEDED", "ANNUAL_LIMIT_EXCEEDED", "SUB_LIMIT_EXCEEDED") for c in codes)
        return ok, reasons, codes, conf

    def evaluate_medical_necessity(self, claim: Dict[str, Any], extracted_documents: List[Dict[str, Any]]) -> Tuple[bool, List[str], List[str], float]:
        codes: List[str] = []
        reasons: List[str] = []
        conf = 0.85

        # rudimentary check: presence of diagnosis and matching line items
        diagnosis = self._extract_diagnosis_from_docs(extracted_documents)
        if not diagnosis:
            codes.append("NOT_MEDICALLY_NECESSARY")
            reasons.append("No diagnosis found to justify treatment")
            conf = 0.4
            return False, reasons, codes, conf

        # if diagnosis present, consider medically necessary for MVP
        return True, reasons, codes, conf

    def evaluate_fraud_flags(self, claim: Dict[str, Any], extracted_documents: List[Dict[str, Any]]) -> Tuple[bool, List[str], List[str], float]:
        codes: List[str] = []
        reasons: List[str] = []
        conf = 1.0

        # Example heuristics: multiple claims same day, provider not in network but suspicious registration, duplicate bills
        prev_same_day = int(claim.get("previous_claims_same_day", 0))
        if prev_same_day and prev_same_day >= 2:
            codes.append("DUPLICATE_CLAIM")
            reasons.append("Multiple claims from same member on the same day")
            conf = 0.6

        # provider validity check
        for doc in extracted_documents:
            ex = doc.get("extracted_json") or {}
            reg = ex.get("doctor_reg") or ex.get("doctor_registration")
            if reg and not self.DOCTOR_REG_REGEX.match(str(reg)):
                codes.append("DOCTOR_REG_INVALID")
                reasons.append("Doctor registration appears invalid")
                conf = 0.5

        ok = not any(c in ("DUPLICATE_CLAIM",) for c in codes)
        return ok, reasons, codes, conf

    # --- helpers ---
    def _parse_date(self, value: Any) -> Optional[date]:
        if not value:
            return None
        if isinstance(value, date):
            return value
        try:
            # try common formats
            return datetime.fromisoformat(str(value)).date()
        except Exception:
            for fmt in ("%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d"):
                try:
                    return datetime.strptime(str(value), fmt).date()
                except Exception:
                    continue
        return None

    def _extract_diagnosis_from_docs(self, docs: List[Dict[str, Any]]) -> Optional[str]:
        for d in docs:
            ex = d.get("extracted_json") or {}
            diag = ex.get("diagnosis") or ex.get("diagnosis_text")
            if diag:
                return str(diag)
        return None
