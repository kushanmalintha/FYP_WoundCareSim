# app/services/scenario_loader.py

from typing import Dict
from app.services.scenario_service import get_scenario
from app.utils.validators import validate_scenario_payload


def load_scenario(scenario_id: str) -> Dict:
    """
    Load and validate scenario for session usage.
    """
    scenario = get_scenario(scenario_id)

    # Validate structure
    validate_scenario_payload(scenario)

    return {
        "scenario_id": scenario["scenario_id"],
        "title": scenario["scenario_title"],
        "patient_history": scenario["patient_history"],
        "wound_details": scenario["wound_details"],
        "conversation_points": scenario.get("required_conversation_points", []),
        "assessment_questions": scenario["assessment_questions"],
        "evaluation_criteria": scenario["evaluation_criteria"],
        "vector_namespace": scenario["vector_store_namespace"]
    }
