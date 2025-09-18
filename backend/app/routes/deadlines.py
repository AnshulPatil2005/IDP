from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from datetime import datetime
from ..deps import db_dep
from ..models import Deadline
from ..services.guidance import deadlines_to_ics

router = APIRouter(prefix="/docs", tags=["deadlines"])

@router.get("/{doc_id}/deadlines.ics", response_class=PlainTextResponse)
def deadlines_ics(doc_id: str, db: Session = Depends(db_dep)):
    dls = db.query(Deadline).filter(Deadline.doc_id==doc_id).all()
    payload = [{"id":d.id,"title":d.title,"due_at":d.due_at} for d in dls]
    return PlainTextResponse(content=deadlines_to_ics(doc_id, payload), media_type="text/calendar")
from fastapi import Header, HTTPException
import os
_API = os.getenv("API_KEY")

def require_api_key(x_api_key: str = Header(None)):
    if _API and x_api_key != _API:
        raise HTTPException(status_code=401, detail="Unauthorized")
