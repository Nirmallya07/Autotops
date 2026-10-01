"""
The doctor's decision loop, as a LangGraph StateGraph.

    START -> observe -> diagnose -> decide -> act -> verify -> END
                                        |
                                        +-> (low confidence) -> notify_human -> END

Each node is a plain function: (AgentState) -> dict of fields to update.
LangGraph merges the returned dict back into the running state — you don't
need to return the whole state, just what changed.

Run `python -m agents.graph` for a smoke test with a fake alert (no real
Prometheus/K8s calls needed for that path).
"""

import json
import os

from langgraph.graph import StateGraph, START, END

from agents.state import AgentState
from agents.claude_client import ask_claude
from agents.prompts import DIAGNOSE_SYSTEM_PROMPT, DECIDE_SYSTEM_PROMPT
from agents import tools


CONFIDENCE_THRESHOLD = float(os.environ.get("AUTO_REMEDIATE_CONFIDENCE_THRESHOLD", 0.75))


# ---------- Nodes ----------

def observe_node(state: AgentState) -> dict:
    """Pull current metrics for the affected service."""
    service = state["alert"]["service"]
    # TODO: once the sample app is instrumented, this hits real Prometheus.
    snapshot = tools.query_service_metrics(service)
    return {"metrics_snapshot": snapshot}


def diagnose_node(state: AgentState) -> dict:
    """Ask Claude to turn the alert + metrics into a root-cause hypothesis."""
    user_prompt = (
        f"Alert: {json.dumps(state['alert'])}\n"
        f"Metrics snapshot: {json.dumps(state['metrics_snapshot'])}"
    )
    raw = ask_claude(DIAGNOSE_SYSTEM_PROMPT, user_prompt)
    # TODO: wrap in try/except and handle malformed JSON from the model
    diagnosis = json.loads(raw)
    return {"diagnosis": diagnosis}


def decide_node(state: AgentState) -> dict:
    """Ask Claude to pick one remediation action given the diagnosis."""
    user_prompt = f"Diagnosis: {json.dumps(state['diagnosis'])}"
    raw = ask_claude(DECIDE_SYSTEM_PROMPT, user_prompt)
    decision = json.loads(raw)
    return {"decision": decision}


def act_node(state: AgentState) -> dict:
    """Execute the chosen action via tools.py."""
    action = state["decision"]["action"]
    service = state["alert"]["service"]

    if action == "rollback":
        result = tools.rollback_deployment(service)
    elif action == "restart":
        result = tools.restart_deployment(service)
    elif action == "scale_up":
        result = tools.scale_deployment(service, replicas=state.get("_scale_target", 3))
    else:
        result = "no_op"

    return {"action_result": result}


def notify_node(state: AgentState) -> dict:
    """Escalate to a human instead of acting automatically."""
    diagnosis = state.get("diagnosis", {})
    msg = (
        f"AutoOps needs a human: {state['alert']['service']} — "
        f"{diagnosis.get('root_cause', 'unknown cause')} "
        f"(confidence {diagnosis.get('confidence', 0):.2f})"
    )
    result = tools.notify_human(msg)
    return {"action_result": result}


def verify_node(state: AgentState) -> dict:
    """Re-check metrics after acting to confirm the fix worked.

    TODO: this currently just re-runs the same query. Real version should
    compare before/after and decide if a retry or escalation is needed.
    """
    service = state["alert"]["service"]
    snapshot = tools.query_service_metrics(service, minutes=2)
    return {
        "metrics_snapshot": snapshot,
        "verified": True,  # TODO: derive from actual comparison
        "verification_notes": "stub — always reports success",
    }


# ---------- Routing ----------

def route_after_diagnose(state: AgentState) -> str:
    """If Claude isn't confident, skip straight to a human instead of deciding."""
    confidence = state.get("diagnosis", {}).get("confidence", 0)
    return "decide" if confidence >= CONFIDENCE_THRESHOLD else "notify_human"


def route_after_decide(state: AgentState) -> str:
    action = state.get("decision", {}).get("action")
    return "notify_human" if action == "notify_human" else "act"


# ---------- Graph assembly ----------

def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("observe", observe_node)
    graph.add_node("diagnose", diagnose_node)
    graph.add_node("decide", decide_node)
    graph.add_node("act", act_node)
    graph.add_node("notify_human", notify_node)
    graph.add_node("verify", verify_node)

    graph.add_edge(START, "observe")
    graph.add_edge("observe", "diagnose")
    graph.add_conditional_edges("diagnose", route_after_diagnose, ["decide", "notify_human"])
    graph.add_conditional_edges("decide", route_after_decide, ["act", "notify_human"])
    graph.add_edge("act", "verify")
    graph.add_edge("verify", END)
    graph.add_edge("notify_human", END)

    return graph.compile()


if __name__ == "__main__":
    # Smoke test — will fail past observe_node without a real Prometheus/K8s
    # connection and ANTHROPIC_API_KEY set. Useful to check the graph
    # compiles and wires together correctly.
    app = build_graph()
    g = app.get_graph()
    print("Nodes:", list(g.nodes.keys()))
    print("Edges:")
    for edge in g.edges:
        print(f"  {edge.source} -> {edge.target}")
    # For a visual diagram instead: pip install grandalf, then use
    # app.get_graph().draw_ascii()
