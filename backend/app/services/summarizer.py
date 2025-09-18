from sqlalchemy.orm import Session
from ..db import SessionLocal
from ..models import Guidance, Clause

def run(doc_id: str):
    db: Session = SessionLocal()
    try:
        cls = db.query(Clause).filter(Clause.doc_id==doc_id).all()
        bullets = []
        for c in cls[:8]:
            chip = f"{doc_id}:{c.page}:{c.start}-{c.end}"
            bullets.append(f"- {c.type.replace('_',' ')}: see [{chip}]")
        text = "Key terms:\n" + "\n".join(bullets) if bullets else "Unknown."
        g = Guidance(doc_id=doc_id, title="Evidence-cited summary",
                     what=text, action="Review flagged items.", risk="medium",
                     deadline=None, evidence=[f"{doc_id}:{cls[0].page}:{cls[0].start}-{cls[0].end}"] if cls else [],
                     confidence=0.8)
        db.query(Guidance).filter(Guidance.doc_id==doc_id, Guidance.title=="Evidence-cited summary").delete()
        db.add(g); db.commit()
        return {"summary": True}
    finally:
        db.close()
