from __future__ import annotations

import os
from datetime import date

from app.db.session import SessionLocal
from app.models import db_models
from app.services.decision_service import DecisionService
from app.db import session as dbsession


def make_sample_image_bytes(text: str) -> bytes:
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io

        img = Image.new("RGB", (600, 200), color=(255, 255, 255))
        d = ImageDraw.Draw(img)
        try:
            f = ImageFont.load_default()
        except Exception:
            f = None
        d.text((10, 10), text, fill=(0, 0, 0), font=f)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        # Pillow not available; return bytes of text
        return text.encode("utf-8")


def main():
    # ensure DB/tables exist
    dbsession.create_tables()
    db = SessionLocal()
    # create member + claim
    member = db.query(db_models.Member).filter_by(member_code="DEMO_MEMBER").first()
    if not member:
        member = db_models.Member(member_code="DEMO_MEMBER", name="Demo Member")
        db.add(member)
        db.commit()
        db.refresh(member)

    claim = db_models.Claim(
        claim_code=f"CLM_DEMO{int(os.times()[4])}",
        member_id=member.id,
        treatment_date=date.today(),
        submission_date=date.today(),
        hospital="Demo Hospital",
        cashless_request=False,
        total_amount=1000.0,
        status="PENDING",
    )
    db.add(claim)
    db.commit()
    db.refresh(claim)

    # generate sample image bytes with embedded text
    sample_text = "Patient: John Doe\nDiagnosis: fever\nLineItem: Consultation - 1000"
    img_bytes = make_sample_image_bytes(sample_text)

    # save to uploads
    os.makedirs("./data/uploads", exist_ok=True)
    filename = f"demo_upload_{claim.id}.png"
    path = os.path.join("./data/uploads", filename)
    with open(path, "wb") as fh:
        fh.write(img_bytes)

    # attempt OCR
    ocr_text = None
    try:
        from app.services.ocr_service import OCRService

        ocr = OCRService()
        ocr_text = ocr.extract_text_from_bytes(img_bytes)
    except Exception as e:
        # fallback: if OCR fails, use the original sample_text so flow can proceed
        ocr_text = sample_text

    # create document record with ocr_text
    doc = db_models.Document(claim_id=claim.id, doc_type="prescription", filename=filename, ocr_text=ocr_text)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    print("Uploaded file:", path)
    print("OCR extracted text (first 200 chars):", (ocr_text or "").strip()[:200])

    # process claim using DecisionService
    decision_service = DecisionService()
    claim_payload = {
        "claim_code": claim.claim_code,
        "member_code": member.member_code,
        "treatment_date": claim.treatment_date.isoformat(),
        "total_amount": claim.total_amount,
    }
    ocr_texts = [{"doc_type": doc.doc_type, "text": doc.ocr_text}]

    import asyncio

    decision = asyncio.run(decision_service.process_claim(claim_payload, ocr_texts, member_record={"join_date": None}, ytd_used=0.0))

    # persist decision
    claim.status = decision.get("status")
    claim.approved_amount = decision.get("approved_amount")
    claim.confidence = decision.get("confidence_score")
    claim.decision_json = decision
    db.add(claim)
    db.commit()

    print("Decision:")
    import json

    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
