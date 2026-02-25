from __future__ import annotations

from typing import Any, Dict, List, Tuple

from ..db import SessionLocal
from ..models import Clause
from .llm import chat_with_citations


def _db_fallback_hits(doc_id: str, limit: int = 6) -> List[Dict[str, Any]]:
    db = SessionLocal()
    try:
        rows = db.query(Clause).filter(Clause.doc_id == doc_id).limit(limit).all()
        return [
            {
                "doc_id": r.doc_id,
                "page": r.page,
                "start": r.start,
                "end": r.end,
                "text": r.text or "",
            }
            for r in rows
        ]
    finally:
        db.close()


def _fallback_answer(doc_id: str, question: str, hits: List[Dict[str, Any]]) -> Tuple[str, float]:
    if not hits:
        return f"Unknown based on available evidence [{doc_id}:1:0-0].", 0.65
    top = hits[0]
    chip = f"[{doc_id}:{top.get('page', 1)}:{top.get('start', 0)}-{top.get('end', 0)}]"
    snippet = (top.get("text") or "").strip()
    if not snippet:
        return f"I cannot extract a confident answer yet {chip}.", 0.65
    return f'Best available evidence for "{question}": "{snippet}" {chip}', 0.7


async def qa(doc_id: str, question: str) -> Tuple[str, float, List[Dict[str, Any]]]:
    hits: List[Dict[str, Any]] = []
    try:
        from .qdrant import search_spans

        hits = search_spans(doc_id, question, top_k=6) or []
    except Exception:
        hits = []

    if not hits:
        hits = _db_fallback_hits(doc_id, limit=6)

    evidence_lines = []
    for h in hits[:4]:
        chip = f"{doc_id}:{h.get('page', 1)}:{h.get('start', 0)}-{h.get('end', 0)}"
        evidence_lines.append(f'- "{h.get("text", "")}" [{chip}]')

    system = (
        "Answer briefly. Only use provided evidence. "
        "Always include span citations like [D:page:start-end]. If uncertain, say Unknown."
    )
    prompt = f"Question: {question}\nEvidence:\n" + "\n".join(evidence_lines or ["- no evidence"])

    try:
        text, conf = await chat_with_citations(system, prompt)
        if not text:
            text, conf = _fallback_answer(doc_id, question, hits)
    except Exception:
        text, conf = _fallback_answer(doc_id, question, hits)

    return text, conf, hits
