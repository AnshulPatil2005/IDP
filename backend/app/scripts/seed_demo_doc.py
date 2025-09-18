import uuid
from datetime import datetime, timedelta
from app.db import SessionLocal, engine, Base
from app.models import Document, Clause, Deadline

def main():
    Base.metadata.create_all(bind=engine)
    doc_id = f"D{uuid.uuid4().hex[:8]}"
    db = SessionLocal()
    try:
        db.add(Document(doc_id=doc_id, title="demo.pdf", status="completed"))
        db.add(Clause(doc_id=doc_id, type="limitation_of_liability", page=1, start=10, end=30,
                      text="Liability capped at 50% of annual fees.", confidence=0.9,
                      normalized={"cap_ratio_to_annual_fees": 0.5}))
        db.add(Clause(doc_id=doc_id, type="renewal", page=1, start=100, end=130,
                      text="Auto-renews; 15 days notice.", confidence=0.85,
                      normalized={"notice_days": 15}))
        db.add(Deadline(doc_id=doc_id, title="Renewal notice window",
                        due_at=datetime.utcnow() + timedelta(days=15)))
        db.commit()
        print(doc_id)
    finally:
        db.close()

if __name__ == "__main__":
    main()
