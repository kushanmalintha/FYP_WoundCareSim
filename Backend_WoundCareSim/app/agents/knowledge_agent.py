# app/agents/knowledge_agent.py
from typing import Dict, Any
from app.agents.agent_base import AgentBase
from app.utils.schema import EvaluatorOutput

class KnowledgeAgent(AgentBase):
    name = "knowledge"

    def __init__(self):
        super().__init__()

    async def evaluate(self, context: Dict[str, Any]) -> EvaluatorOutput:
        """
        Dummy knowledge evaluator:
        - Checks for presence of critical keywords in transcript (e.g. comorbidities, allergies)
        - Validates MCQ answers if provided in context["mcq_answers"]
        - Later: will call LLM + RAG to verify clinical correctness.
        """
        step = context.get("step", "unknown")
        transcript = (context.get("transcript") or "").lower()
        mcq_answers = context.get("mcq_answers", {})  # e.g. {"q1": "B", "q2": "A"}
        expected_mcq = context.get("expected_mcq", {})  # passed by scenario loader for dummy check

        # Keyword presence checks
        keywords = ["diabetes", "hypertension", "allergy", "fever", "pain"]
        found = [k for k in keywords if k in transcript]

        # MCQ scoring (simple)
        mcq_total = len(expected_mcq)
        mcq_correct = 0
        for qid, correct in expected_mcq.items():
            ans = mcq_answers.get(qid)
            if ans is not None and str(ans).strip().lower() == str(correct).strip().lower():
                mcq_correct += 1

        mcq_score = (mcq_correct / mcq_total) if mcq_total > 0 else 0.0
        keyword_score = min(1.0, len(found) / max(1.0, len(keywords)))

        # Weighted final
        if mcq_total > 0:
            score = 0.6 * mcq_score + 0.4 * keyword_score
        else:
            score = keyword_score

        rationale = (
            f"Found keywords: {found}. MCQ correct {mcq_correct}/{mcq_total} (mcq_score={mcq_score:.2f})."
        )

        suggested = []
        if mcq_total > 0 and mcq_correct < mcq_total:
            suggested.append("Review clinical reasoning for questions marked incorrect.")
        if "allergy" not in transcript:
            suggested.append("Confirm and document allergy history explicitly.")

        evidence_refs = []
        # future: attach scenario-specific RAG docs here

        return EvaluatorOutput(
            agent=self.name,
            step=step,
            score=round(float(score), 3),
            rationale=rationale,
            confidence=round(0.65 + 0.35 * score, 3),
            evidence_refs=evidence_refs,
            suggested_actions=suggested,
            raw={
                "mcq_total": mcq_total,
                "mcq_correct": mcq_correct,
                "keywords_found": found
            }
        )
