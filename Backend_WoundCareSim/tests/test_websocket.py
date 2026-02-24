from fastapi.testclient import TestClient

from app.main import app
from app.api.session_routes import session_manager


client = TestClient(app)


def _create_session():
    session_id = session_manager.create_session(
        scenario_id="scenario_ws",
        student_id="student_ws",
        scenario_metadata={
            "scenario_id": "scenario_ws",
            "title": "WS Scenario",
            "patient_history": "Patient has a wound.",
            "wound_details": "Forearm laceration",
            "conversation_points": [],
            "assessment_questions": [],
            "evaluation_criteria": {},
            "vector_namespace": "ws-test",
        },
    )
    session = session_manager.get_session(session_id)
    return session_id, session["session_token"]


def test_websocket_rejects_invalid_token():
    session_id, _ = _create_session()

    with client.websocket_connect(f"/ws/session/{session_id}?token=invalid") as ws:
        error_payload = ws.receive_json()
        assert error_payload["type"] == "error"
        assert "Authentication failed" in error_payload["message"]


def test_websocket_connect_and_invalid_event_error():
    session_id, token = _create_session()

    with client.websocket_connect(f"/ws/session/{session_id}?token={token}") as ws:
        connected = ws.receive_json()
        assert connected["type"] == "server_event"
        assert connected["event"] == "nurse_message"

        ws.send_json({"type": "event", "event": "unknown_event", "data": {}})
        error_payload = ws.receive_json()
        assert error_payload["type"] == "error"
        assert "Unsupported event" in error_payload["message"]
