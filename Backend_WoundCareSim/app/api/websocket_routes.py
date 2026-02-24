import base64
from typing import Any, Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from app.api.session_routes import (
    _detect_verification_request,
    _handle_verification_as_action,
    StepInput,
    _safe_tts,
    action_event_service,
    audio_service,
    clinical_agent,
    conversation_manager,
    is_action_already_performed,
    patient_agent,
    session_manager,
    run_step,
)
from app.agents.staff_nurse_agent import StaffNurseAgent
from app.core.state_machine import Step
from app.rag.retriever import retrieve_with_rag

router = APIRouter(tags=["WebSocket"])


def _extract_token(websocket: WebSocket) -> Optional[str]:
    token = websocket.query_params.get("token")
    if token:
        return token
    auth_header = websocket.headers.get("authorization")
    if auth_header and auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return websocket.headers.get("x-session-token")


async def _send_error(websocket: WebSocket, message: str) -> None:
    await websocket.send_json({"type": "error", "message": message})


async def _send_server_event(websocket: WebSocket, event: str, data: Dict[str, Any]) -> None:
    await websocket.send_json({"type": "server_event", "event": event, "data": data})


async def _send_tts_event(websocket: WebSocket, tts_payload: Optional[Dict[str, Any]], role: str) -> None:
    if not tts_payload:
        return
    audio_bytes = tts_payload.get("audio_base64")
    if not audio_bytes:
        return
    await _send_server_event(
        websocket,
        "tts_audio",
        {"audio_bytes": audio_bytes, "role": role},
    )


@router.websocket("/ws/session/{session_id}")
async def websocket_endpoint(session_id: str, websocket: WebSocket):
    await websocket.accept()

    session = session_manager.get_session(session_id)
    if not session:
        await _send_error(websocket, "Session not found")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    token = _extract_token(websocket)
    authenticated = session_manager.validate_session_token(session_id, token)

    if not authenticated:
        try:
            connect_msg = await websocket.receive_json()
        except Exception:
            await _send_error(websocket, "Authentication failed")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        if connect_msg.get("type") != "connect":
            await _send_error(websocket, "First message must be a connect payload")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        if connect_msg.get("session_id") != session_id:
            await _send_error(websocket, "Session mismatch")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

        token = connect_msg.get("auth_token")
        authenticated = session_manager.validate_session_token(session_id, token)
        if not authenticated:
            await _send_error(websocket, "Authentication failed")
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await _send_server_event(
        websocket,
        "nurse_message",
        {"text": f"Connected to session {session_id}", "session_id": session_id},
    )

    stt_buffer = bytearray()

    try:
        while True:
            message = await websocket.receive_json()
            if message.get("type") != "event":
                await _send_error(websocket, "Invalid message type")
                continue

            event = message.get("event")
            data = message.get("data") or {}

            if event == "stt_chunk":
                chunk_b64 = data.get("audio_chunk") or data.get("chunk")
                if not chunk_b64:
                    await _send_error(websocket, "Missing STT chunk")
                    continue
                try:
                    stt_buffer.extend(base64.b64decode(chunk_b64))
                except Exception:
                    await _send_error(websocket, "Invalid base64 STT chunk")
                    continue

                partial_text = data.get("partial_text")
                if partial_text:
                    await _send_server_event(
                        websocket,
                        "transcription_result",
                        {"text": partial_text, "is_final": False},
                    )

            elif event == "stt_complete":
                provided_text = data.get("text") or data.get("transcript")
                if provided_text:
                    final_text = provided_text
                elif stt_buffer:
                    filename = data.get("filename", "stream.webm")
                    content_type = data.get("content_type", "audio/webm")
                    final_text = await audio_service.transcribe_audio(
                        filename=filename,
                        content=bytes(stt_buffer),
                        content_type=content_type,
                    )
                else:
                    await _send_error(websocket, "No transcript or audio provided")
                    continue

                stt_buffer.clear()
                await _send_server_event(
                    websocket,
                    "transcription_result",
                    {"text": final_text, "is_final": True},
                )

            elif event == "text_message":
                text = (data.get("text") or "").strip()
                if not text:
                    await _send_error(websocket, "Text message is required")
                    continue

                current_step = session.get("current_step")
                if current_step == Step.HISTORY.value:
                    patient_history = session["scenario_metadata"]["patient_history"]
                    conversation_manager.add_turn(session_id, Step.HISTORY.value, "student", text)
                    response = await patient_agent.respond(
                        patient_history=patient_history,
                        conversation_history=conversation_manager.conversations[session_id][Step.HISTORY.value],
                        student_message=text,
                    )
                    conversation_manager.add_turn(session_id, Step.HISTORY.value, "patient", response)
                    await _send_server_event(websocket, "nurse_message", {"text": response, "role": "patient"})
                    await _send_tts_event(websocket, await _safe_tts(response, role="patient"), "patient")
                else:
                    staff_nurse = StaffNurseAgent()
                    response = await staff_nurse.respond(
                        student_input=text,
                        current_step=current_step,
                        next_step=None,
                    )
                    await _send_server_event(websocket, "nurse_message", {"text": response, "role": "nurse"})
                    await _send_tts_event(websocket, await _safe_tts(response, role="staff_nurse"), "nurse")

            elif event == "verification_request":
                student_message = (data.get("text") or "").strip()
                if not student_message:
                    await _send_error(websocket, "Verification text is required")
                    continue

                is_verification, material_type = _detect_verification_request(student_message)
                if not is_verification:
                    await _send_error(websocket, "Could not detect verification request")
                    continue

                response = await _handle_verification_as_action(
                    session=session,
                    student_message=student_message,
                    material_type=material_type,
                )
                await _send_server_event(
                    websocket,
                    "nurse_message",
                    {"text": response.get("staff_nurse_response", "")},
                )
                await _send_tts_event(websocket, response.get("staff_nurse_audio"), "nurse")
                await _send_server_event(
                    websocket,
                    "real_time_feedback",
                    response.get("feedback") or {},
                )
                await _send_tts_event(websocket, response.get("feedback_audio"), "feedback")

            elif event == "action_performed":
                action_type = data.get("action_type")
                if not action_type:
                    await _send_error(websocket, "action_type is required")
                    continue

                if session.get("current_step") != Step.CLEANING_AND_DRESSING.value:
                    await _send_error(websocket, "Actions are only allowed in cleaning_and_dressing")
                    continue

                if is_action_already_performed(session, action_type):
                    feedback = {
                        "status": "duplicate",
                        "missing_actions": [],
                        "message": "This action was already completed.",
                    }
                else:
                    rag_guidelines = session.get("cached_rag_guidelines", "")
                    if not rag_guidelines:
                        rag_result = await retrieve_with_rag(
                            query="wound cleaning and dressing preparation steps sequence prerequisites required actions",
                            scenario_id=session["scenario_id"],
                        )
                        rag_guidelines = rag_result.get("text", "")
                        session["cached_rag_guidelines"] = rag_guidelines

                    performed_actions = session.get("action_events", [])
                    rt_feedback = await clinical_agent.get_real_time_feedback(
                        action_type=action_type,
                        performed_actions=performed_actions,
                        rag_guidelines=rag_guidelines,
                    )
                    action_event_service.record_action(
                        session_id=session_id,
                        action_type=action_type,
                        step=session.get("current_step"),
                        metadata=data.get("metadata"),
                    )
                    feedback = {
                        "status": rt_feedback.get("status", "complete"),
                        "missing_actions": rt_feedback.get("missing_actions", []),
                        "message": rt_feedback.get("message", "Action processed."),
                    }

                await _send_server_event(websocket, "real_time_feedback", feedback)
                await _send_tts_event(
                    websocket,
                    await _safe_tts(feedback.get("message", ""), role="realtime_feedback"),
                    "feedback",
                )

            elif event == "step_complete":
                requested_step = data.get("step") or session.get("current_step")
                step_response = await run_step(
                    StepInput(
                        session_id=session_id,
                        step=requested_step,
                        user_input=data.get("user_input"),
                        student_mcq_answers=data.get("student_mcq_answers"),
                    )
                )

                completed_step = step_response.get("current_step")
                next_step = step_response.get("next_step")

                if completed_step == Step.HISTORY.value:
                    feedback_payload = step_response.get("feedback") or {}
                    await _send_server_event(websocket, "final_feedback", feedback_payload)
                    await _send_tts_event(websocket, step_response.get("feedback_audio"), "feedback")

                elif completed_step == Step.ASSESSMENT.value:
                    mcq_result = step_response.get("mcq_result") or {}
                    summary_text = None
                    if mcq_result:
                        summary_text = (
                            f"You answered {mcq_result.get('correct_count', 0)} out of "
                            f"{mcq_result.get('total_questions', 0)} questions correctly."
                        )
                    await _send_server_event(
                        websocket,
                        "assessment_summary",
                        {
                            "mcq_result": mcq_result,
                            "summary_text": summary_text,
                        },
                    )
                    await _send_tts_event(
                        websocket,
                        step_response.get("summary_audio"),
                        "assessment_feedback",
                    )

                await _send_server_event(websocket, "step_complete", {"next_step": next_step})
                if next_step == Step.COMPLETED.value:
                    await _send_server_event(websocket, "session_end", {"session_id": session_id})

            else:
                await _send_error(websocket, f"Unsupported event: {event}")

    except WebSocketDisconnect:
        return
