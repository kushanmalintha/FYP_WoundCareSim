# app/agents/agent_base.py
from abc import ABC, abstractmethod
from typing import Dict, Any
from app.utils.schema import EvaluatorOutput

class AgentBase(ABC):
    """
    Base class for agents. Each agent must implement async evaluate(context)
    where context is a dict containing keys like:
      - scenario_id
      - step
      - transcript (str)
      - actions (list/dict)
      - student_id
      - rag_context (optional)
    """

    name: str = "base"

    def __init__(self):
        pass

    @abstractmethod
    async def evaluate(self, context: Dict[str, Any]) -> EvaluatorOutput:
        """
        Evaluate the provided context and return an EvaluatorOutput pydantic model.
        """
        raise NotImplementedError()
