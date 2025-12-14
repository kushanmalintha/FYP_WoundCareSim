# app/services/scenario_service.py

from typing import Dict, List
from datetime import datetime
from app.utils.firebase_client import (
    get_document,
    set_document,
    update_document,
    delete_document,
    get_collection
)
from app.utils.validators import validate_scenario_payload

COLLECTION = "scenarios"


def create_scenario(data: Dict):
    validate_scenario_payload(data)
    data["created_at"] = datetime.utcnow().isoformat()
    set_document(COLLECTION, data["scenario_id"], data)
    return data


def update_scenario(scenario_id: str, data: Dict):
    update_document(COLLECTION, scenario_id, data)
    return get_scenario(scenario_id)


def delete_scenario(scenario_id: str):
    delete_document(COLLECTION, scenario_id)
    return {"deleted": scenario_id}


def get_scenario(scenario_id: str) -> Dict:
    scenario = get_document(COLLECTION, scenario_id)
    if not scenario:
        raise ValueError("Scenario not found")
    return scenario


def list_scenarios() -> List[Dict]:
    return get_collection(COLLECTION)
