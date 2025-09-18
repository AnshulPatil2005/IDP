from pydantic import BaseModel, Field
from typing import List

class GuidanceItemOut(BaseModel):
    id: str
    doc_id: str
    title: str
    what_it_means: str
    action: str | None = None
    risk: str = "low"
    deadline: str | None = None
    evidence: List[str] = []
    confidence: float = Field(ge=0, le=1)
    policy_rule: str | None = None
