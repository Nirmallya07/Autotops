import datetime
import json
import pathlib

from jsonschema import validate

SCHEMA_PATH = pathlib.Path(__file__).resolve().parent.parent / "schemas" / "incident.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text())
WATCHER_VERSION = "watcher-v0"


def next_incident_id(out_dir):
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(exist_ok=True)
    return f"INC-{len(list(out_dir.glob('INC-*.json'))) + 1:03d}"


def create_incident(incident_id, service, namespace, failure_type, severity, evidence):
    incident = {
        "incident_id": incident_id,
        "service": service,
        "namespace": namespace,
        "failure_type": failure_type,
        "severity": severity,
        "detected_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status": "OPEN",
        "source": {"watcher": WATCHER_VERSION},
        "evidence": evidence,
    }
    validate(incident, SCHEMA)
    return incident
