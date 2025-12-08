# app/agents/clinical_agent.py
from typing import Dict, Any, List
from app.agents.agent_base import AgentBase
from app.utils.schema import EvaluatorOutput

class ClinicalAgent(AgentBase):
    name = "clinical"

    def __init__(self):
        super().__init__()

    async def evaluate(self, context: Dict[str, Any]) -> EvaluatorOutput:
        """
        Dummy clinical evaluator:
        - Accepts `actions` list describing tool usage and sequence.
        - Example actions format:
            [
              {"time": 12345, "action": "wash_hands"},
              {"time": 12346, "action": "don_gloves"},
              {"time": 12350, "action": "clean_wound"}
            ]
        - Checks presence/sequence of key actions (hand hygiene -> gloves -> wound cleaning -> dressing)
        """
        step = context.get("step", "unknown")
        actions: List[Dict[str, Any]] = context.get("actions", [])

        action_names = [a.get("action", "") for a in actions]
        required_sequence = ["wash_hands", "don_gloves", "clean_wound", "apply_dressing"]

        # Check presence
        present = {act: (act in action_names) for act in required_sequence}
        # Check order: find indices, ensure increasing
        idxs = []
        for act in required_sequence:
            try:
                idxs.append(action_names.index(act))
            except ValueError:
                idxs.append(None)

        order_ok = True
        # if any missing -> order incorrect
        if any(i is None for i in idxs):
            order_ok = False
        else:
            for earlier, later in zip(idxs, idxs[1:]):
                if earlier >= later:
                    order_ok = False
                    break

        # compute simple score
        presence_score = sum(1 for v in present.values() if v) / len(required_sequence)
        order_score = 1.0 if order_ok else 0.0

        # weight: presence 0.6, order 0.4
        score = 0.6 * presence_score + 0.4 * order_score

        rationale = f"Action presence: {present}. order_ok={order_ok}."
        suggested = []
        if not present["wash_hands"]:
            suggested.append("Perform hand hygiene before procedure.")
        if not present["don_gloves"]:
            suggested.append("Don sterile gloves before touching the wound.")
        if not order_ok:
            suggested.append("Follow aseptic sequence: hand hygiene -> gloves -> cleaning -> dressing.")

        evidence_refs = []
        return EvaluatorOutput(
            agent=self.name,
            step=step,
            score=round(float(score), 3),
            rationale=rationale,
            confidence=round(0.7 + 0.3 * score, 3),
            evidence_refs=evidence_refs,
            suggested_actions=suggested,
            raw={
                "action_names": action_names,
                "presence": present,
                "idxs": idxs,
                "order_ok": order_ok
            }
        )
