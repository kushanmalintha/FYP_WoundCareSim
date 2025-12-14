# app/utils/validators.py

from typing import Dict, List

REQUIRED_FIELDS = [
    "scenario_id",
    "scenario_title",
    "patient_history",
    "wound_details",
    "assessment_questions",
    "evaluation_criteria",
    "vector_store_namespace"
]


def validate_scenario_payload(data: Dict):
    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    if not isinstance(data.get("assessment_questions", []), list):
        raise ValueError("assessment_questions must be a list")

    for q in data.get("assessment_questions", []):
        if "question" not in q or "answer" not in q:
            raise ValueError("Each MCQ must have question and answer")

    if not isinstance(data.get("evaluation_criteria", {}), dict):
        raise ValueError("evaluation_criteria must be a dictionary")
