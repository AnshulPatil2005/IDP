from pydantic import BaseModel, Field
from typing import List
from .common import TextSpan

class AskRequest(BaseModel):
    doc_id: str
    question: str

class AskAnswer(BaseModel):
    answer: str
    confidence: float
    evidence: List[TextSpan]
    quotes: List[str]
