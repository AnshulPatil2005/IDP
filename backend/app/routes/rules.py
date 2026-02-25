from __future__ import annotations

import os
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..deps import db_dep
from ..models import Clause, PolicyFire
from ..services.rules import evaluate_rules_yaml

router = APIRouter(prefix="/rules", tags=["rules"])


def _default_rules_path() -> Path:
    return Path(__file__).resolve().parents[3] / "configs" / "rules.yaml"


@router.post("/validate")
def validate(doc_id: str, db: Session = Depends(db_dep)):
    configured = os.getenv("RULES_PATH")
    rules_path = Path(configured).expanduser() if configured else _default_rules_path()
    if not rules_path.exists():
        raise HTTPException(status_code=500, detail=f"Rules file not found: {rules_path}")

    with rules_path.open("r", encoding="utf-8") as f:
        spec = yaml.safe_load(f) or {"rules": []}

    clauses = []
    for c in db.query(Clause).filter(Clause.doc_id == doc_id).all():
        clauses.append(
            {
                "id": c.id,
                "doc_id": c.doc_id,
                "type": c.type,
                "page": c.page,
                "start": c.start,
                "end": c.end,
                "text": c.text,
                "confidence": c.confidence,
                "normalized": c.normalized,
            }
        )

    fires = evaluate_rules_yaml(spec, clauses, doc_id)
    db.query(PolicyFire).filter(PolicyFire.doc_id == doc_id).delete()
    for fire in fires:
        db.add(PolicyFire(**fire))
    db.commit()
    return {"doc_id": doc_id, "fires": fires}
