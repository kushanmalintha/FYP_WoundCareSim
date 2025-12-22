import json
from pathlib import Path

from app.utils.firebase_client import create_scenario_metadata

BASE_DIR = Path(__file__).resolve().parent.parent

def upload_scenario(json_path: Path):
    with open(json_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    scenario_id = payload["scenario_id"]
    create_scenario_metadata(scenario_id, payload)

    print(f"Scenario '{scenario_id}' uploaded successfully.")


if __name__ == "__main__":
    json_file = BASE_DIR / "data" / "scenario_test_001.json"
    upload_scenario(json_file)
