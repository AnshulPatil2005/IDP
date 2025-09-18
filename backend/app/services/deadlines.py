from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from ..db import SessionLocal
from ..models import Deadline

def run(doc_id: str):
    db: Session = SessionLocal()
    try:
        d1 = Deadline(doc_id=doc_id, title="Renewal notice window", due_at=datetime.utcnow()+timedelta(days=15))
        db.add(d1); db.commit()
        return {"deadlines": 1}
    finally:
        db.close()
