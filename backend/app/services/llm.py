# backend/app/services/llm.py
from __future__ import annotations
import os
from typing import Tuple, Dict, Any, List
import httpx

PROVIDER = os.getenv("LLM_PROVIDER", "openrouter").lower()
MODEL = os.getenv("LLM_MODEL", "deepseek/deepseek-chat-v3-0324:free")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Legacy Ollama support (deprecated)
OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://localhost:11434")

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

    Supports multiple LLM providers:
    - openrouter: Uses OpenRouter API with various free models
    - ollama: Legacy local Ollama support (deprecated)
    """
    if PROVIDER == "openrouter":
        return await _chat_openrouter(system, prompt)
    elif PROVIDER == "ollama":
        return await _chat_ollama(system, prompt)
    else:
        raise RuntimeError(f"LLM_PROVIDER={PROVIDER} not supported. Use 'openrouter' or 'ollama'.")

async def _chat_openrouter(system: str, prompt: str) -> Tuple[str, float]:
    """Chat using OpenRouter API (OpenAI-compatible format)."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not configured in environment")

    url = f"{OPENROUTER_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "HTTP-Referer": "https://titan-guidance.app",  # Optional: your site URL
        "X-Title": "Titan-Guidance",  # Optional: your app name
        "Content-Type": "application/json"
    }

    payload = {
        "model": MODEL,
        "messages": _format_messages(system, prompt),
        "temperature": 0.0,
        "max_tokens": 2000
    }

    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, json=payload, headers=headers)
        r.raise_for_status()
        data = r.json()

    # OpenAI-compatible response format
    text = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
    if not text:
        text = "Unable to generate response."

    return text, _confidence_heuristic(text)

async def _chat_ollama(system: str, prompt: str) -> Tuple[str, float]:
    """Chat using Ollama API (legacy support)."""
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
