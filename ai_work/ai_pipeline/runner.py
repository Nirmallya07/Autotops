"""Run a normalized Watcher incident through diagnosis and proposal generation.

This entry point checks the affected pod before recommending remediation. It
stops before approval or execution; a human must review every proposal.
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
from ai_work.ai_pipeline.recovery.health_checker import (
    HEALTHY_NOW,
    IDENTITY_CHANGED,
    POD_NOT_FOUND,
    KubernetesHealthChecker,
)


def process_incident(
    incident_path: str,
    diagnoser_name: str = "mock",
    health_checker=None,
) -> Dict[str, Any]:
    """Diagnose an incident and recommend remediation only when appropriate."""
    incident = IncidentLoader().load(incident_path)
    context = DiagnosticContext().build(incident)

    if diagnoser_name == "ollama":
        diagnoser = OllamaDiagnoser()
    elif diagnoser_name == "mock":
        diagnoser = MockDiagnoser()
    else:
        raise ValueError(f"Unsupported diagnoser: {diagnoser_name}")

    diagnosis = DiagnosisValidator().validate(diagnoser.diagnose(context))

    checker = health_checker if health_checker is not None else KubernetesHealthChecker()
    health_check = checker.assess(incident)

    if health_check["status"] == HEALTHY_NOW:
        return {
            "incident_id": incident["incident_id"],
            "status": "CURRENTLY_HEALTHY",
            "incident": incident,
            "diagnosis": diagnosis,
            "health_check": health_check,
            "proposal": None,
            "execution_performed": False,
            "message": (
                "The affected pod is healthy at this check. No remediation "
                "proposal was generated. Observe it over a stability window "
                "before declaring the incident resolved."
            ),
        }

    if health_check["status"] in {POD_NOT_FOUND, IDENTITY_CHANGED}:
        return {
            "incident_id": incident["incident_id"],
            "status": "NEEDS_HEALTH_REVIEW",
            "incident": incident,
            "diagnosis": diagnosis,
            "health_check": health_check,
            "proposal": None,
            "execution_performed": False,
            "message": (
                "The original pod could not be safely matched to the live pod. "
                "Review the current workload before proposing remediation."
            ),
        }

    # UNKNOWN does not mean healthy. Preserve the approval-gated proposal path,
    # but include the failed health assessment so a reviewer sees the uncertainty.
    proposal = RemediationProposal().create(incident, diagnosis)

    return {
        "incident_id": incident["incident_id"],
        "status": "AWAITING_HUMAN_APPROVAL",
        "incident": incident,
        "diagnosis": diagnosis,
        "health_check": health_check,
        "proposal": proposal,
        "execution_performed": False,
        "message": (
            "Review the proposal and obtain explicit human approval before "
            "execution. The live health check was inconclusive."
            if health_check["status"] == UNKNOWN
            else "Review the proposal and obtain explicit human approval before execution."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose a Watcher incident, check current pod health, and "
            "generate an approval-gated remediation proposal."
        )
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
