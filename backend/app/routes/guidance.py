# backend/app/routes/guidance.py
from __future__ import annotations

import re
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..deps import db_dep
from ..models import Guidance as GModel, Clause, PolicyFire
from ..schemas.guidance import GuidanceItemOut

router = APIRouter(prefix="/docs", tags=["guidance"])

# chip format: "D1:14:231-560"
_CHIP_RX = re.compile(r"^(?P<doc>[^:]+):(?P<page>\d+):(?P<start>\d+)-(?P<end>\d+)$")


def _policy_rule_for_first_chip(
    db: Session, doc_id: str, evidence: list[str]
) -> tuple[Optional[str], Optional[str]]:
    """
    Resolve (policy_rule_id, severity) for the first evidence chip, if possible.
    Returns (None, None) if not resolvable.
    """
    if not evidence:
        return None, None

    m = _CHIP_RX.match(evidence[0])
    if not m:
        return None, None
    # ensure same doc; otherwise ignore
    if m.group("doc") != doc_id:
        return None, None

    page = int(m.group("page"))
    start = int(m.group("start"))
    end = int(m.group("end"))

    clause = (
        db.query(Clause)
        .filter(
            Clause.doc_id == doc_id,
            Clause.page == page,
            Clause.start == start,
            Clause.end == end,
        )
        .first()
    )
    if not clause:
        return None, None

    fire = (
        db.query(PolicyFire)
        .filter(
            PolicyFire.doc_id == doc_id,
            PolicyFire.clause_id == clause.id,
        )
        .first()
    )
    if not fire:
        return None, None

    return fire.rule_id, fire.severity


@router.get("/{doc_id}/guidance", response_model=list[GuidanceItemOut])
def get_guidance(doc_id: str, db: Session = Depends(db_dep)) -> list[GuidanceItemOut]:
    rows = db.query(GModel).filter(GModel.doc_id == doc_id).all()
    out: list[GuidanceItemOut] = []

    for g in rows:
        policy_rule, severity = _policy_rule_for_first_chip(db, doc_id, g.evidence or [])

        # Prefer the stored risk (set by composer); if absent, fall back to severity or "low"
        risk_value = g.risk or severity or "low"

        out.append(
            GuidanceItemOut(
                id=g.id,
                doc_id=g.doc_id,
                title=g.title,
                what_it_means=g.what,
                action=g.action,
                risk=risk_value,
                deadline=g.deadline,
                evidence=g.evidence or [],
                confidence=float(g.confidence or 0.0),
                policy_rule=policy_rule,
            )
        )

    return out
from fastapi import Header, HTTPException
import os
_API = os.getenv("API_KEY")

def require_api_key(x_api_key: str = Header(None)):
    if _API and x_api_key != _API:
        raise HTTPException(status_code=401, detail="Unauthorized")
