from __future__ import annotations

import uuid
from datetime import datetime, date

from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    Float,
    Boolean,
    Text,
    JSON,
    ForeignKey,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Policy(Base):
    __tablename__ = "policies"

    id = Column(Integer, primary_key=True)
    policy_code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(256), nullable=True)
    policy_json = Column(JSON, nullable=False)
    effective_date = Column(Date, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    members = relationship("Member", back_populates="policy")


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True)
    member_code = Column(String(64), unique=True, index=True, nullable=False)
    name = Column(String(256), nullable=False)
    join_date = Column(Date, nullable=True)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=True)
    dependents = Column(Boolean, default=False)

    policy = relationship("Policy", back_populates="members")
    claims = relationship("Claim", back_populates="member")


class Provider(Base):
    __tablename__ = "providers"

    id = Column(Integer, primary_key=True)
    name = Column(String(256), nullable=False)
    is_network = Column(Boolean, default=False)
    registration_no = Column(String(128), nullable=True, unique=False)


class Claim(Base):
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True)
    claim_code = Column(String(64), unique=True, index=True, nullable=False, default=generate_uuid)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=True)
    treatment_date = Column(Date, nullable=False)
    submission_date = Column(Date, nullable=True)
    hospital = Column(String(256), nullable=True)
    cashless_request = Column(Boolean, default=False)
    total_amount = Column(Float, nullable=False, default=0.0)
    status = Column(String(64), nullable=False, default="PENDING")
    approved_amount = Column(Float, nullable=True)
    confidence = Column(Float, nullable=True)
    decision_json = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    member = relationship("Member", back_populates="claims")
    items = relationship("ClaimItem", back_populates="claim", cascade="all, delete-orphan")
    documents = relationship("Document", back_populates="claim", cascade="all, delete-orphan")
    audits = relationship("AuditLog", back_populates="claim", cascade="all, delete-orphan")


class ClaimItem(Base):
    __tablename__ = "claim_items"

    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    category = Column(String(128), nullable=True)
    description = Column(String(512), nullable=True)
    amount = Column(Float, nullable=False, default=0.0)
    approved_amount = Column(Float, nullable=True)
    reason_code = Column(String(128), nullable=True)

    claim = relationship("Claim", back_populates="items")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True)
    doc_code = Column(String(64), unique=True, index=True, nullable=False, default=generate_uuid)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False)
    doc_type = Column(String(64), nullable=False)
    filename = Column(String(512), nullable=True)
    ocr_text = Column(Text, nullable=True)
    extracted_json = Column(JSON, nullable=True)
    upload_ts = Column(DateTime, server_default=func.now())

    claim = relationship("Claim", back_populates="documents")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=True)
    actor = Column(String(128), nullable=True)
    action = Column(String(128), nullable=False)
    payload = Column(JSON, nullable=True)
    ts = Column(DateTime, server_default=func.now())

    claim = relationship("Claim", back_populates="audits")


class Usage(Base):
    __tablename__ = "usage"

    id = Column(Integer, primary_key=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False)
    policy_year = Column(Integer, nullable=False)
    used_amount = Column(Float, nullable=False, default=0.0)

    # optional relationship if needed
    member = relationship("Member")
