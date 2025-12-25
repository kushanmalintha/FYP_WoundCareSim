from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from app.services.session_manager import SessionManager
from app.services.scenario_loader import load_scenario
from app.services.evaluation_service import EvaluationService
from app.core.coordinator import Coordinator
from app.core.state_machine import Step, next_step
from app.utils.schema import EvaluatorResponse
from app.rag.retriever import retrieve_with_rag


router = APIRouter(prefix="/session", tags=["Session"])

# Core services
session_manager = SessionManager()
coordinator = Coordinator()
evaluation_service = EvaluationService(coordinator=coordinator)


# ----------------------------
# Request models
# ----------------------------

class StartSessionRequest(BaseModel):
    scenario_id: str
    student_id: str


class EvalInput(BaseModel):
    session_id: str
    step: str
    user_input: Optional[str] = None
    evaluator_outputs: List[EvaluatorResponse]


# ----------------------------
# Routes
# ----------------------------

@router.post("/start")
def start_session(req: StartSessionRequest):
    try:
        scenario = load_scenario(req.scenario_id)

        session_id = session_manager.create_session(
            scenario_id=req.scenario_id,
            student_id=req.student_id,
            scenario_metadata=scenario
        )

        return {
            "session_id": session_id,
            "current_step": Step.HISTORY.value,
            "scenario_summary": {
                "scenario_id": scenario["scenario_id"],
                "title": scenario["title"],
                "patient_history": scenario["patient_history"],
                "wound_details": scenario["wound_details"],
            },
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/step")
async def session_step(payload: EvalInput):
    sid = payload.session_id
    session = session_manager.get_session(sid)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    cur_step = session["current_step"]
    scenario_id = session["scenario_id"]

    rag_result = None

    # ----------------------------
    # Optional RAG retrieval
    # ----------------------------
    if payload.user_input:
        try:
            rag_result = await retrieve_with_rag(
                query=payload.user_input,
                scenario_id=scenario_id,
                system_instruction=(
                    f"You are assisting in step '{cur_step}' "
                    "of a surgically clean wound care procedure."
                ),
            )

            session_manager.add_rag_result(
                sid,
                {
                    "step": cur_step,
                    "query": payload.user_input,
                    "llm_output": rag_result["text"],
                },
            )

        except Exception as e:
            print(f"RAG retrieval failed: {str(e)}")

    # ----------------------------
    # Evaluation aggregation (Week-4)
    # ----------------------------
    try:
        evaluation = await evaluation_service.aggregate_evaluations(
            evaluator_outputs=payload.evaluator_outputs,
            step=cur_step,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Evaluation aggregation failed: {str(e)}",
        )

    # ----------------------------
    # Session logging
    # ----------------------------
    session_manager.add_log(
        sid,
        {
            "step": cur_step,
            "user_input": payload.user_input,
            "evaluation": evaluation,
            "rag_used": rag_result is not None,
        },
    )

    # ----------------------------
    # Step transition
    # ----------------------------
    next_s = None
    try:
        next_s = next_step(Step(cur_step))
        session["current_step"] = next_s.value
    except Exception:
        pass

    # ----------------------------
    # Response
    # ----------------------------
    response = {
        "session_id": sid,
        "current_step": cur_step,
        "evaluation": evaluation,
    }

    if rag_result:
        response["assistant_response"] = rag_result["text"]

    if next_s:
        response["next_step"] = next_s.value

    return response
