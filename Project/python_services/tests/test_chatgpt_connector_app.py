from fastapi.testclient import TestClient

from chatgpt_connector.app import create_app
from chatgpt_connector.auth import ConnectorAuthService


class FakeToolRunner:
    def __init__(self):
        self.calls = []

    @staticmethod
    def manifest():
        return [
            {
                "name": "openclaw_execute_task",
                "description": "Run a safe OpenClaw task.",
                "input_schema": {"type": "object"},
            }
        ]

    async def run(self, tool_name, arguments, session):
        self.calls.append((tool_name, arguments, session.session_id))
        return {"tool": tool_name, "arguments": arguments, "session_id": session.session_id}


def test_connector_app_exposes_manifest_and_tool_surface():
    auth = ConnectorAuthService(public_url="http://connector.test", secret="unit-test-secret")
    tool_runner = FakeToolRunner()
    app = create_app(auth_service=auth, tool_runner=tool_runner)
    client = TestClient(app)

    manifest = client.get("/mcp")
    assert manifest.status_code == 200
    manifest_json = manifest.json()
    assert manifest_json["service_name"] == "chatgpt-openclaw-connector"
    assert manifest_json["tools"][0]["name"] == "openclaw_execute_task"


def test_connector_app_oauth_and_tool_call_flow():
    auth = ConnectorAuthService(public_url="http://connector.test", secret="unit-test-secret")
    tool_runner = FakeToolRunner()
    app = create_app(auth_service=auth, tool_runner=tool_runner)
    client = TestClient(app)

    start = client.post(
        "/oauth/start",
        json={"chatgpt_subject": "chatgpt-user-1", "user_id": "user-1", "display_name": "Jess"},
    )
    assert start.status_code == 200
    start_json = start.json()
    assert start_json["chatgpt_subject"] == "chatgpt-user-1"

    session = client.post(
        "/oauth/callback",
        json={
            "state": start_json["state"],
            "chatgpt_subject": "chatgpt-user-1",
            "user_id": "user-1",
            "display_name": "Jess",
        },
    )
    assert session.status_code == 200
    session_json = session.json()
    assert session_json["session_id"].startswith("sess_")
    assert session_json["session_token"]

    call = client.post(
        "/mcp",
        headers={"Authorization": f"Bearer {session_json['session_token']}"},
        json={
            "tool": "openclaw_execute_task",
            "arguments": {"task_type": "content_strategy", "prompt": "Make a launch plan"},
        },
    )
    assert call.status_code == 200
    call_json = call.json()
    assert call_json["ok"] is True
    assert call_json["result"]["tool"] == "openclaw_execute_task"
    assert tool_runner.calls[0][0] == "openclaw_execute_task"

    session_lookup = client.get(f"/sessions/{session_json['session_id']}")
    assert session_lookup.status_code == 200
    assert session_lookup.json()["session_id"] == session_json["session_id"]
    assert "session_token" not in session_lookup.json()
