"""Run a normalized Watcher incident through diagnosis and proposal generation.

The entry point checks current pod health and verifies sustained recovery before
suppressing remediation. It stops before approval or execution.
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
    UNKNOWN,
    KubernetesHealthChecker,
)
from ai_work.ai_pipeline.recovery.stability_monitor import (
    NEEDS_REVIEW,
    RECOVERED,
    RecoveryStabilityMonitor,
)


def process_incident(
    incident_path: str,
    diagnoser_name: str = "mock",
    health_checker=None,
    stability_monitor=None,
    stability_window_seconds: float = 60,
    stability_interval_seconds: float = 10,
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
        monitor = (
            stability_monitor
            if stability_monitor is not None
            else RecoveryStabilityMonitor(
                checker,
                window_seconds=stability_window_seconds,
                interval_seconds=stability_interval_seconds,
            )
        )
        stability_check = monitor.monitor(incident, initial_result=health_check)

        if stability_check["status"] == RECOVERED:
            return {
                "incident_id": incident["incident_id"],
                "status": RECOVERED,
                "incident": incident,
                "diagnosis": diagnosis,
                "health_check": health_check,
                "stability_check": stability_check,
                "proposal": None,
                "execution_performed": False,
                "message": (
                    "All sampled observations of the same pod were healthy "
                    "throughout the stability window. Recovery is verified; "
                    "no remediation proposal was generated. Incident closure "
                    "remains a separate action."
                ),
            }

        if stability_check["status"] == NEEDS_REVIEW:
            return {
                "incident_id": incident["incident_id"],
                "status": "NEEDS_HEALTH_REVIEW",
                "incident": incident,
                "diagnosis": diagnosis,
                "health_check": health_check,
                "stability_check": stability_check,
                "proposal": None,
                "execution_performed": False,
                "message": (
                    "The original pod identity could not be verified throughout "
                    "the stability window. Review the current workload."
                ),
            }

        if stability_check["status"] in {UNKNOWN, "UNHEALTHY"}:
            # Surface the latest observation rather than leaving the initial
            # healthy snapshot as the apparent current state.
            latest_observation = (
                stability_check.get("observations") or [{}]
            )[-1]
            health_check = (
                latest_observation
                if latest_observation.get("status") == stability_check["status"]
                else {
                    **health_check,
                    "status": stability_check["status"],
                    "reason": stability_check.get("reason"),
                }
            )
        else:
            health_check = {
                **health_check,
                "status": UNKNOWN,
                "reason": "The stability monitor returned an unrecognized result.",
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

    proposal = RemediationProposal().create(incident, diagnosis)
    result = {
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
    if "stability_check" in locals():
        result["stability_check"] = stability_check
        result["message"] = (
            "The pod became unhealthy or the stability window was interrupted. "
            "Review the approval-gated proposal before any remediation."
        )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Diagnose an incident, check current pod health, verify sustained "
            "recovery, and generate an approval-gated remediation proposal."
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
        "--stability-window-seconds",
        type=float,
        default=60,
        help="How long the pod must remain healthy before recovery is verified (default: 60)",
    )
    parser.add_argument(
        "--stability-interval-seconds",
        type=float,
        default=10,
        help="Seconds between health observations during recovery verification (default: 10)",
    )
    parser.add_argument(
        "--output",
        help="Optional path to write the JSON result; prints to stdout when omitted",
    )
    args = parser.parse_args()

    try:
        result = process_incident(
            args.incident,
            args.diagnoser,
            stability_window_seconds=args.stability_window_seconds,
            stability_interval_seconds=args.stability_interval_seconds,
        )
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
