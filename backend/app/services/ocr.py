# backend/app/services/ocr.py
from __future__ import annotations

import io
from typing import Dict, List
from pdf2image import convert_from_bytes
import pytesseract
from pytesseract import Output
from .storage import put_json, put_bytes  # ensure these save bytes/JSON to your storage

def run(doc_id: str) -> Dict[str, bool]:
    """
    OCR pipeline (MVP):
      1) Load PDF bytes (implement your own fetch).
      2) Rasterize pages (pdf2image).
      3) OCR each page (pytesseract).
      4) Build spans with char [start,end] and bbox.
      5) Save page images and layout_index.json.
    Returns: {"layout_index": True}
    """
    # TODO: replace with your real fetch (from MinIO or disk)
    pdf_bytes = _fetch_pdf_bytes(doc_id)
    if not pdf_bytes:
        # Fallback: keep compatibility so the app has at least one span
        layout = {"pages": {"1": {"width": 800, "height": 1100,
                                  "spans": [{"start": 10, "end": 30, "bbox": [100, 200, 250, 40], "text": ""}]}}}
        put_json(f"{doc_id}/layout_index.json", layout)
        return {"layout_index": True}

    # 1) Rasterize PDF → PIL Images (requires poppler in the container OS for pdf2image)
    pages = convert_from_bytes(pdf_bytes, dpi=200)
    layout = {"pages": {}}

    for idx, img in enumerate(pages, start=1):
        # 2) Save a JPEG of the page for the frontend viewer/overlay
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        put_bytes(f"{doc_id}/pages/{idx}.jpg", buf.getvalue(), content_type="image/jpeg")

        # 3) OCR words with positions
        data = pytesseract.image_to_data(img, output_type=Output.DICT)  # keys: 'text','left','top','width','height','conf','level', etc.

        page_spans: List[Dict] = []
        cursor = 0  # character index within this page
        page_text_parts: List[str] = []

        n = len(data["text"])
        for i in range(n):
            word = (data["text"][i] or "").strip()
            if not word:
                continue
            left, top, width, height = data["left"][i], data["top"][i], data["width"][i], data["height"][i]

            # naive text stream with a space between tokens
            if page_text_parts:
                page_text_parts.append(" ")
                cursor += 1
            start = cursor
            page_text_parts.append(word)
            cursor += len(word)
            end = cursor

            page_spans.append({
                "start": start,
                "end": end,
                "bbox": [left, top, width, height],  # x, y, w, h in pixels on the rasterized page
                "text": word,
            })

        layout["pages"][str(idx)] = {
            "width": img.width,
            "height": img.height,
            "spans": page_spans,
        }

    put_json(f"{doc_id}/layout_index.json", layout)
    return {"layout_index": True}


# --- helpers ---------------------------------------------------------------

def _fetch_pdf_bytes(doc_id: str) -> bytes | None:
    """
    Replace this stub with your real storage:
      - If you’re on MinIO: add a get_bytes() helper and call it here.
      - If you store locally in dev: read from /app_storage/{doc_id}/original.pdf
    """
    try:
        # Example: local dev fallback (if you saved uploaded PDFs to disk)
        import os
        path = f"/app_storage/{doc_id}/original.pdf"
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
    except Exception:
        pass
    return None
