# backend/app/routes/ask.py
from __future__ import annotations

from typing import Any, Awaitable, Mapping, Sequence, Tuple, Union, cast
from fastapi import APIRouter, HTTPException
from ..schemas.ask import AskRequest, AskAnswer
from ..schemas.common import TextSpan
from ..services import rag

router = APIRouter(prefix="", tags=["ask"])

# Helper: sync/async tolerant
async def _maybe_await(
    v: Union[
        Tuple[str, float, list[dict[str, Any]]],
        Awaitable[Tuple[str, float, list[dict[str, Any]]]]
    ]
) -> Tuple[str, float, list[dict[str, Any]]]:
    if hasattr(v, "__await__"):
        return await cast(Awaitable[Tuple[str, float, list[dict[str, Any]]]], v)
    return cast(Tuple[str, float, list[dict[str, Any]]], v)

# Helpers to appease the type checker and guard against None/bad types
def to_int(x: Any, default: int = 0) -> int:
    if x is None:
        return default
    try:
        return int(x)  # handles int, float, str with digits, objects with __int__/__index__
    except Exception:
        return default

def to_str(x: Any, default: str = "") -> str:
    return str(x) if x is not None else default

@router.post("/ask", response_model=AskAnswer)
async def ask(req: AskRequest) -> AskAnswer:
    try:
        answer, conf, hits_raw = await _maybe_await(rag.qa(req.doc_id, req.question))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG pipeline failed: {type(e).__name__}: {e}")

    if not isinstance(answer, str) or not isinstance(conf, (int, float)):
        raise HTTPException(status_code=500, detail="RAG pipeline returned invalid types")

    # Require citations + minimum confidence
    if conf < 0.6 or "[" not in answer:
        raise HTTPException(status_code=428, detail="Need review: insufficient evidence/citations")

    # Treat hits as a sequence of mappings for stricter typing
    hits: Sequence[Mapping[str, Any]] = cast(Sequence[Mapping[str, Any]], hits_raw or [])

    spans: list[TextSpan] = []
    quotes: list[str] = []

    for h in hits[:3]:
        doc_id = to_str(h.get("doc_id"), req.doc_id)
        page = to_int(h.get("page"), 0)
        start = to_int(h.get("start"), 0)
        end = to_int(h.get("end"), start if start >= 0 else 0)
        spans.append(TextSpan(doc_id=doc_id, page=page, start=start, end=end))
        quotes.append(to_str(h.get("text"), ""))

    return AskAnswer(answer=answer, confidence=float(conf), evidence=spans, quotes=quotes)
