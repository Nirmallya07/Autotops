"""Append-only lifecycle history kept separate from immutable incident evidence."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


OPEN = "OPEN"
INVESTIGATING = "INVESTIGATING"
AWAITING_HUMAN_APPROVAL = "AWAITING_HUMAN_APPROVAL"
NEEDS_HEALTH_REVIEW = "NEEDS_HEALTH_REVIEW"
RECOVERED = "RECOVERED"
RESOLVED = "RESOLVED"

PROCESSING_OUTCOMES = {
    AWAITING_HUMAN_APPROVAL,
    NEEDS_HEALTH_REVIEW,
    RECOVERED,
}


class IncidentLifecycle:
    """Persist incident state transitions without modifying the source incident.

    One JSON file is stored per incident. Events are appended and the current
    status is a projection of the last event. Only an explicit human action can
    move a RECOVERED incident to RESOLVED.
    """

    def __init__(self, path):
        self.path = Path(path)

    def start_processing(self, incident_id):
        record = self._load_or_create(incident_id)
        current = record["current_status"]
        if current == RESOLVED:
            raise ValueError(f"Incident {incident_id} is already RESOLVED.")
        if current != INVESTIGATING:
            self._append(record, INVESTIGATING, "ai_pipeline", "Incident processing started.")
            self._save(record)
        return record

    def record_outcome(self, incident_id, outcome, details=None):
        if outcome not in PROCESSING_OUTCOMES:
            raise ValueError(f"Unsupported processing outcome: {outcome}")
        record = self._load_or_create(incident_id)
        if record["current_status"] == RESOLVED:
            raise ValueError(f"Incident {incident_id} is already RESOLVED.")
        if record["current_status"] != INVESTIGATING:
            self._append(record, INVESTIGATING, "ai_pipeline", "Incident processing started.")
        self._append(
            record,
            outcome,
            "ai_pipeline",
            (details or {}).get("message") or f"Processing outcome: {outcome}.",
            details=details,
        )
        self._save(record)
        return record

    def resolve(self, incident_id, actor, note):
        if not isinstance(actor, str) or not actor.strip():
            raise ValueError("A non-empty human actor is required to resolve an incident.")
        if not isinstance(note, str) or not note.strip():
            raise ValueError("A resolution note is required.")
        record = self._load_or_create(incident_id)
        if record["current_status"] != RECOVERED:
            raise ValueError(
                "Only a RECOVERED incident can be resolved in this lifecycle version."
            )
        self._append(record, RESOLVED, actor.strip(), note.strip())
        self._save(record)
        return record

    def read(self, incident_id):
        if not self.path.is_file():
            raise FileNotFoundError(f"Lifecycle record not found: {self.path}")
        record = json.loads(self.path.read_text(encoding="utf-8"))
        if record.get("incident_id") != incident_id:
            raise ValueError("Lifecycle record incident_id does not match the request.")
        return record

    def _load_or_create(self, incident_id):
        if self.path.exists():
            record = json.loads(self.path.read_text(encoding="utf-8"))
            if record.get("incident_id") != incident_id:
                raise ValueError("Lifecycle record belongs to a different incident.")
            return record
        now = self._now()
        return {
            "schema_version": 1,
            "incident_id": incident_id,
            "current_status": OPEN,
            "created_at": now,
            "updated_at": now,
            "events": [{
                "status": OPEN,
                "timestamp": now,
                "actor": "watcher",
                "message": "Incident detected by the Watcher.",
            }],
        }

    def _append(self, record, status, actor, message, details=None):
        event = {
            "status": status,
            "timestamp": self._now(),
            "actor": actor,
            "message": message,
        }
        if details is not None:
            event["details"] = details
        record["events"].append(event)
        record["current_status"] = status
        record["updated_at"] = event["timestamp"]

    def _save(self, record):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)

    @staticmethod
    def _now():
        return datetime.now(timezone.utc).isoformat()
