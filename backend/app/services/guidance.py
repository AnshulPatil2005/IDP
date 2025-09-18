# backend/app/services/guidance.py
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Clause, PolicyFire, Guidance as GModel


def compose(doc_id: str) -> dict:
    """
    Compose GuidanceItems for a document from clauses and policy fires.
    - Per-clause, attach the matching PolicyFire (if any) to set risk.
    - Replace any existing guidance items for this doc to avoid duplicates.
    """
    db: Session = SessionLocal()
    try:
        # Fetch once
        clauses: List[Clause] = (
            db.query(Clause).filter(Clause.doc_id == doc_id).all()
        )
        fires_by_clause: Dict[str, PolicyFire] = {
            f.clause_id: f
            for f in db.query(PolicyFire).filter(PolicyFire.doc_id == doc_id).all()
        }

        # Clear existing guidance for this doc (simple upsert strategy)
        db.query(GModel).filter(GModel.doc_id == doc_id).delete()

        created = 0
        for c in clauses:
            # Build evidence chip like "D1:14:231-560"
            evidence_chip = f"{c.doc_id}:{c.page}:{c.start}-{c.end}"
            fire = fires_by_clause.get(c.id)  # may be None
            risk = fire.severity if fire else "low"

            g = GModel(
                doc_id=c.doc_id,
                title=f"{c.type.replace('_', ' ').title()} – check terms",
                what="Detected clause with potential considerations.",
                action="Review and align with policy.",
                risk=risk,
                deadline=None,
                evidence=[evidence_chip],
                confidence=float(c.confidence or 0.0),
            )
            db.add(g)
            created += 1

        db.commit()
        return {"guidance_items": created}
    finally:
        db.close()


def deadlines_to_ics(doc_id: str, deadlines: List[dict]) -> str:
    """
    Convert a list of deadlines into an iCalendar string.

    Each deadline dict is expected to contain:
      - id: str
      - title: str
      - due_at: datetime
    """
    def _dt(dt: datetime) -> str:
        # UTC (Z) format; adjust if you store tz-aware datetimes
        return dt.strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Titan-Guidance//EN",
    ]

    for d in deadlines:
        due_at = d["due_at"]
        if not isinstance(due_at, datetime):
            # Skip invalid entries silently; alternatively raise
            continue

        lines += [
            "BEGIN:VEVENT",
            f"UID:{d['id']}@titan-guidance",
            f"DTSTAMP:{_dt(due_at)}",
            f"DTSTART:{_dt(due_at)}",
            f"SUMMARY:{d['title']} (Doc {doc_id})",
            "END:VEVENT",
        ]

    lines.append("END:VCALENDAR")
    return "\r\n".join(lines)
