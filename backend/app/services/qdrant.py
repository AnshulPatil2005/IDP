from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List

_COL = os.getenv("QDRANT_COLLECTION", "spans")
_QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
_qdrant_client: Any = None
_embed_model: Any = None
_qdrant_disabled = False
_embedding_disabled = False


def _get_qdrant():
    global _qdrant_client, _qdrant_disabled
    if _qdrant_disabled:
        raise RuntimeError("Qdrant disabled")
    if _qdrant_client is None:
        try:
            from qdrant_client import QdrantClient
        except Exception as exc:
            _qdrant_disabled = True
            raise RuntimeError(f"qdrant-client import failed: {exc}") from exc
        _qdrant_client = QdrantClient(url=_QDRANT_URL)
    return _qdrant_client


def _get_model():
    global _embed_model, _embedding_disabled
    if _embedding_disabled:
        raise RuntimeError("Embedding model disabled")
    if _embed_model is None:
        try:
            from sentence_transformers import SentenceTransformer
        except Exception as exc:
            _embedding_disabled = True
            raise RuntimeError(f"sentence-transformers import failed: {exc}") from exc
        _embed_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")
    return _embed_model


def ensure_collection(dim: int = 768) -> None:
    client = _get_qdrant()
    from qdrant_client.models import Distance, VectorParams

    cols = {c.name for c in client.get_collections().collections}
    if _COL not in cols:
        client.create_collection(_COL, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))


def embed(texts: List[str]) -> List[List[float]]:
    model = _get_model()
    return model.encode(texts, normalize_embeddings=True).tolist()  # type: ignore


def _stable_id(doc: str, idx: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc}::{idx}"))


def upsert_spans(doc_id: str, spans: List[Dict[str, Any]]) -> bool:
    if not spans:
        return True
    try:
        client = _get_qdrant()
        ensure_collection()
        from qdrant_client.models import Batch
    except Exception:
        return False

    try:
        vectors = embed([s["text"] for s in spans])
        ids = [_stable_id(doc_id, i) for i in range(len(spans))]
        payloads = [{"doc_id": doc_id, **s} for s in spans]
        client.upsert(
            collection_name=_COL,
            points=Batch(ids=ids, vectors=vectors, payloads=payloads),  # type: ignore
            wait=True,
        )
        return True
    except Exception:
        return False


def search_spans(doc_id: str, query: str, top_k: int = 5):
    try:
        client = _get_qdrant()
        ensure_collection()
        from qdrant_client.models import FieldCondition, Filter, MatchValue
    except Exception:
        return []

    try:
        vec = embed([query])[0]
        qfilter = Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))])
        hits = client.search(
            collection_name=_COL,
            query_vector=vec,
            limit=top_k,
            query_filter=qfilter,
            with_payload=True,
        )
        return [h.payload or {} for h in hits]
    except Exception:
        return []
