from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Dict, Any
from .common import TextSpan

class ClauseTypeEnum(str, Enum):
    indemnity = "indemnity"
    limitation_of_liability = "limitation_of_liability"
    termination = "termination"
    renewal = "renewal"
    governing_law = "governing_law"
    confidentiality = "confidentiality"
    intellectual_property = "intellectual_property"
    payment = "payment"
    sla = "sla"

class ClauseOut(BaseModel):
    id: str
    doc_id: str
    type: ClauseTypeEnum
    parties: List[str] = []
    text_span: TextSpan
    text: str | None = None
    confidence: float = Field(ge=0, le=1)
    normalized: Dict[str, Any] = {}
