from typing import Dict, List, Any, Optional
from app.services.scenario_loader import ScenarioLoader, load_scenario
from app.rag.retriever import Retriever, retrieve_with_rag
from app.core.coordinator import coordinate, READINESS_THRESHOLDS
from app.services.session_manager import SessionManager
from app.utils.mcq_evaluator import MCQEvaluator
from app.schemas.evaluator_response import EvaluatorResponse


class EvaluationService:
    """
    Week-5 Enhanced Evaluation Service

    Responsibilities:
    - Load scenario metadata
    - Retrieve RAG context
    - Prepare agent context
    - Aggregate evaluator outputs (schema-driven)
    - Validate MCQ answers (Assessment step)
    - Format VR-friendly responses
    - Control session progression (gatekeeper)
    """
    
    def __init__(
        self,
        retriever: Retriever,
        scenario_loader: ScenarioLoader,
        session_manager: SessionManager
    ):
        self.retriever = retriever
        self.scenario_loader = scenario_loader
        self.session_manager = session_manager
        self.mcq_evaluator = MCQEvaluator()

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
        step: str,
        student_mcq_answers: Optional[Dict[str, str]] = None,
        scenario_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Aggregates evaluator agent outputs using the coordinator.
        Includes MCQ validation for Assessment step.

        Args:
            evaluator_outputs: Schema-validated evaluator responses
            step: Current session step
            student_mcq_answers: Optional MCQ answers for Assessment
            scenario_id: Required if MCQ validation needed

        Returns:
            Coordinated result with scores, readiness, and VR-formatted output
        """
        # Convert schema objects to dicts for coordinator
        evaluator_dicts = [self._evaluator_to_dict(ev) for ev in evaluator_outputs]
        
        # Handle MCQ validation for Assessment step
        mcq_result = None
        if step == "ASSESSMENT" and student_mcq_answers and scenario_id:
            mcq_result = await self._validate_mcq_step(
                student_mcq_answers,
                scenario_id,
                evaluator_dicts
            )
        
        # Call coordinator for aggregation
        coordinated_result = coordinate(evaluator_dicts, step)
        
        # Format for VR consumption
        vr_response = self._format_for_vr(
            coordinated_result,
            step,
            mcq_result
        )
        
        return vr_response

    async def _validate_mcq_step(
        self,
        student_answers: Dict[str, str],
        scenario_id: str,
        evaluator_dicts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Validates MCQ answers and adjusts Knowledge Agent score.
        
        Args:
            student_answers: Student's MCQ responses
            scenario_id: Scenario identifier
            evaluator_dicts: List of evaluator dictionaries
        
        Returns:
            MCQ validation result with contribution to Knowledge score
        """
        # Load scenario metadata for MCQ answers
        scenario_meta = load_scenario(scenario_id)
        mcq_data = scenario_meta.get("assessment_mcqs", {})
        
        # Validate MCQ answers
        mcq_result = self.mcq_evaluator.validate_mcq_answers(
            student_answers,
            mcq_data
        )
        
        # Compute MCQ contribution to Knowledge Agent
        mcq_contribution = self.mcq_evaluator.compute_mcq_contribution(
            mcq_result["score"]
        )
        
        # Find Knowledge Agent evaluation and enhance it
        for eval_data in evaluator_dicts:
            if eval_data.get("agent") == "knowledge":
                # Add MCQ info to Knowledge Agent metadata
                eval_data["mcq_score"] = mcq_result["score"]
                eval_data["mcq_contribution"] = mcq_contribution
                
                # Boost or reduce confidence based on MCQ performance
                original_confidence = eval_data.get("confidence", 0.5)
                eval_data["confidence"] = (
                    original_confidence * 0.6 + mcq_result["score"] * 0.4
                )
                
                # Add MCQ feedback to explanation
                mcq_summary = self.mcq_evaluator.get_mcq_summary(mcq_result)
                eval_data["explanation"] = (
                    f"{eval_data['explanation']} "
                    f"MCQ Performance: {mcq_summary}"
                )
                break
        
        return mcq_result

    def _evaluator_to_dict(self, evaluator: EvaluatorResponse) -> Dict[str, Any]:
        """
        Converts EvaluatorResponse schema to dictionary for coordinator.
        
        Args:
            evaluator: Schema-validated evaluator response
        
        Returns:
            Dictionary representation
        """
        return {
            "agent": evaluator.agent,
            "verdict": evaluator.verdict,
            "confidence": evaluator.confidence,
            "strengths": evaluator.strengths,
            "issues_detected": evaluator.issues_detected,
            "missed_points": evaluator.missed_points,
            "explanation": evaluator.explanation
        }

    def _format_for_vr(
        self,
        coordinated_result: Dict[str, Any],
        current_step: str,
        mcq_result: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Formats evaluation results for VR consumption.
        Creates clean, structured payload ready for Unity.
        
        Args:
            coordinated_result: Output from coordinator
            current_step: Current session step
            mcq_result: Optional MCQ validation results
        
        Returns:
            VR-friendly response structure
        """
        # Extract key data from coordinated result
        step_feedback = coordinated_result.get("step_feedback", {})
        readiness = coordinated_result.get("ready_for_next_step", False)
        scores = coordinated_result.get("scores", {})
        blocking_issues = coordinated_result.get("blocking_issues", [])
        retry_guidance = coordinated_result.get("retry_guidance", "")
        
        # Build VR response
        vr_response = {
            "step": current_step,
            "readiness": {
                "ready_for_next_step": readiness,
                "blocking_issues": blocking_issues,
                "retry_instructions": retry_guidance
            },
            "scores": {
                "composite": scores.get("composite_score", 0.0),
                "communication": scores.get("communication", 0.0),
                "knowledge": scores.get("knowledge", 0.0),
                "clinical": scores.get("clinical", 0.0)
            },
            "feedback": {
                "strengths": step_feedback.get("strengths", []),
                "issues": step_feedback.get("issues_detected", []),
                "missed_points": step_feedback.get("missed_points", []),
                "overall_summary": coordinated_result.get("overall_feedback", "")
            },
            "next_expected_action": self._get_next_action(current_step, readiness),
            "agent_details": coordinated_result.get("agent_contributions", [])
        }
        
        # Add MCQ results if present
        if mcq_result:
            vr_response["mcq_results"] = {
                "score": mcq_result["score"],
                "correct": mcq_result["correct_count"],
                "total": mcq_result["total_questions"],
                "summary": self.mcq_evaluator.get_mcq_summary(mcq_result),
                "question_feedback": mcq_result["per_question_feedback"]
            }
        
        # Preserve original coordinator output for internal use
        vr_response["_internal"] = coordinated_result
        
        return vr_response

    def _get_next_action(self, current_step: str, ready: bool) -> str:
        """
        Determines next expected action for VR guidance.
        
        Args:
            current_step: Current session step
            ready: Whether student is ready to progress
        
        Returns:
            Action guidance string
        """
        if ready:
            step_progression = {
                "HISTORY": "Proceed to Assessment",
                "ASSESSMENT": "Proceed to Cleaning",
                "CLEANING": "Proceed to Dressing",
                "DRESSING": "Complete session"
            }
            return step_progression.get(current_step, "Continue")
        else:
            return f"Retry {current_step} with improvements"

    def get_readiness_threshold(self, step: str) -> float:
        """
        Retrieves progression threshold for a step.
        
        Args:
            step: Session step
        
        Returns:
            Confidence threshold (0.0-1.0)
        """
        return READINESS_THRESHOLDS.get(step, 0.6)

    async def process_step_result(
        self,
        session_id: str,
        coordinator_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Gatekeeper logic for session progression.
        Controls advancement, retry, or locking based on evaluation results.
        
        Args:
            session_id: Session identifier
            coordinator_output: VR-formatted coordinator output
        
        Returns:
            Progression decision with status and feedback
        """
        session = self.session_manager.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        # Extract internal coordinator result
        internal_result = coordinator_output.get("_internal", coordinator_output)
        
        # Store last evaluation
        self.session_manager.store_last_evaluation(
            session_id, coordinator_output
        )

        # 🚫 Lock if unsafe (critical blocking issues)
        blocking_issues = coordinator_output.get("readiness", {}).get("blocking_issues", [])
        if blocking_issues:
            self.session_manager.lock_current_step(session_id)
            return {
                "status": "LOCKED",
                "current_step": session["current_step"],
                "reason": "Critical safety issue detected",
                "blocking_issues": blocking_issues,
                "feedback": coordinator_output
            }

        # ❌ Not ready → retry
        readiness = coordinator_output.get("readiness", {})
        if not readiness.get("ready_for_next_step", False):
            self.session_manager.increment_attempt(session_id)
            attempt_count = session.get("attempt_count", {}).get(session["current_step"], 1)
            
            return {
                "status": "RETRY",
                "current_step": session["current_step"],
                "attempt_number": attempt_count,
                "retry_guidance": readiness.get("retry_instructions", ""),
                "feedback": coordinator_output
            }

        # ✅ Ready → advance
        next_step = self.session_manager.advance_step(session_id)
        self.session_manager.reset_attempts(session_id)

        return {
            "status": "ADVANCED",
            "previous_step": session["current_step"],
            "current_step": next_step,
            "feedback": coordinator_output,
            "message": f"Successfully advanced from {session['current_step']} to {next_step}"
        }

    async def evaluate_mcq_only(
        self,
        student_answers: Dict[str, str],
        scenario_id: str
    ) -> Dict[str, Any]:
        """
        Standalone MCQ evaluation endpoint.
        Useful for Assessment step-only validation.
        
        Args:
            student_answers: Student's MCQ responses
            scenario_id: Scenario identifier
        
        Returns:
            VR-formatted MCQ results
        """
        scenario_meta = load_scenario(scenario_id)
        mcq_data = scenario_meta.get("assessment_mcqs", {})
        
        mcq_result = self.mcq_evaluator.validate_mcq_answers(
            student_answers,
            mcq_data
        )
        
        return {
            "step": "ASSESSMENT",
            "mcq_results": {
                "score": mcq_result["score"],
                "correct": mcq_result["correct_count"],
                "total": mcq_result["total_questions"],
                "summary": self.mcq_evaluator.get_mcq_summary(mcq_result),
                "question_feedback": mcq_result["per_question_feedback"]
            }
        }