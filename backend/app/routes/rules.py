from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from ..deps import db_dep
from ..services.rules import evaluate_rules_yaml
from ..models import Clause, PolicyFire
import os, yaml

router = APIRouter(prefix="/rules", tags=["rules"])

@router.post("/validate")
def validate(doc_id: str, db: Session = Depends(db_dep)):
    rules_path = os.getenv("RULES_PATH", "/configs/rules.yaml")
    spec = yaml.safe_load(open(rules_path))
    clauses = []
    for c in db.query(Clause).filter(Clause.doc_id==doc_id).all():
        clauses.append({
            "id": c.id, "doc_id": c.doc_id, "type": c.type, "page": c.page,
            "start": c.start, "end": c.end, "text": c.text,
            "confidence": c.confidence, "normalized": c.normalized
        })
    fires = evaluate_rules_yaml(spec, clauses, doc_id)
    for f in fires:
        db.add(PolicyFire(**f))
    db.commit()
    return {"doc_id": doc_id, "fires": fires}
from fastapi import Header, HTTPException
import os
_API = os.getenv("API_KEY")

def require_api_key(x_api_key: str = Header(None)):
    if _API and x_api_key != _API:
        raise HTTPException(status_code=401, detail="Unauthorized")
