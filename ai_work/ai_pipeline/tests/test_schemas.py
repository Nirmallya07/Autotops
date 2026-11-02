
import json
from pathlib import Path

from jsonschema import Draft7Validator


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = ROOT / "schemas"


def load_schema(filename):
    path = SCHEMA_DIR / filename

    with path.open("r", encoding="utf-8") as file:
        schema = json.load(file)

    Draft7Validator.check_schema(schema)
    print(f"PASS: {filename} is valid JSON Schema")
    return schema


def test_diagnosis_schema():
    schema = load_schema("diagnosis.json")

    sample = {
        "incident_id": "INC-003",
        "root_cause": "Readiness probe failed",
        "evidence": ["Readiness probe returned connection refused"],
        "confidence": 0.8,
        "recommended_action": "Investigate the health endpoint"
    }

    Draft7Validator(schema).validate(sample)
    print("PASS: Diagnosis sample validated")


def test_remediation_schema():
    schema = load_schema("remediation.json")

    sample = {
        "incident_id": "INC-003",
        "action": "restart",
        "target": "demo-api",
        "reason": "Repeated container failures",
        "evidence_refs": ["kubernetes_events", "logs"],
        "risk": "MEDIUM",
        "approval_required": True,
        "status": "PROPOSED"
    }

    Draft7Validator(schema).validate(sample)
    print("PASS: Remediation sample validated")


def test_report_schema():
    schema = load_schema("report.json")

    sample = {
        "incident_id": "INC-003",
        "service": "demo-api",
        "failure_type": "CrashLoopBackOff",
        "root_cause": "Readiness probe failed",
        "confidence": 0.8,
        "recommended_action": "Investigate the health endpoint",
        "proposed_action": "restart",
        "target": "demo-api",
        "risk": "MEDIUM",
        "approval_status": "APPROVED",
        "execution_status": "SUCCESS",
        "recovery_status": "RECOVERED"
    }

    Draft7Validator(schema).validate(sample)
    print("PASS: Report sample validated")


if __name__ == "__main__":
    test_diagnosis_schema()
    test_remediation_schema()
    test_report_schema()
    print("\nALL SCHEMA TESTS PASSED")
