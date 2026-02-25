# app/services/pipeline.py
from __future__ import annotations

import os
from celery import chain
from celery import shared_task  # use shared_task for robustness
from .ocr import run as ocr_run
from .tables import run as tables_run
from .embeddings import run as emb_run
from .clauses import run as clauses_run
from .deadlines import run as deadlines_run
from .rules import run as rules_run
from .summarizer import run as summary_run
from .guidance import compose as compose_run

# IMPORTANT: names must match the strings you see in the error logs
@shared_task(name="app.services.pipeline.task_ocr")
def task_ocr(doc_id):
    return ocr_run(doc_id)

@shared_task(name="app.services.pipeline.task_tables")
def task_tables(doc_id):
    return tables_run(doc_id)

@shared_task(name="app.services.pipeline.task_emb")
def task_emb(doc_id):
    return emb_run(doc_id)

@shared_task(name="app.services.pipeline.task_clauses")
def task_clauses(doc_id):
    return clauses_run(doc_id)

@shared_task(name="app.services.pipeline.task_deadlines")
def task_deadlines(doc_id):
    return deadlines_run(doc_id)

@shared_task(name="app.services.pipeline.task_rules")
def task_rules(doc_id):
    return rules_run(doc_id)

@shared_task(name="app.services.pipeline.task_summary")
def task_summary(doc_id):
    return summary_run(doc_id)

@shared_task(name="app.services.pipeline.task_compose")
def task_compose(doc_id):
    return compose_run(doc_id)


def _run_sync(doc_id: str):
    task_ocr(doc_id)
    task_tables(doc_id)
    task_emb(doc_id)
    task_clauses(doc_id)
    task_deadlines(doc_id)
    task_rules(doc_id)
    task_summary(doc_id)
    task_compose(doc_id)
    return {"doc_id": doc_id, "mode": "sync"}


def enqueue_ingestion(doc_id: str):
    if os.getenv("PIPELINE_MODE", "async").lower() == "sync":
        return _run_sync(doc_id)

    try:
        return chain(
            task_ocr.si(doc_id),  # type: ignore
            task_tables.si(doc_id),  # type: ignore
            task_emb.si(doc_id),  # type: ignore
            task_clauses.si(doc_id),  # type: ignore
            task_deadlines.si(doc_id),  # type: ignore
            task_rules.si(doc_id),  # type: ignore
            task_summary.si(doc_id),  # type: ignore
            task_compose.si(doc_id),  # type: ignore
        ).apply_async()
    except Exception:
        return _run_sync(doc_id)
