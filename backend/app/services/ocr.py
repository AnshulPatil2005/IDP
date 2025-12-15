# backend/app/services/ocr.py
from __future__ import annotations

import io
from typing import Dict, List
from PIL import Image
import numpy as np
from doctr.io import DocumentFile
from doctr.models import ocr_predictor
from .storage import put_json, put_bytes, get_bytes

# Initialize docTR model (lazy load)
_predictor = None

def _get_predictor():
    """Lazy load the OCR predictor model."""
    global _predictor
    if _predictor is None:
        # Use pre-trained model: db_resnet50 for detection + crnn_vgg16_bn for recognition
        # Set pretrained=True to download weights automatically
        _predictor = ocr_predictor(det_arch='db_resnet50', reco_arch='crnn_vgg16_bn', pretrained=True)
    return _predictor

def run(doc_id: str) -> Dict[str, bool]:
    """
    OCR pipeline using docTR:
      1) Load PDF bytes from MinIO storage.
      2) Use docTR to process PDF directly (no rasterization needed).
      3) Extract text with bounding boxes from docTR output.
      4) Build spans with char [start,end] and bbox.
      5) Save page images and layout_index.json.
    Returns: {"layout_index": True}
    """
    pdf_bytes = _fetch_pdf_bytes(doc_id)
    if not pdf_bytes:
        # Fallback: keep compatibility so the app has at least one span
        layout = {"pages": {"1": {"width": 800, "height": 1100,
                                  "spans": [{"start": 10, "end": 30, "bbox": [100, 200, 250, 40], "text": ""}]}}}
        put_json(f"{doc_id}/layout_index.json", layout)
        return {"layout_index": True}

    # docTR can process PDF directly from bytes
    doc = DocumentFile.from_pdf(io.BytesIO(pdf_bytes))

    # Run OCR prediction
    predictor = _get_predictor()
    result = predictor(doc)

    layout = {"pages": {}}

    # Process each page
    for page_idx, page in enumerate(result.pages, start=1):
        # Get page dimensions (docTR works in normalized coordinates 0-1)
        # We need to get the actual image to save it and get dimensions
        page_img = doc[page_idx - 1]  # docTR doc is 0-indexed

        # Convert numpy array to PIL Image if needed
        if isinstance(page_img, np.ndarray):
            page_img = Image.fromarray((page_img * 255).astype(np.uint8) if page_img.max() <= 1 else page_img.astype(np.uint8))

        # Save page image as JPEG
        buf = io.BytesIO()
        page_img.save(buf, format="JPEG", quality=85)
        put_bytes(f"{doc_id}/pages/{page_idx}.jpg", buf.getvalue(), content_type="image/jpeg")

        page_width = page_img.width
        page_height = page_img.height

        page_spans: List[Dict] = []
        cursor = 0  # character index within this page

        # Process blocks -> lines -> words
        for block in page.blocks:
            for line in block.lines:
                for word in line.words:
                    text = word.value.strip()
                    if not text:
                        continue

                    # docTR provides normalized coordinates (0-1)
                    # Format: ((x_min, y_min), (x_max, y_max))
                    geometry = word.geometry
                    x_min, y_min = geometry[0]
                    x_max, y_max = geometry[1]

                    # Convert to pixel coordinates
                    left = int(x_min * page_width)
                    top = int(y_min * page_height)
                    width = int((x_max - x_min) * page_width)
                    height = int((y_max - y_min) * page_height)

                    # Add space before word if not first word
                    if page_spans:
                        cursor += 1

                    start = cursor
                    cursor += len(text)
                    end = cursor

                    page_spans.append({
                        "start": start,
                        "end": end,
                        "bbox": [left, top, width, height],  # x, y, w, h in pixels
                        "text": text,
                        "confidence": word.confidence,  # docTR provides confidence scores
                    })

        layout["pages"][str(page_idx)] = {
            "width": page_width,
            "height": page_height,
            "spans": page_spans,
        }

    put_json(f"{doc_id}/layout_index.json", layout)
    return {"layout_index": True}


# --- helpers ---------------------------------------------------------------

def _fetch_pdf_bytes(doc_id: str) -> bytes | None:
    """
    Fetch PDF bytes from MinIO storage.
    Falls back to local disk if storage fails.
    """
    # First try MinIO storage
    pdf_bytes = get_bytes(f"{doc_id}/original.pdf")
    if pdf_bytes:
        return pdf_bytes

    # Fallback: try local disk (for dev environment)
    try:
        import os
        path = f"/app_storage/{doc_id}/original.pdf"
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
    except Exception:
        pass

    return None
