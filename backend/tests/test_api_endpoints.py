from __future__ import annotations

import os
from pathlib import Path

from fastapi.testclient import TestClient


def test_all_api_endpoints_with_sample_pdf(tmp_path: Path):
    sample_pdf = Path(os.getenv("SAMPLE_PDF_PATH", r"C:\Users\dpati\Downloads\3450439.3451867.pdf"))
    if not sample_pdf.exists():
        raise AssertionError(f"Sample PDF not found: {sample_pdf}")

    project_root = Path(__file__).resolve().parents[2]
    db_path = tmp_path / "test.db"
    storage_root = tmp_path / "storage"

    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ["PIPELINE_MODE"] = "sync"
    os.environ["STORAGE_BACKEND"] = "local"
    os.environ["STORAGE_LOCAL_ROOT"] = str(storage_root)
    os.environ["RULES_PATH"] = str(project_root / "configs" / "rules.yaml")
    os.environ["OCR_BACKEND"] = "stub"
    os.environ["API_KEY"] = ""
    os.environ.pop("OPENROUTER_API_KEY", None)

    from backend.app.main import app

    client = TestClient(app)

    health = client.get("/")
    assert health.status_code == 200
    assert health.json() == {"ok": True}

    with sample_pdf.open("rb") as f:
        ingest = client.post(
            "/ingest",
            files={"file": (sample_pdf.name, f, "application/pdf")},
        )
    assert ingest.status_code == 200, ingest.text
    ingest_payload = ingest.json()
    doc_id = ingest_payload["doc_id"]
    assert ingest_payload["status"] == "queued"
    assert ingest_payload["object"] == f"{doc_id}/original.pdf"

    clauses = client.get(f"/docs/{doc_id}/clauses")
    assert clauses.status_code == 200, clauses.text
    clauses_payload = clauses.json()
    assert len(clauses_payload) >= 2

    validation = client.post(f"/rules/validate?doc_id={doc_id}")
    assert validation.status_code == 200, validation.text
    validation_payload = validation.json()
    assert validation_payload["doc_id"] == doc_id
    assert len(validation_payload["fires"]) >= 1

    guidance = client.get(f"/docs/{doc_id}/guidance")
    assert guidance.status_code == 200, guidance.text
    guidance_payload = guidance.json()
    assert len(guidance_payload) >= 1

    deadlines = client.get(f"/docs/{doc_id}/deadlines.ics")
    assert deadlines.status_code == 200, deadlines.text
    assert "BEGIN:VCALENDAR" in deadlines.text
    assert "END:VCALENDAR" in deadlines.text

    ask = client.post(
        "/ask",
        json={"doc_id": doc_id, "question": "What renewal notice period is described?"},
    )
    assert ask.status_code == 200, ask.text
    ask_payload = ask.json()
    assert ask_payload["answer"]
    assert ask_payload["confidence"] >= 0.6
    assert len(ask_payload["evidence"]) >= 1
