from typing import Dict, List, Any
from app.services.scenario_loader import ScenarioLoader
from app.rag.retriever import Retriever
from app.core.coordinator import coordinate


class EvaluationService:
    """
    Orchestrates evaluation workflow:
    1. Prepares agent context (transcript, RAG, scenario metadata)
    2. Coordinates agent evaluation results
    3. Returns structured feedback for session management
    """
    
    def __init__(self, retriever: Retriever, scenario_loader: ScenarioLoader):
        self.retriever = retriever
        self.scenario_loader = scenario_loader

    async def prepare_agent_context(
        self, 
        transcript: str, 
        scenario_id: str, 
        step: str
    ) -> Dict[str, Any]:
        """
        Creates complete context package for agent evaluation.
        
        Args:
            transcript: Student's input text
            scenario_id: Firestore scenario identifier
            step: Current session step (HISTORY|ASSESSMENT|CLEANING|DRESSING)
        
        Returns:
            Context dictionary containing:
            - transcript
            - step
            - rag_chunks (from OpenAI Vector Store)
            - scenario_metadata (from Firestore)
        """
        # Load scenario metadata from Firestore
        scenario_meta = await self.scenario_loader.load_scenario(scenario_id)

        # Retrieve relevant RAG chunks based on query and step
        rag_chunks = await self.retriever.get_context(
            query=transcript,
            scenario_id=scenario_id,
            step=step
        )

        return {
            "transcript": transcript,
            "step": step,
            "rag_chunks": rag_chunks,
            "scenario_metadata": scenario_meta
        }

    async def evaluate_and_coordinate(
        self,
        agent_evaluations: List[Dict[str, Any]],
        current_step: str
    ) -> Dict[str, Any]:
        """
        Coordinates multiple agent evaluations into unified feedback.
        
        Args:
            agent_evaluations: List of evaluation outputs from agents
                Each must contain:
                - agent: str (communication|knowledge|clinical)
                - strengths: List[str]
                - issues_detected: List[str]
                - missed_points: List[str]
                - explanation: str
                - confidence: float (0.0-1.0)
            current_step: Current session step
        
        Returns:
            Coordinated evaluation result:
            - step_feedback: Aggregated strengths/issues/missed
            - overall_feedback: Human-readable summary
            - readiness_for_next_step: bool
            - aggregated_confidence: float
            - agent_contributions: Per-agent transparency data
        """
        # Validate agent evaluations structure
        validated_evals = self._validate_evaluations(agent_evaluations)
        
        # Call coordinator for aggregation
        coordinated_result = coordinate(validated_evals, current_step)
        
        return coordinated_result

    def _validate_evaluations(
        self, 
        evaluations: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Validates and normalizes agent evaluation outputs.
        Ensures required fields exist and have correct types.
        """
        validated = []
        required_fields = {
            "agent": str,
            "strengths": list,
            "issues_detected": list,
            "missed_points": list,
            "explanation": str,
            "confidence": (float, int)
        }
        
        for ev in evaluations:
            validated_ev = {}
            
            # Check all required fields
            for field, expected_type in required_fields.items():
                value = ev.get(field)
                
                # Provide defaults if missing
                if value is None:
                    if expected_type == str:
                        validated_ev[field] = ""
                    elif expected_type == list:
                        validated_ev[field] = []
                    elif expected_type == (float, int):
                        validated_ev[field] = 0.0
                    continue
                
                # Type validation
                if expected_type == (float, int):
                    validated_ev[field] = float(value)
                elif expected_type == list:
                    validated_ev[field] = list(value) if isinstance(value, list) else []
                elif expected_type == str:
                    validated_ev[field] = str(value)
                else:
                    validated_ev[field] = value
            
            # Normalize confidence to 0.0-1.0 range
            confidence = validated_ev.get("confidence", 0.0)
            validated_ev["confidence"] = max(0.0, min(1.0, confidence))
            
            validated.append(validated_ev)
        
        return validated

    async def get_step_requirements(
        self, 
        scenario_id: str, 
        step: str
    ) -> Dict[str, Any]:
        """
        Retrieves step-specific requirements for validation.
        Useful for agents to understand what to evaluate.
        
        Args:
            scenario_id: Firestore scenario identifier
            step: Current step
        
        Returns:
            Step requirements including:
            - required_topics: List of topics to cover
            - prohibited_actions: Things to avoid
            - key_procedures: Clinical procedures expected
        """
        scenario_meta = await self.scenario_loader.load_scenario(scenario_id)
        
        # Extract step-specific requirements from scenario metadata
        step_requirements = scenario_meta.get("step_requirements", {}).get(step, {})
        
        return {
            "required_topics": step_requirements.get("required_topics", []),
            "prohibited_actions": step_requirements.get("prohibited_actions", []),
            "key_procedures": step_requirements.get("key_procedures", []),
            "step": step
        }

    def get_step_weights(self, step: str) -> Dict[str, float]:
        """
        Retrieves agent weighting for a specific step.
        Useful for understanding evaluation priorities.
        
        Args:
            step: Session step
        
        Returns:
            Agent weight dictionary
        """
        from app.core.coordinator import STEP_WEIGHTS
        return STEP_WEIGHTS.get(step, STEP_WEIGHTS["HISTORY"])

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