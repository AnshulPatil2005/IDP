from .storage import get_json


def run(doc_id: str):
    layout = get_json(f"{doc_id}/layout_index.json") or {"pages": {}}
    spans = []
    for page, pdata in layout.get("pages", {}).items():
        for sp in pdata.get("spans", []):
            spans.append(
                {
                    "page": int(page),
                    "start": sp["start"],
                    "end": sp["end"],
                    "bbox": sp.get("bbox"),
                    "text": sp.get("text", f"page{page}:{sp['start']}-{sp['end']}"),
                }
            )

    indexed = 0
    if spans:
        try:
            from .qdrant import upsert_spans

            if upsert_spans(doc_id, spans):
                indexed = len(spans)
        except Exception:
            indexed = 0

    return {"embeddings": len(spans), "indexed": indexed}
