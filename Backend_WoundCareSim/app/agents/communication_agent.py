# app/agents/communication_agent.py
from typing import Dict, Any
from app.agents.agent_base import AgentBase
from app.utils.schema import EvaluatorOutput
import math

class CommunicationAgent(AgentBase):
    name = "communication"

    def __init__(self):
        super().__init__()

    async def evaluate(self, context: Dict[str, Any]) -> EvaluatorOutput:
        """
        Dummy evaluator:
        - uses transcript length and simple keyword checks to produce a score.
        - In Phase 3+, replace this with an LLM call with a communication-focused system prompt.
        """
        step = context.get("step", "unknown")
        transcript = (context.get("transcript") or "").strip()
        actions = context.get("actions", [])

        # Basic heuristics for Week-2 (deterministic and explainable)
        length = len(transcript)
        has_greeting = any(word in transcript.lower() for word in ["hello", "hi", "good morning", "good afternoon"])
        has_closing = any(word in transcript.lower() for word in ["thank you", "thanks", "goodbye", "bye"])
        asks_consent = "consent" in transcript.lower() or "may i" in transcript.lower() or "can i" in transcript.lower()

        # Score components (0..1)
        length_score = max(0.0, min(1.0, math.log1p(length) / 5.0))  # gentle scale
        greeting_score = 1.0 if has_greeting else 0.5
        closing_score = 1.0 if has_closing else 0.5
        consent_score = 1.0 if asks_consent else 0.0

        # Weighted aggregation
        score = (0.25 * length_score) + (0.25 * greeting_score) + (0.25 * consent_score) + (0.25 * closing_score)
        score = max(0.0, min(1.0, score))

        rationale = (
            f"Transcript length {length} (length_score={length_score:.2f}); "
            f"greeting={'yes' if has_greeting else 'no'}; closing={'yes' if has_closing else 'no'}; "
            f"consent={'yes' if asks_consent else 'no'}."
        )

        suggested = []
        if not has_greeting:
            suggested.append("Begin with a brief greeting to establish rapport.")
        if not asks_consent:
            suggested.append("Ask for consent before physical assessment or touching.")
        if not has_closing:
            suggested.append("Close the encounter with a summary and thanks.")

        evidence_refs = []
        # In future, insert RAG references like guideline IDs, e.g. "guideline:consent_01"

        return EvaluatorOutput(
            agent=self.name,
            step=step,
            score=round(float(score), 3),
            rationale=rationale,
            confidence=round(0.6 + 0.4 * score, 3),  # simple confidence heuristic
            evidence_refs=evidence_refs,
            suggested_actions=suggested,
            raw={
                "length": length,
                "has_greeting": has_greeting,
                "has_closing": has_closing,
                "asks_consent": asks_consent,
            }
        )
