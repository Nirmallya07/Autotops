"""
Thin FastAPI wrapper around the LangGraph agent.
Alertmanager (or you, manually via curl) POSTs to /webhook/alert; the agent
runs the full Observe->Diagnose->Decide->Act->Verify loop and returns the
final state.
"""

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from pydantic import BaseModel

from agents.graph import build_graph
from agents.state import AgentState

app = FastAPI(title="AutoOps Agent API")
_agent = build_graph()


class AlertPayload(BaseModel):
    alert_name: str
    service: str
    severity: str


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/webhook/alert")
def handle_alert(payload: AlertPayload):
    initial_state: AgentState = {
        "alert": payload.model_dump(),
        "metrics_snapshot": None,
        "diagnosis": None,
        "decision": None,
        "action_result": None,
        "verified": None,
        "verification_notes": None,
        "retry_count": 0,
    }
    final_state = _agent.invoke(initial_state)
    return final_state
