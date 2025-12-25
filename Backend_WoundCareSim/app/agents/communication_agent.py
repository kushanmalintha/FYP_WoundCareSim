import json
import re

from pydantic import ValidationError
from app.agents.agent_base import BaseAgent
from app.utils.schema import EvaluatorResponse

class CommunicationAgent(BaseAgent):
    """
    Evaluates student communication and returns a structured EvaluatorResponse.
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
        
        # 1. Update Prompt to FORCE JSON output matching your Schema
        system_prompt = (
            "You are a nursing communication evaluator.\n"
            "Your task is to evaluate ONLY the student's communication skills.\n"
            "You MUST respond with valid JSON matching this structure:\n"
            "{\n"
            '  "agent_name": "CommunicationAgent",\n'
            '  "step": "Current Step Name",\n'
            '  "strengths": ["List of strengths..."],\n'
            '  "issues_detected": ["List of issues..."],\n'
            '  "explanation": "Detailed reasoning...",\n'
            '  "verdict": "Appropriate" | "Partially Appropriate" | "Inappropriate",\n'
            '  "confidence": 0.0 to 1.0\n'
            "}\n\n"
            "Rules:\n"
            "- Do NOT include markdown formatting like ```json ... ```\n"
            "- Output RAW JSON only.\n"
        )

        user_prompt = (
            f"CURRENT PROCEDURE STEP: {current_step}\n"
            f"STUDENT INPUT: {student_input}\n"
            f"SCENARIO CONTEXT: {scenario_metadata.get('patient_history', 'N/A')}\n"
            f"RAG CONTEXT: {rag_response}\n"
        )

        # 2. Get Raw Text from LLM
        raw_response = await self.run(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.2,
        )

        # 3. Parse and Validate
        try:
            # Clean up potential markdown code blocks (common LLM habit)
            clean_json = raw_response.replace("```json", "").replace("```", "").strip()
            
            # Parse JSON string to Dictionary
            response_data = json.loads(clean_json)
            
            # Ensure 'step' and 'agent_name' are set correctly if LLM hallucinates them
            response_data["step"] = current_step
            response_data["agent_name"] = "CommunicationAgent"

            # Validate against Pydantic Schema
            structured_output = EvaluatorResponse(**response_data)
            
            return structured_output

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
