"""Tests for the local Ollama diagnosis prompt and response handling."""

from ai_work.ai_pipeline.diagnoser.ollama import OllamaDiagnoser


def test_prompt_distinguishes_crashloopbackoff_symptom_from_root_cause():
    prompt = OllamaDiagnoser(model="qwen2.5:3b")._build_prompt({
        "incident_id": "INC-TEST",
        "service": "demo",
        "namespace": "default",
        "failure_type": "CrashLoopBackOff",
        "severity": "HIGH",
        "pod_status": {},
        "kubernetes_events": [],
        "metrics": {},
        "logs": [],
    })

    assert "not the underlying application root cause" in prompt
    assert "exact root cause cannot yet be determined" in prompt
    assert "previous container logs" in prompt
    assert "Do not recommend increasing retry counts" in prompt
    assert "generic runtime or development-server warnings" in prompt


def test_ollama_response_parser_preserves_valid_diagnosis():
    diagnosis = OllamaDiagnoser(model="qwen2.5:3b")._parse_response(
        {"incident_id": "INC-TEST"},
        '{"root_cause":"The exact cause is unknown from supplied logs.",'
        '"evidence":["Exit code 1"],"confidence":0.4,'
        '"recommended_action":"Inspect previous container logs."}',
    )

    assert diagnosis["incident_id"] == "INC-TEST"
    assert diagnosis["root_cause"] == "The exact cause is unknown from supplied logs."
    assert diagnosis["confidence"] == 0.4
    assert diagnosis["recommended_action"] == "Inspect previous container logs."
