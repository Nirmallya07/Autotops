import datetime
import json
import pathlib

from jsonschema import validate

SCHEMA_PATH = pathlib.Path(__file__).resolve().parent.parent / "schemas" / "incident.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text())
WATCHER_VERSION = "watcher-v0"


def next_incident_id(out_dir):
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    # Use the highest existing numeric ID, not the file count: deleted files
    # must not cause an ID collision with an incident that still exists.
    ids = []
    for path in out_dir.glob("INC-*.json"):
        try:
            ids.append(int(path.stem.split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"INC-{max(ids, default=0) + 1:03d}"


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
