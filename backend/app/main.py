import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db import engine, Base
from .routes import ingest as r_ingest, clauses as r_clauses, guidance as r_guidance, deadlines as r_deadlines, ask as r_ask, rules as r_rules

app = FastAPI(title="Titan-Guidance API", version="0.1.0")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auto-create tables for dev (use Alembic later)
Base.metadata.create_all(bind=engine)

app.include_router(r_ingest.router)
app.include_router(r_clauses.router)
app.include_router(r_guidance.router)
app.include_router(r_deadlines.router)
app.include_router(r_ask.router)
app.include_router(r_rules.router)

@app.get("/")
def health():
    return {"ok": True}
