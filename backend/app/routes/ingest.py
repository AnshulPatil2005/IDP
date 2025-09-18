# backend/api/routers/ingest.py
from fastapi import APIRouter, UploadFile, File, Depends, Header, HTTPException
from sqlalchemy.orm import Session
from ..deps import db_dep
from ..models import Document
from ..services.pipeline import enqueue_ingestion
from minio import Minio#type: ignore
import uuid, os

router = APIRouter(prefix="/ingest", tags=["ingest"])

# ---- MinIO config from env ----
_MINIO_ENDPOINT   = os.getenv("MINIO_ENDPOINT", "minio:9000")  # use "localhost:9000" if not in Docker
_MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
_MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minioadmin")
_MINIO_BUCKET     = os.getenv("MINIO_BUCKET", "docs")
_MINIO_SECURE     = os.getenv("MINIO_SECURE", "false").lower() == "true"

minio_client = Minio(
    _MINIO_ENDPOINT,
    access_key=_MINIO_ACCESS_KEY,
    secret_key=_MINIO_SECRET_KEY,
    secure=_MINIO_SECURE,
)

# Ensure bucket exists (lazy init)
def _ensure_bucket():
    if not minio_client.bucket_exists(_MINIO_BUCKET):
        minio_client.make_bucket(_MINIO_BUCKET)

# Optional API key gate
_API = os.getenv("API_KEY")
def require_api_key(x_api_key: str = Header(None)):
    if _API and x_api_key != _API:
        raise HTTPException(status_code=401, detail="Unauthorized")

@router.post("", dependencies=[Depends(require_api_key)] if _API else None)
async def ingest(file: UploadFile = File(...), db: Session = Depends(db_dep)):
    # 1) Create a doc_id and object name
    doc_id = f"D{uuid.uuid4().hex[:8]}"
    _, ext = os.path.splitext(file.filename or "")
    object_name = f"{doc_id}{ext or ''}"

    # 2) Ensure bucket exists and upload (streaming, no full file in RAM)
    _ensure_bucket()
    # IMPORTANT: don't pre-read the file; use file.file directly
    minio_client.put_object(
        _MINIO_BUCKET,
        object_name,
        data=file.file,                 # SpooledTemporaryFile from Starlette
        length=-1,                      # unknown length → multipart
        part_size=10 * 1024 * 1024,     # 10MB parts
        content_type=file.content_type or "application/octet-stream",
    )

    # 3) Record in DB and mark as 'uploaded' (adjust field names as your model requires)
    db.add(Document(
        doc_id=doc_id,
        title=file.filename,
        status="uploaded",              # was "queued" before; now it's uploaded to storage
        # storage_uri=f"s3://{_MINIO_BUCKET}/{object_name}",  # uncomment if your model has this field
    ))
    db.commit()

    # 4) Kick off async pipeline
    enqueue_ingestion(doc_id)

    return {
        "doc_id": doc_id,
        "status": "queued",             # queued for processing
        "bucket": _MINIO_BUCKET,
        "object": object_name,
    }
