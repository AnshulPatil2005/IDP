from __future__ import annotations

import os
import uuid

from fastapi import APIRouter, Depends, File, Header, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..deps import db_dep
from ..models import Document
from ..services.pipeline import enqueue_ingestion
from ..services.storage import put_bytes

router = APIRouter(prefix="/ingest", tags=["ingest"])

_API = os.getenv("API_KEY")
_BUCKET = os.getenv("MINIO_BUCKET", "docs")


def require_api_key(x_api_key: str = Header(None)):
    if _API and x_api_key != _API:
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("", dependencies=[Depends(require_api_key)] if _API else None)
async def ingest(file: UploadFile = File(...), db: Session = Depends(db_dep)):
    doc_id = f"D{uuid.uuid4().hex[:8]}"
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    # OCR expects this key.
    object_name = f"{doc_id}/original.pdf"
    put_bytes(object_name, payload, content_type=file.content_type or "application/pdf")

    db.add(
        Document(
            doc_id=doc_id,
            title=file.filename,
            status="uploaded",
        )
    )
    db.commit()

    enqueue_ingestion(doc_id)

    return {
        "doc_id": doc_id,
        "status": "queued",
        "bucket": _BUCKET,
        "object": object_name,
    }
