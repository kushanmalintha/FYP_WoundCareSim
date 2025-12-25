from typing import List, Dict, Any
from app.utils.schema import EvaluatorResponse
from app.utils.scoring import aggregate_scores, check_readiness


class Coordinator:
    def aggregate(
        self,
        evaluations: List[EvaluatorResponse],
        current_step: str
    ) -> Dict[str, Any]:

        if not evaluations:
            return {
                "step": current_step,
                "summary": {},
                "agent_feedback": {},
                "notes": "No evaluator outputs received",
                "decision": {
                    "ready_for_next_step": False,
                    "reason": "No evaluations available"
                }
            }

        agent_feedback = {}
        all_strengths = []
        all_issues = []
        explanations = []

        for ev in evaluations:
            agent_feedback[ev.agent_name] = {
                "strengths": ev.strengths,
                "issues_detected": ev.issues_detected,
                "explanation": ev.explanation,
                "verdict": ev.verdict,
                "confidence": ev.confidence,
            }

            all_strengths.extend(
                [f"[{ev.agent_name}] {s}" for s in ev.strengths]
            )
            all_issues.extend(
                [f"[{ev.agent_name}] {i}" for i in ev.issues_detected]
            )
            explanations.append(
                f"[{ev.agent_name}] {ev.explanation}"
            )

        score_result = aggregate_scores(evaluations, current_step)
        readiness_result = check_readiness(
            evaluations,
            current_step,
            score_result["composite_score"]
        )

        # ---- Final response ----
        return {
            "step": current_step,
            "summary": {
                "strengths": all_strengths,
                "issues_detected": all_issues,
            },
            "agent_feedback": agent_feedback,
            "combined_explanation": " ".join(explanations),
            "scores": score_result,
            "decision": readiness_result,
        }
