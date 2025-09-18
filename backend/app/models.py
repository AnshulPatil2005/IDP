from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime
import uuid
from .db import Base

def _id(prefix="id"): return f"{prefix}_{uuid.uuid4().hex[:10]}"

class Document(Base):
    __tablename__ = "documents"
    doc_id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[str] = mapped_column(String, default="queued")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class Clause(Base):
    __tablename__ = "clauses"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("cl"))
    doc_id: Mapped[str] = mapped_column(String, ForeignKey("documents.doc_id"))
    type: Mapped[str] = mapped_column(String, index=True)
    page: Mapped[int] = mapped_column(Integer)
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)
    text: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, default=0.8)
    normalized: Mapped[dict] = mapped_column(JSON, default={})

class Guidance(Base):
    __tablename__ = "guidance"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("gd"))
    doc_id: Mapped[str] = mapped_column(String, ForeignKey("documents.doc_id"))
    title: Mapped[str] = mapped_column(String)
    what: Mapped[str] = mapped_column(Text)
    action: Mapped[str | None] = mapped_column(Text)
    risk: Mapped[str] = mapped_column(String, default="low")
    deadline: Mapped[str | None] = mapped_column(String)
    evidence: Mapped[list] = mapped_column(JSON, default=[])
    confidence: Mapped[float] = mapped_column(Float, default=0.8)

class Deadline(Base):
    __tablename__ = "deadlines"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("dl"))
    doc_id: Mapped[str] = mapped_column(String, ForeignKey("documents.doc_id"))
    title: Mapped[str] = mapped_column(String)
    due_at: Mapped[datetime] = mapped_column(DateTime)
    source_clause_id: Mapped[str | None] = mapped_column(String, ForeignKey("clauses.id"))

class PolicyFire(Base):
    __tablename__ = "policy_fires"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: _id("pf"))
    rule_id: Mapped[str] = mapped_column(String)
    doc_id: Mapped[str] = mapped_column(String, ForeignKey("documents.doc_id"))
    clause_id: Mapped[str] = mapped_column(String, ForeignKey("clauses.id"))
    severity: Mapped[str] = mapped_column(String)
    message: Mapped[str] = mapped_column(Text)
