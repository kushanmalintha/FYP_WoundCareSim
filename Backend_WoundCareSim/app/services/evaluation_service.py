from typing import Dict, List, Any, Optional
from app.services.scenario_loader import load_scenario
from app.rag.retriever import retrieve_with_rag
from app.core.coordinator import Coordinator
from app.services.session_manager import SessionManager
from app.utils.mcq_evaluator import MCQEvaluator
from app.utils.schema import EvaluatorResponse


class EvaluationService:
    def __init__(
        self,
        coordinator: Coordinator,
        session_manager: SessionManager
    ):
        self.coordinator = coordinator
        self.session_manager = session_manager
        self.mcq_evaluator = MCQEvaluator()

    async def prepare_agent_context(
        self,
        transcript: str,
        scenario_id: str,
        step: str
    ) -> Dict[str, Any]:

        scenario_metadata = load_scenario(scenario_id)

        rag = await retrieve_with_rag(
            query=transcript,
            scenario_id=scenario_id
        )

        return {
            "transcript": transcript,
            "step": step,
            "scenario_metadata": scenario_metadata,
            "rag_context": rag["text"]
        }

    async def aggregate_evaluations(
        self,
        session_id: str,
        evaluator_outputs: List[EvaluatorResponse],
        student_mcq_answers: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:

        session = self.session_manager.get_session(session_id)
        step = session["current_step"]

        coordinator_output = self.coordinator.aggregate(
            evaluations=evaluator_outputs,
            current_step=step
        )

        if step == "ASSESSMENT" and student_mcq_answers:
            scenario_meta = load_scenario(session["scenario_id"])
            mcq_result = self.mcq_evaluator.validate_mcq_answers(
                student_mcq_answers,
                scenario_meta.get("assessment_questions", {})
            )
            coordinator_output["mcq_result"] = mcq_result

        self.session_manager.store_last_evaluation(
            session_id, coordinator_output
        )

        return coordinator_output
    
    def determine_input_type(self, payload: Dict[str, Any]) -> str:
        if "action_type" in payload:
            return "ACTION"
        return "TEXT"
    

    
    