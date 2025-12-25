from typing import List, Dict
from app.utils.schema import EvaluatorResponse


# ---- Verdict → Base score mapping ----
VERDICT_SCORE_MAP = {
    "Appropriate": 1.0,
    "Partially Appropriate": 0.6,
    "Inappropriate": 0.0,
}


# ---- Step-wise agent importance ----
STEP_WEIGHTS = {
    "HISTORY": {
        "CommunicationAgent": 0.5,
        "KnowledgeAgent": 0.4,
        "ClinicalAgent": 0.1,
    },
    "ASSESSMENT": {
        "CommunicationAgent": 0.3,
        "KnowledgeAgent": 0.7,
        "ClinicalAgent": 0.0,
    },
    "CLEANING": {
        "CommunicationAgent": 0.1,
        "KnowledgeAgent": 0.1,
        "ClinicalAgent": 0.8,
    },
    "DRESSING": {
        "CommunicationAgent": 0.1,
        "KnowledgeAgent": 0.1,
        "ClinicalAgent": 0.8,
    },
}


# ---- Step readiness thresholds ----
STEP_THRESHOLD = {
    "HISTORY": 0.6,
    "ASSESSMENT": 0.6,
    "CLEANING": 0.7,
    "DRESSING": 0.7,
}


def score_single_evaluation(ev: EvaluatorResponse) -> float:
    """
    Convert one evaluator output into a numeric score.
    """
    base_score = VERDICT_SCORE_MAP.get(ev.verdict, 0.0)
    return base_score * ev.confidence


def aggregate_scores(
    evaluations: List[EvaluatorResponse],
    current_step: str
) -> Dict[str, float]:
    """
    Compute per-agent and composite scores.
    """
    weights = STEP_WEIGHTS.get(current_step, {})
    agent_scores = {}
    composite_score = 0.0

    for ev in evaluations:
        score = score_single_evaluation(ev)
        agent_scores[ev.agent_name] = score

        weight = weights.get(ev.agent_name, 0.0)
        composite_score += score * weight

    return {
        "agent_scores": agent_scores,
        "composite_score": round(composite_score, 3),
    }


def check_readiness(
    evaluations: List[EvaluatorResponse],
    current_step: str,
    composite_score: float
) -> Dict[str, object]:
    """
    Decide whether the system can safely move to the next step.
    """

    blocking_issues = []

    # Safety-first rule: any Inappropriate verdict blocks in clinical steps
    for ev in evaluations:
        if ev.verdict == "Inappropriate":
            if current_step in {"CLEANING", "DRESSING"} and ev.agent_name == "ClinicalAgent":
                blocking_issues.append(
                    f"Critical clinical issue detected by {ev.agent_name}"
                )

    threshold = STEP_THRESHOLD.get(current_step, 1.0)

    ready = composite_score >= threshold and not blocking_issues

    return {
        "ready_for_next_step": ready,
        "blocking_issues": blocking_issues,
        "threshold": threshold,
    }
