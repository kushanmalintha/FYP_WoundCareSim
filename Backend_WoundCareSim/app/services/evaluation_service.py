<<<<<<< HEAD
from typing import Dict, List, Any
from app.services.scenario_loader import ScenarioLoader
from app.rag.retriever import Retriever
from app.core.coordinator import coordinate
from app.services.session_manager import SessionManager
=======
from typing import Dict, Any, List

from app.services.scenario_loader import load_scenario
from app.rag.retriever import retrieve_with_rag
from app.core.coordinator import Coordinator
from app.utils.schema import EvaluatorResponse
>>>>>>> c82b935883eba8052e3a6572ae3e443e7a7f9ade


class EvaluationService:
    """
    Week-4 Evaluation Service

    Responsibilities:
    - Load scenario metadata
    - Retrieve RAG context
    - Prepare agent context
    - Aggregate evaluator outputs (schema-driven)
    """
<<<<<<< HEAD
    
    def __init__(
        self,
        retriever: Retriever,
        scenario_loader: ScenarioLoader,
        session_manager: SessionManager
    ):
        self.retriever = retriever
        self.scenario_loader = scenario_loader
        self.session_manager = session_manager
=======

    def __init__(self, coordinator: Coordinator):
        self.coordinator = coordinator
>>>>>>> c82b935883eba8052e3a6572ae3e443e7a7f9ade

    async def prepare_agent_context(
        self,
        transcript: str,
        scenario_id: str,
        step: str,
        system_instruction: str = ""
    ) -> Dict[str, Any]:
        """
        Prepares the full context passed to evaluator agents.
        """

        # Load scenario (sync)
        scenario_metadata = load_scenario(scenario_id)

        # Retrieve RAG context (async)
        rag_result = await retrieve_with_rag(
            query=transcript,
            scenario_id=scenario_id,
            system_instruction=system_instruction
        )

        return {
            "transcript": transcript,
            "step": step,
            "scenario_metadata": scenario_metadata,
            "rag_context": rag_result["text"],
            "rag_raw": rag_result["raw_response"],
        }

    async def aggregate_evaluations(
        self,
        evaluator_outputs: List[EvaluatorResponse],
        step: str
    ) -> Dict[str, Any]:
        """
        Aggregates evaluator agent outputs using the coordinator.

        NOTE:
        - evaluator_outputs MUST already be schema-validated
        """

<<<<<<< HEAD
    def get_readiness_threshold(self, step: str) -> float:
        """
        Retrieves progression threshold for a step.
        
        Args:
            step: Session step
        
        Returns:
            Confidence threshold (0.0-1.0)
        """
        from app.core.coordinator import READINESS_THRESHOLDS
        return READINESS_THRESHOLDS.get(step, 0.6)

    async def process_step_result(
        self,
        session_id: str,
        coordinator_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Gatekeeper logic for session progression.
        """

        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError("Session not found")

        # Store last evaluation
        self.session_manager.store_last_evaluation(
            session_id, coordinator_output
        )

        # 🚫 Lock if unsafe
        if coordinator_output.get("blocking_issues"):
            self.session_manager.lock_current_step(session_id)
            return {
                "status": "LOCKED",
                "current_step": session["current_step"],
                "reason": "Critical safety issue detected",
                "feedback": coordinator_output
            }

        # ❌ Not ready → retry
        if not coordinator_output.get("ready_for_next_step", False):
            self.session_manager.increment_attempt(session_id)
            return {
                "status": "RETRY",
                "current_step": session["current_step"],
                "retry_guidance": coordinator_output.get("retry_guidance", ""),
                "feedback": coordinator_output
            }

        # ✅ Ready → advance
        next_step = self.session_manager.advance_step(session_id)
        self.session_manager.reset_attempts(session_id)

        return {
            "status": "ADVANCED",
            "previous_step": session["current_step"],
            "current_step": next_step,
            "feedback": coordinator_output
        }
 
=======
        if not evaluator_outputs:
            raise ValueError("No evaluator outputs provided")

        if not all(isinstance(ev, EvaluatorResponse) for ev in evaluator_outputs):
            raise TypeError("All evaluator outputs must be EvaluatorResponse instances")

        return self.coordinator.aggregate(
            evaluations=evaluator_outputs,
            current_step=step
        )
>>>>>>> c82b935883eba8052e3a6572ae3e443e7a7f9ade
