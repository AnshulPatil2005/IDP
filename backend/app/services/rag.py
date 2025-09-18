# backend/app/services/rag.py
from __future__ import annotations
from typing import Tuple, List, Dict, Any
from .qdrant import search_spans
from .llm import chat_with_citations

async def qa(doc_id: str, question: str) -> Tuple[str, float, List[Dict[str, Any]]]:
    hits = search_spans(doc_id, question, top_k=6)
    # Build evidence bullets (use real text if available)
    quotes = []
    for h in hits[:4]:
        chip = f"{doc_id}:{h['page']}:{h['start']}-{h['end']}"
        quotes.append(f'• "{h.get("text","")}" [{chip}]')

    system = "Answer briefly. Only use provided evidence. Always include span citations like [D:page:start-end]. If uncertain, say Unknown."
    prompt = f"Question: {question}\nEvidence:\n" + "\n".join(quotes)

    text, conf = await chat_with_citations(system, prompt)
    return text, conf, hits
