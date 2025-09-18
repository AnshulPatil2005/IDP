from sqlalchemy.orm import Session
from ..db import SessionLocal
from ..models import Clause

def run(doc_id: str):
    db: Session = SessionLocal()
    try:
        # seed 2 clauses
        c1 = Clause(doc_id=doc_id, type="limitation_of_liability", page=1, start=10, end=30,
                    text="Liability is capped at fifty percent (50%) of annual fees.",
                    confidence=0.9, normalized={"cap_ratio_to_annual_fees": 0.5})
        c2 = Clause(doc_id=doc_id, type="renewal", page=1, start=100, end=130,
                    text="Auto-renews with a 15 days notice window.", confidence=0.85,
                    normalized={"notice_days": 15})
        db.add_all([c1, c2]); db.commit()
        return {"clauses": 2}
    finally:
        db.close()
from fastapi import Header, HTTPException
import os
_API = os.getenv("API_KEY")

def require_api_key(x_api_key: str = Header(None)):
    if _API and x_api_key != _API:
        raise HTTPException(status_code=401, detail="Unauthorized")
