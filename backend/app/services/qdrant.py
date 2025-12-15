from typing import List, Dict, Any
import uuid
import os
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, Batch, Filter, FieldCondition, MatchValue
from sentence_transformers import SentenceTransformer

_qdrant = QdrantClient(url=os.getenv("QDRANT_URL", "http://qdrant:6333"))
_COL = "spans"
# Using all-mpnet-base-v2: Better quality, Apache 2.0 license, 768 dimensions
_model = SentenceTransformer("sentence-transformers/all-mpnet-base-v2")

def ensure_collection(dim: int = 768) -> None:
    cols = {c.name for c in _qdrant.get_collections().collections}
    if _COL not in cols:
        _qdrant.create_collection(_COL, vectors_config=VectorParams(size=dim, distance=Distance.COSINE))

def embed(texts: List[str]) -> List[List[float]]:
    return _model.encode(texts, normalize_embeddings=True).tolist() # type: ignore

def _stable_id(doc: str, idx: int) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc}::{idx}"))

def upsert_spans(doc_id: str, spans: List[Dict[str, Any]]) -> None:
    ensure_collection()
    if not spans:
        return

    vectors = embed([s["text"] for s in spans])
    ids = [_stable_id(doc_id, i) for i in range(len(spans))]
    payloads = [{"doc_id": doc_id, **s} for s in spans]

    _qdrant.upsert(
        collection_name=_COL,
        points=Batch(ids=ids, vectors=vectors, payloads=payloads),#type: ignore
        wait=True,
    )

def search_spans(doc_id: str, query: str, top_k: int = 5):
    ensure_collection()
    vec = embed([query])[0]
    qfilter = Filter(must=[FieldCondition(key="doc_id", match=MatchValue(value=doc_id))])
    hits = _qdrant.search(collection_name=_COL, query_vector=vec, limit=top_k, query_filter=qfilter, with_payload=True)
    return [h.payload or {} for h in hits]
