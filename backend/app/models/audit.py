from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime
from ..db import Base

class Audit(Base):
    __tablename__ = "audit"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    doc_id: Mapped[str]
    stage: Mapped[str]          # e.g. "ocr", "clauses", "summarizer"
    input: Mapped[dict] = mapped_column(JSONB)
    output: Mapped[dict] = mapped_column(JSONB)
    model: Mapped[str | None]
    created_at: Mapped[datetime]
