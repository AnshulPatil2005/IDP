from pydantic import BaseModel, Field

class TextSpan(BaseModel):
    doc_id: str
    page: int
    start: int
    end: int

Risk = str  # "low" | "medium" | "high" | "critical" – keep loose for now
