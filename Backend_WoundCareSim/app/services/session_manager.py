from app.core.state_machine import Step, next_step
from typing import Optional, Dict, Any
from datetime import datetime
import secrets

from app.services.scenario_loader import load_scenario


class SessionManager:
    """
    Manages training sessions.

    Session is the runtime owner of scenario data.
    Firestore is read ONCE at session creation.
    """

    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    # ----------------------------
    # Session lifecycle
    # ----------------------------

    def create_session(
        self,
        scenario_id: str,
        student_id: str,
        scenario_metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        session_id = f"sess_{len(self.sessions) + 1}_{int(datetime.now().timestamp())}"

        if scenario_metadata is None:
            scenario_metadata = load_scenario(scenario_id)

        self.sessions[session_id] = {
            "scenario_id": scenario_id,
            "student_id": student_id,
            "session_token": secrets.token_urlsafe(24),
            "current_step": Step.HISTORY.value,
            "last_evaluation": None,
            "scenario_metadata": scenario_metadata,
            "logs": [],
            "rag_results": [],
            "action_events": [],
            "mcq_answers": {},  # NEW: Store MCQ answers for ASSESSMENT step
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        return session_id

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self.sessions.get(session_id)

    def validate_session_token(self, session_id: str, token: Optional[str]) -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False
        if not token:
            return False
        return secrets.compare_digest(session.get("session_token", ""), token)

    # ----------------------------
    # Evaluation & logging
    # ----------------------------

    def store_last_evaluation(
        self,
        session_id: str,
        evaluation: Dict[str, Any]
    ) -> None:
        session = self.sessions.get(session_id)
        if session:
            session["last_evaluation"] = evaluation
            session["updated_at"] = datetime.now().isoformat()

    def add_log(
        self,
        session_id: str,
        log: Dict[str, Any]
    ) -> None:
        session = self.sessions.get(session_id)
        if session:
            session["logs"].append(log)
            session["updated_at"] = datetime.now().isoformat()

    def add_rag_result(
        self,
        session_id: str,
        rag_result: Dict[str, Any]
    ) -> None:
        session = self.sessions.get(session_id)
        if session:
            session["rag_results"].append(rag_result)

    # ----------------------------
    # Step progression (always allowed)
    # ----------------------------

    def advance_step(self, session_id: str) -> Optional[str]:
        session = self.sessions.get(session_id)
        if not session:
            return None

        current_step = Step(session["current_step"])
        new_step = next_step(current_step)

        session["current_step"] = new_step.value
        session["updated_at"] = datetime.now().isoformat()

        return new_step.value
