from __future__ import annotations

import io
import os
from typing import Any, Dict, List, Tuple

from .storage import get_bytes, put_bytes, put_json

_predictor: Any = None
_document_file_cls: Any = None
_doctr_available = True


def _fallback_layout(doc_id: str) -> Dict[str, bool]:
    layout = {
        "pages": {
            "1": {
                "width": 800,
                "height": 1100,
                "spans": [
                    {
                        "start": 0,
                        "end": 36,
                        "bbox": [40, 40, 720, 30],
                        "text": "OCR unavailable; fallback layout generated.",
                        "confidence": 0.5,
                    }
                ],
            }
        }
    }
    put_json(f"{doc_id}/layout_index.json", layout)
    return {"layout_index": True}


def _get_doctr() -> Tuple[Any, Any]:
    global _predictor, _document_file_cls, _doctr_available
    if _predictor is not None and _document_file_cls is not None:
        return _predictor, _document_file_cls
    if not _doctr_available:
        raise RuntimeError("docTR is unavailable")
    if os.getenv("OCR_BACKEND", "doctr").lower() == "stub":
        raise RuntimeError("OCR backend configured to stub mode")

    try:
        import numpy as np
        from PIL import Image
        from doctr.io import DocumentFile
        from doctr.models import ocr_predictor
    except Exception as exc:  # pragma: no cover - dependency-sensitive
        _doctr_available = False
        raise RuntimeError(f"docTR import failed: {exc}") from exc

    # keep symbols available to run()
    _predictor = ocr_predictor(det_arch="db_resnet50", reco_arch="crnn_vgg16_bn", pretrained=True)
    _document_file_cls = (DocumentFile, Image, np)
    return _predictor, _document_file_cls


def _fetch_pdf_bytes(doc_id: str) -> bytes | None:
    return get_bytes(f"{doc_id}/original.pdf")


def run(doc_id: str) -> Dict[str, bool]:
    pdf_bytes = _fetch_pdf_bytes(doc_id)
    if not pdf_bytes:
        return _fallback_layout(doc_id)

    try:
        predictor, doctr_bundle = _get_doctr()
        DocumentFile, Image, np = doctr_bundle
    except Exception:
        return _fallback_layout(doc_id)

    try:
        doc = DocumentFile.from_pdf(io.BytesIO(pdf_bytes))
        result = predictor(doc)
    except Exception:
        return _fallback_layout(doc_id)

    layout: Dict[str, Any] = {"pages": {}}
    for page_idx, page in enumerate(result.pages, start=1):
        page_img = doc[page_idx - 1]
        if isinstance(page_img, np.ndarray):
            if page_img.max() <= 1:
                page_img = Image.fromarray((page_img * 255).astype("uint8"))
            else:
                page_img = Image.fromarray(page_img.astype("uint8"))

        buf = io.BytesIO()
        page_img.save(buf, format="JPEG", quality=85)
        put_bytes(f"{doc_id}/pages/{page_idx}.jpg", buf.getvalue(), content_type="image/jpeg")

        page_width = page_img.width
        page_height = page_img.height
        page_spans: List[Dict[str, Any]] = []
        cursor = 0

        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    text = (word.value or "").strip()
                    if not text:
                        continue

                    ((x_min, y_min), (x_max, y_max)) = word.geometry
                    left = int(x_min * page_width)
                    top = int(y_min * page_height)
                    width = int((x_max - x_min) * page_width)
                    height = int((y_max - y_min) * page_height)

                    if page_spans:
                        cursor += 1
                    start = cursor
                    cursor += len(text)
                    end = cursor

                    page_spans.append(
                        {
                            "start": start,
                            "end": end,
                            "bbox": [left, top, width, height],
                            "text": text,
                            "confidence": float(getattr(word, "confidence", 0.0) or 0.0),
                        }
                    )

        layout["pages"][str(page_idx)] = {
            "width": page_width,
            "height": page_height,
            "spans": page_spans,
        }

    if not layout["pages"]:
        return _fallback_layout(doc_id)

    put_json(f"{doc_id}/layout_index.json", layout)
    return {"layout_index": True}
