"""Run a normalized Watcher incident through diagnosis and proposal generation.

This entry point deliberately stops before approval or execution. A human must
review the generated proposal before any execution handoff is created.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

from ai_work.ai_pipeline.diagnoser.context import DiagnosticContext
from ai_work.ai_pipeline.diagnoser.mock import MockDiagnoser
from ai_work.ai_pipeline.diagnoser.ollama import OllamaDiagnoser
from ai_work.ai_pipeline.diagnoser.validator import DiagnosisValidator
from ai_work.ai_pipeline.fixer.proposal import RemediationProposal
from ai_work.ai_pipeline.incident_loader import IncidentLoader


def process_incident(incident_path: str, diagnoser_name: str = "mock") -> Dict[str, Any]:
    """Load a Watcher JSON incident, diagnose it, validate it, and propose a fix."""
    incident = IncidentLoader().load(incident_path)
    context = DiagnosticContext().build(incident)

    if diagnoser_name == "ollama":
        diagnoser = OllamaDiagnoser()
    elif diagnoser_name == "mock":
        diagnoser = MockDiagnoser()
    else:
        raise ValueError(f"Unsupported diagnoser: {diagnoser_name}")

    diagnosis = DiagnosisValidator().validate(diagnoser.diagnose(context))
    proposal = RemediationProposal().create(incident, diagnosis)

    return {
        "incident_id": incident["incident_id"],
        "status": "AWAITING_HUMAN_APPROVAL",
        "incident": incident,
        "diagnosis": diagnosis,
        "proposal": proposal,
        "execution_performed": False,
        "message": "Review the proposal and obtain explicit human approval before execution.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Diagnose a Watcher incident and generate an approval-gated remediation proposal."
    )
    parser.add_argument("incident", help="Path to a normalized Watcher incident JSON file")
    parser.add_argument(
        "--diagnoser",
        choices=("mock", "ollama"),
        default="mock",
        help="Use deterministic mock diagnosis (default) or local Ollama diagnosis",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the JSON result; prints to stdout when omitted",
    )
    args = parser.parse_args()

    try:
        result = process_incident(args.incident, args.diagnoser)
        rendered = json.dumps(result, indent=2, ensure_ascii=False)
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(rendered + "\n", encoding="utf-8")
            print(f"Analysis written to {output_path}")
            print(f"Status: {result['status']}")
        else:
            print(rendered)
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"AutoOps incident processing failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
