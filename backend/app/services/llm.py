# backend/app/services/llm.py
from __future__ import annotations
import os
from typing import Tuple, Dict, Any, List
import httpx

PROVIDER = os.getenv("LLM_PROVIDER", "ollama").lower()
MODEL = os.getenv("LLM_MODEL", "llama3.1:8b-instruct")
OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")  # host URL (containers: host.docker.internal)

def _format_messages(system: str, user: str) -> List[Dict[str, str]]:
    msgs: List[Dict[str, str]] = []
    if system:
        msgs.append({"role": "system", "content": system})
    msgs.append({"role": "user", "content": user})
    return msgs

def _confidence_heuristic(text: str) -> float:
    # Simple heuristic: if model emitted bracketed citations, assume higher confidence
    return 0.8 if "[" in text and "]" in text else 0.55

async def chat_with_citations(system: str, prompt: str) -> Tuple[str, float]:
    """
    Returns (answer_text, confidence).
    Assumes you already embedded evidence and 'cite like [D:page:start-end]' instructions in 'prompt'.
    """
    if PROVIDER != "ollama":
        raise RuntimeError(f"LLM_PROVIDER={PROVIDER} not supported in this file. Set LLM_PROVIDER=ollama.")

    url = f"{OLLAMA_BASE.rstrip('/')}/api/chat"
    payload = {
        "model": MODEL,
        "messages": _format_messages(system, prompt),
        "stream": False,
        "options": {"temperature": 0.0}
    }
    async with httpx.AsyncClient(timeout=60) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        data = r.json()

    text = (data.get("message") or {}).get("content", "").strip()
    return text, _confidence_heuristic(text)
