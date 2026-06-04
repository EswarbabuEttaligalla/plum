from __future__ import annotations

import re

from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, Form
from fastapi import status as http_status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import db_models
from app.models import schemas
from app.services.decision_service import DecisionService

router = APIRouter(prefix="/claims", tags=["claims"])

decision_service = DecisionService()


def classify_document_type(ocr_text: str, current_doc_type: str = "prescription") -> str:
    text = (ocr_text or "").lower()

    bill_signals = ["invoice", "bill no", "gst no", "total amount"]
    prescription_signals = ["diagnosis", "prescription", "reg. no", "registration no", "doctor"]
    report_signals = ["report", "findings", "impression", "advice", "investigation"]

    bill_score = sum(1 for signal in bill_signals if signal in text)
    prescription_score = sum(1 for signal in prescription_signals if signal in text)
    report_score = sum(1 for signal in report_signals if signal in text)

    if bill_score >= 3:
        return "bill"
    if prescription_score >= 3:
        return "prescription"
    if report_score >= 2:
        return "report"
    return current_doc_type or "prescription"


@router.post("/", response_model=schemas.ClaimResponse)
def create_claim(payload: schemas.ClaimCreate, db: Session = Depends(get_db)):
    # create member if not exists (simple behaviour for MVP)
    member = db.query(db_models.Member).filter_by(member_code=payload.member_code).first()
    if not member:
        member = db_models.Member(member_code=payload.member_code, name=payload.member_code)
        db.add(member)
        db.commit()
        db.refresh(member)

    claim = db_models.Claim(
        claim_code="CLM_" + payload.member_code + "_" + payload.treatment_date.isoformat(),
        member_id=member.id,
        treatment_date=payload.treatment_date,
        submission_date=payload.submission_date,
        hospital=payload.hospital,
        cashless_request=payload.cashless_request or False,
        total_amount=payload.total_amount or sum(i.amount for i in payload.items),
        status="PENDING",
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    # add items
    for it in payload.items:
        ci = db_models.ClaimItem(claim_id=claim.id, category=it.category, description=it.description, amount=it.amount)
        db.add(ci)
    db.commit()

    db.refresh(claim)
    return claim


@router.get("/", response_model=schemas.ClaimListResponse)
def list_claims(db: Session = Depends(get_db)):
    claims = db.query(db_models.Claim).order_by(db_models.Claim.created_at.desc()).all()
    return schemas.ClaimListResponse(claims=claims)


@router.post("/{claim_id}/upload", response_model=schemas.DocumentUploadResponse)
async def upload_document(claim_id: int, file: UploadFile = File(...), doc_type: str = Form("prescription"), db: Session = Depends(get_db)):
    claim = db.query(db_models.Claim).filter_by(id=claim_id).first()
    if not claim:
        raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="Claim not found")

    contents = await file.read()
    # store file to disk for MVP
    save_dir = "./data/uploads"
    import os

    os.makedirs(save_dir, exist_ok=True)
    path = os.path.join(save_dir, file.filename)
    with open(path, "wb") as fh:
        fh.write(contents)

    # If the uploaded file is an image or PDF, attempt OCR and store text
    ocr_text_val = None
    try:
        _, ext = os.path.splitext(file.filename or "")
        ext = (ext or "").lower()
        image_exts = {".jpg", ".jpeg", ".png", ".pdf"}
        if ext in image_exts:
            from app.services.ocr_service import OCRService

            ocr = OCRService()
            try:
                ocr_text_val = ocr.extract_text_from_bytes(contents)
            except Exception:
                # best-effort OCR; leave ocr_text as None on failure
                ocr_text_val = None
    except Exception:
        # best-effort; don't block upload on unexpected OCR errors
        ocr_text_val = None
    doc_type = classify_document_type(ocr_text_val or "", current_doc_type=doc_type)
    doc = db_models.Document(claim_id=claim.id, doc_type=doc_type, filename=file.filename, ocr_text=ocr_text_val)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    return schemas.DocumentUploadResponse(doc_code=doc.doc_code, doc_type=doc.doc_type, filename=doc.filename, upload_ts=doc.upload_ts)


@router.post("/{claim_id}/process")
async def process_claim(claim_id: int, db: Session = Depends(get_db)):
    claim = db.query(db_models.Claim).filter_by(id=claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    # gather uploaded documents and their OCR text (for MVP assume raw file text saved in ocr_text)
    docs = db.query(db_models.Document).filter_by(claim_id=claim.id).all()
    ocr_texts = []
    for d in docs:
        classified_doc_type = classify_document_type(d.ocr_text or "", current_doc_type=d.doc_type)
        if classified_doc_type != d.doc_type:
            d.doc_type = classified_doc_type
            db.add(d)
        if d.ocr_text:
            ocr_texts.append({"doc_type": classified_doc_type, "text": d.ocr_text})
        else:
            # fallback: read file if present in uploads
            try:
                with open(f"./data/uploads/{d.filename}", "r", encoding="utf-8") as fh:
                    txt = fh.read()
                classified_doc_type = classify_document_type(txt, current_doc_type=d.doc_type)
                if classified_doc_type != d.doc_type:
                    d.doc_type = classified_doc_type
                    db.add(d)
                ocr_texts.append({"doc_type": classified_doc_type, "text": txt})
            except Exception:
                ocr_texts.append({"doc_type": d.doc_type, "text": ""})

    db.commit()
    # build claim payload for decision service
    claim_payload = {
        "claim_code": claim.claim_code,
        "member_code": claim.member.member_code if getattr(claim, "member", None) else None,
        "treatment_date": claim.treatment_date.isoformat(),
        "total_amount": claim.total_amount,
    }

    decision = await decision_service.process_claim(claim_payload, ocr_texts, member_record={"join_date": None}, ytd_used=0.0)

    # persist decision
    claim.status = decision.get("status")
    claim.approved_amount = decision.get("approved_amount")
    claim.confidence = decision.get("confidence_score")
    claim.decision_json = decision
    db.add(claim)
    db.commit()

    return decision


@router.get("/{claim_id}", response_model=schemas.ClaimResponse)
def get_claim(claim_id: int, db: Session = Depends(get_db)):
    claim = db.query(db_models.Claim).filter_by(id=claim_id).first()
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    return claim
