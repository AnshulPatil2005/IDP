from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..deps import db_dep
from ..models import Clause
from ..schemas.clause import ClauseOut, ClauseTypeEnum
from ..schemas.common import TextSpan

router = APIRouter(prefix="/docs", tags=["clauses"])

@router.get("/{doc_id}/clauses", response_model=list[ClauseOut])
def get_clauses(doc_id: str, db: Session = Depends(db_dep)):
    rows = db.query(Clause).filter(Clause.doc_id == doc_id).all()
    out = []
    for c in rows:
        ctype = ClauseTypeEnum(c.type)
        out.append(ClauseOut(
    id=c.id, doc_id=c.doc_id, type=ctype, parties=[],
    text_span=TextSpan(doc_id=c.doc_id, page=c.page, start=c.start, end=c.end),
    text=c.text, confidence=c.confidence, normalized=c.normalized
        ))
    return out
from fastapi import Header, HTTPException
import os
_API = os.getenv("API_KEY")

def require_api_key(x_api_key: str = Header(None)):
    if _API and x_api_key != _API:
        raise HTTPException(status_code=401, detail="Unauthorized")
