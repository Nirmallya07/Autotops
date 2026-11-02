from ai_work.ai_pipeline.diagnoser.context import DiagnosticContext
from ai_work.ai_pipeline.diagnoser.ollama import OllamaDiagnoser


def test_diagnostic_context_carries_collection_metadata():
    incident = {
        "incident_id": "INC-TEST",
        "evidence": {
            "logs": [],
            "current_logs": [],
            "previous_logs": [],
            "log_collection": {
                "containers": {
                    "app": {
                        "current": {"status": "error"},
                        "previous": {"status": "unavailable"},
                    }
                }
            },
            "event_collection": {"status": "error"},
        },
    }

    context = DiagnosticContext().build(incident)

    assert context["log_collection"]["containers"]["app"]["current"]["status"] == "error"
    assert context["event_collection"]["status"] == "error"


def test_ollama_prompt_explains_collection_failures_are_not_root_causes():
    context = {
        "incident_id": "INC-TEST",
        "current_logs": [],
        "previous_logs": [],
        "log_collection": {
            "containers": {
                "app": {"current": {"status": "error"}}
            }
        },
        "event_collection": {"status": "error"},
    }

    prompt = OllamaDiagnoser()._build_prompt(context)

    assert '"log_collection"' in prompt
    assert '"event_collection"' in prompt
    assert "Never cite a Kubernetes API error" in prompt
    assert "observability record, not proof" in prompt
