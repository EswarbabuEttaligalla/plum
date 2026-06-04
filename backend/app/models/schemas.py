from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class DecisionStatus(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    PARTIAL = "PARTIAL"


class ClaimItemCreate(BaseModel):
    category: Optional[str]
    description: Optional[str]
    amount: float

    model_config = ConfigDict(from_attributes=True)


class ClaimCreate(BaseModel):
    member_code: str
    treatment_date: date
    submission_date: Optional[date] = None
    hospital: Optional[str] = None
    cashless_request: Optional[bool] = False
    items: List[ClaimItemCreate]
    total_amount: Optional[float] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentUploadResponse(BaseModel):
    doc_code: str
    doc_type: str
    filename: Optional[str] = None
    upload_ts: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class ExtractedDocument(BaseModel):
    doc_code: str
    claim_id: int
    doc_type: str
    extracted_json: Dict[str, Any]
    field_confidences: Optional[Dict[str, float]] = None
    ocr_text: Optional[str] = None
    upload_ts: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class DecisionResponse(BaseModel):
    claim_id: str
    status: DecisionStatus
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    approved_amount: float = 0.0
    reasons: List[str] = []
    policy_rules_checked: List[str] = []
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ClaimItemResponse(BaseModel):
    id: int
    category: Optional[str]
    description: Optional[str]
    amount: float
    approved_amount: Optional[float] = None
    reason_code: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentResponse(BaseModel):
    id: int
    doc_code: str
    doc_type: str
    filename: Optional[str]
    upload_ts: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ClaimResponse(BaseModel):
    id: int
    claim_code: str
    member_id: int
    treatment_date: date
    submission_date: Optional[date]
    hospital: Optional[str]
    cashless_request: bool
    total_amount: float
    status: str
    approved_amount: Optional[float]
    confidence: Optional[float]
    decision_json: Optional[Dict[str, Any]]
    items: List[ClaimItemResponse] = []
    documents: List[DocumentResponse] = []
    created_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class ClaimListResponse(BaseModel):
    claims: List[ClaimResponse]

    model_config = ConfigDict(from_attributes=True)


class PolicyLoadRequest(BaseModel):
    policy_code: str
    policy_json: Dict[str, Any]

    model_config = ConfigDict(from_attributes=True)
