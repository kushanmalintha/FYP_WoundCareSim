from typing import Dict, Any
from datetime import datetime


class ActionSchema:
    """
    Represents a VR-triggered student action.
    """

    def __init__(
        self,
        action_type: str,
        step: str,
        metadata: Dict[str, Any] | None = None
    ):
        self.action_type = action_type
        self.step = step
        self.timestamp = datetime.utcnow().isoformat()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_type": self.action_type,
            "step": self.step,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
