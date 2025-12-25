import json

from pydantic_core import ValidationError
from app.agents.agent_base import BaseAgent
from app.utils.schema import EvaluatorResponse

class ClinicalAgent(BaseAgent):
    """
    Evaluates the student's clinical and procedural correctness.
    Focuses on cleaning and dressing steps, with minimal involvement elsewhere.
    """

    def __init__(self):
        super().__init__()

    async def evaluate(
        self,
        current_step: str,
        student_input: str,
        scenario_metadata: dict,
        rag_response: str,
    ) -> EvaluatorResponse:
        """
        Evaluate clinical correctness and return a structured object.
        """

        system_prompt = (
            "You are a nursing clinical skills evaluator.\n"
            "Your role is to evaluate ONLY clinical and procedural correctness.\n\n"
            "You MUST respond with valid JSON matching this structure:\n"
            "{\n"
            '  "agent_name": "ClinicalAgent",\n'
            '  "step": "Current Step Name",\n'
            '  "strengths": ["List of correctly performed clinical actions..."],\n'
            '  "issues_detected": ["List of clinical errors or unsafe actions..."],\n'
            '  "explanation": "Detailed clinical reasoning prioritizing patient safety...",\n'
            '  "verdict": "Appropriate" | "Partially Appropriate" | "Inappropriate",\n'
            '  "confidence": 0.0 to 1.0\n'
            "}\n\n"
            "Strict Rules:\n"
            "- Output RAW JSON only. No markdown formatting.\n"
            "- Do NOT evaluate communication style.\n"
            "- Prioritize patient safety above all else.\n"
        )

        user_prompt = (
            f"CURRENT PROCEDURE STEP: {current_step}\n"
            f"STUDENT INPUT: {student_input}\n"
            f"SCENARIO CONTEXT (Wound): {scenario_metadata.get('wound_details', 'N/A')}\n"
            f"CLINICAL EXPECTATIONS:\n"
            f"- CLEANING: hand hygiene, aseptic technique, correct direction\n"
            f"- DRESSING: appropriate selection, protection, closure\n"
            f"REFERENCE GUIDELINES: {rag_response}\n"
        )

        raw_response = await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )

        try:
            clean_json = raw_response.replace("```json", "").replace("```", "").strip()
            response_data = json.loads(clean_json)
            
            # Enforce consistency
            response_data["step"] = current_step
            response_data["agent_name"] = "ClinicalAgent"

            return EvaluatorResponse(**response_data)
        # UPDATED EXCEPT BLOCK: Catch ValidationError
        except (json.JSONDecodeError, ValueError, ValidationError) as e:
            print(f"Agent Parsing Failed: {e}")
            return EvaluatorResponse(
                agent_name="CommunicationAgent",
                step=current_step,
                strengths=[],
                issues_detected=["Error parsing evaluator response"],
                explanation=f"Failed to parse LLM output. Raw: {raw_response[:50]}...",
                verdict="Inappropriate",
                confidence=0.0
            )
