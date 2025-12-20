"""
Evaluator output format (informal specification).
This file contains helpers and dataclasses if needed later.
"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class EvidenceRef(BaseModel):
    doc_id: str
    chunk_index: Optional[int] = None
    excerpt: Optional[str] = None

class EvaluatorOutput(BaseModel):
    agent: str
    step: str
    score: float
    rationale: str
    confidence: float
    evidence_refs: List[EvidenceRef] = []
    suggested_actions: List[str] = []
    raw: Dict[str, Any] = {}

class EvaluatorResponse(BaseModel):
    """
    Strict structured output for all evaluator agents
    """

    agent_name: str = Field(..., description="Name of evaluator agent")
    step: str = Field(..., description="Current procedure step")

    strengths: List[str] = Field(
        ..., description="What the student did correctly"
    )

    issues_detected: List[str] = Field(
        ..., description="Problems or mistakes identified"
    )

    missed_points: List[str] = Field(
        ..., description="Expected actions or knowledge not demonstrated"
    )

    explanation: str = Field(
        ..., description="Concise reasoning tied to scenario & guidelines"
    )

    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Evaluator confidence (0–1)"
    )

    references: List[str] = Field(
        default_factory=list,
        description="Scenario or RAG references used"
    )
