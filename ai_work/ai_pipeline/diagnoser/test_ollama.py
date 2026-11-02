from pathlib import Path
from ai_work.ai_pipeline.incident_loader import IncidentLoader
from ai_work.ai_pipeline.diagnoser.context import DiagnosticContext
from ai_work.ai_pipeline.diagnoser.ollama import OllamaDiagnoser


def test_ollama_diagnoser():
    path = Path(__file__).resolve().parents[2] / "examples" / "incident-CrashLoopBackOff.json"
    incident = IncidentLoader().load(str(path))
    context = DiagnosticContext().build(incident)
    diagnosis = OllamaDiagnoser().diagnose(context)
    assert diagnosis["incident_id"] == incident["incident_id"]
    assert diagnosis["root_cause"].strip()
    assert isinstance(diagnosis["evidence"], list)
    assert 0 <= diagnosis["confidence"] <= 1
    assert diagnosis["recommended_action"].strip()
