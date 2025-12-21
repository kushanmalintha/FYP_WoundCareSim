from typing import List, Dict, Any
from statistics import mean

# Step-aware agent weighting configuration
STEP_WEIGHTS = {
    "HISTORY": {
        "communication": 0.5,
        "knowledge": 0.4,
        "clinical": 0.1
    },
    "ASSESSMENT": {
        "communication": 0.2,
        "knowledge": 0.6,
        "clinical": 0.2
    },
    "CLEANING": {
        "communication": 0.1,
        "knowledge": 0.2,
        "clinical": 0.7
    },
    "DRESSING": {
        "communication": 0.1,
        "knowledge": 0.2,
        "clinical": 0.7
    }
}

# Readiness thresholds per step
READINESS_THRESHOLDS = {
    "HISTORY": 0.6,
    "ASSESSMENT": 0.65,
    "CLEANING": 0.7,
    "DRESSING": 0.7
}


def coordinate(evaluations: List[Dict[str, Any]], current_step: str) -> Dict[str, Any]:
    """
    Step-aware intelligent aggregation of evaluator outputs.
    
    Args:
        evaluations: List of evaluator outputs with structure:
            {
                "agent": "communication|knowledge|clinical",
                "strengths": [...],
                "issues_detected": [...],
                "missed_points": [...],
                "explanation": "...",
                "confidence": 0.0-1.0
            }
        current_step: "HISTORY"|"ASSESSMENT"|"CLEANING"|"DRESSING"
    
    Returns:
        {
            "step_feedback": {...},
            "overall_feedback": "...",
            "readiness_for_next_step": bool,
            "aggregated_confidence": float,
            "agent_contributions": {...}
        }
    """
    if not evaluations:
        return {
            "step_feedback": {},
            "overall_feedback": "No evaluations provided",
            "readiness_for_next_step": False,
            "aggregated_confidence": 0.0,
            "agent_contributions": {}
        }
    
    # Validate step
    if current_step not in STEP_WEIGHTS:
        current_step = "HISTORY"  # Default fallback
    
    # Get step-specific weights
    weights = STEP_WEIGHTS[current_step]
    threshold = READINESS_THRESHOLDS[current_step]
    
    # Organize evaluations by agent
    agent_evals = {}
    for ev in evaluations:
        agent_name = ev.get("agent", "unknown")
        agent_evals[agent_name] = ev
    
    # Calculate weighted confidence
    weighted_confidence = _calculate_weighted_confidence(agent_evals, weights)
    
    # Aggregate feedback by category
    step_feedback = _aggregate_step_feedback(agent_evals, weights)
    
    # Generate overall feedback text
    overall_feedback = _generate_overall_feedback(agent_evals, current_step, weights)
    
    # Determine readiness for next step
    readiness = _assess_readiness(
        agent_evals, 
        weighted_confidence, 
        threshold, 
        current_step
    )
    
    # Track agent contributions for transparency
    agent_contributions = _track_agent_contributions(agent_evals, weights)
    
    return {
        "step_feedback": step_feedback,
        "overall_feedback": overall_feedback,
        "readiness_for_next_step": readiness,
        "aggregated_confidence": round(weighted_confidence, 3),
        "agent_contributions": agent_contributions,
        "current_step": current_step
    }


def _calculate_weighted_confidence(
    agent_evals: Dict[str, Dict], 
    weights: Dict[str, float]
) -> float:
    """Calculate weighted average of agent confidences."""
    weighted_sum = 0.0
    total_weight = 0.0
    
    for agent_name, weight in weights.items():
        if agent_name in agent_evals:
            confidence = agent_evals[agent_name].get("confidence", 0.0)
            weighted_sum += confidence * weight
            total_weight += weight
    
    return weighted_sum / total_weight if total_weight > 0 else 0.0


def _aggregate_step_feedback(
    agent_evals: Dict[str, Dict], 
    weights: Dict[str, float]
) -> Dict[str, Any]:
    """
    Aggregate strengths, issues, and missed points across agents.
    More heavily weighted agents contribute more to the aggregation.
    """
    all_strengths = []
    all_issues = []
    all_missed = []
    
    # Sort agents by weight (descending) for prioritized aggregation
    sorted_agents = sorted(
        weights.items(), 
        key=lambda x: x[1], 
        reverse=True
    )
    
    for agent_name, weight in sorted_agents:
        if agent_name not in agent_evals:
            continue
        
        ev = agent_evals[agent_name]
        
        # Prefix with agent name for traceability
        strengths = ev.get("strengths", [])
        issues = ev.get("issues_detected", [])
        missed = ev.get("missed_points", [])
        
        # Only include if weight is significant (>10%)
        if weight > 0.1:
            all_strengths.extend([
                f"[{agent_name.title()}] {s}" for s in strengths
            ])
            all_issues.extend([
                f"[{agent_name.title()}] {i}" for i in issues
            ])
            all_missed.extend([
                f"[{agent_name.title()}] {m}" for m in missed
            ])
    
    return {
        "strengths": all_strengths,
        "issues_detected": all_issues,
        "missed_points": all_missed
    }


def _generate_overall_feedback(
    agent_evals: Dict[str, Dict], 
    current_step: str,
    weights: Dict[str, float]
) -> str:
    """
    Generate human-readable overall feedback text.
    Prioritizes explanations from more heavily weighted agents.
    """
    feedback_parts = [f"Step: {current_step}"]
    
    # Sort agents by weight for prioritized feedback
    sorted_agents = sorted(
        weights.items(), 
        key=lambda x: x[1], 
        reverse=True
    )
    
    for agent_name, weight in sorted_agents:
        if agent_name not in agent_evals:
            continue
        
        ev = agent_evals[agent_name]
        explanation = ev.get("explanation", "")
        
        if explanation and weight > 0.1:
            feedback_parts.append(
                f"{agent_name.title()} ({int(weight*100)}%): {explanation}"
            )
    
    return " | ".join(feedback_parts) if len(feedback_parts) > 1 else "No detailed feedback available"


def _assess_readiness(
    agent_evals: Dict[str, Dict],
    weighted_confidence: float,
    threshold: float,
    current_step: str
) -> bool:
    """
    Determine if student is ready to progress to next step.
    
    Logic:
    1. Weighted confidence must exceed step threshold
    2. No critical issues from high-weight agents
    3. Step-specific validation
    """
    # Base check: confidence threshold
    if weighted_confidence < threshold:
        return False
    
    # Check for critical issues from dominant agents
    critical_issues = _check_critical_issues(agent_evals, current_step)
    if critical_issues:
        return False
    
    return True


def _check_critical_issues(
    agent_evals: Dict[str, Dict],
    current_step: str
) -> bool:
    """
    Check if any high-priority agent detected critical issues.
    Critical issues prevent progression regardless of confidence.
    """
    weights = STEP_WEIGHTS[current_step]
    
    # Find the dominant agent for this step
    dominant_agent = max(weights.items(), key=lambda x: x[1])[0]
    
    if dominant_agent in agent_evals:
        ev = agent_evals[dominant_agent]
        issues = ev.get("issues_detected", [])
        
        # If dominant agent has >2 issues, consider it critical
        if len(issues) > 2:
            return True
        
        # Check for specific critical keywords
        critical_keywords = ["unsafe", "dangerous", "contraindicated", "error"]
        for issue in issues:
            if any(keyword in issue.lower() for keyword in critical_keywords):
                return True
    
    return False


def _track_agent_contributions(
    agent_evals: Dict[str, Dict],
    weights: Dict[str, float]
) -> Dict[str, Any]:
    """
    Track individual agent contributions for transparency and debugging.
    """
    contributions = {}
    
    for agent_name, weight in weights.items():
        if agent_name in agent_evals:
            ev = agent_evals[agent_name]
            contributions[agent_name] = {
                "weight": weight,
                "confidence": ev.get("confidence", 0.0),
                "strengths_count": len(ev.get("strengths", [])),
                "issues_count": len(ev.get("issues_detected", [])),
                "missed_count": len(ev.get("missed_points", []))
            }
    
    return contributions