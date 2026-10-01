"""
Tests that don't need a real Prometheus/K8s/Claude connection — just check
the graph compiles and the routing functions make the right call given a
state. Add integration tests separately once the stub tools are filled in.
"""

from agents.graph import build_graph, route_after_diagnose, route_after_decide


def test_graph_compiles():
    app = build_graph()
    assert app is not None


def test_route_after_diagnose_high_confidence_goes_to_decide():
    state = {"diagnosis": {"confidence": 0.9}}
    assert route_after_diagnose(state) == "decide"


def test_route_after_diagnose_low_confidence_goes_to_notify():
    state = {"diagnosis": {"confidence": 0.3}}
    assert route_after_diagnose(state) == "notify_human"


def test_route_after_decide_notify_action():
    state = {"decision": {"action": "notify_human"}}
    assert route_after_decide(state) == "notify_human"


def test_route_after_decide_remediation_action_goes_to_act():
    state = {"decision": {"action": "restart"}}
    assert route_after_decide(state) == "act"
