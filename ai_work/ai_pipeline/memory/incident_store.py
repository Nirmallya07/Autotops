"""SQLite-backed incident memory with deterministic lexical retrieval.

The store contains resolved outcomes only. Retrieval is advisory: callers must
never treat a similar historical incident as proof of the current root cause.
"""
import json
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

_TOKEN = re.compile(r"[a-z0-9_]+")


class IncidentMemory:
    def __init__(self, path="artifacts/incident_memory.sqlite3"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY, service TEXT, failure_type TEXT,
                root_cause TEXT, evidence TEXT, remediation TEXT, outcome TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP)""")
            db.execute("CREATE INDEX IF NOT EXISTS idx_memory_type ON incidents(failure_type)")

    def _connect(self):
        db = sqlite3.connect(str(self.path), timeout=10)
        db.row_factory = sqlite3.Row
        return db

    @staticmethod
    def _tokens(text):
        return set(_TOKEN.findall((text or "").lower()))

    def remember(self, incident: Dict[str, Any], diagnosis: Dict[str, Any],
                 remediation: Dict[str, Any], outcome: Dict[str, Any]):
        status = str(outcome.get("status", "")).upper()
        if status not in {"RECOVERED", "RESOLVED", "SUCCESS"}:
            raise ValueError("Only successful, verified incident outcomes can enter memory.")
        incident_id = incident.get("incident_id")
        if not isinstance(incident_id, str) or not incident_id:
            raise ValueError("incident_id is required")
        values = (
            incident_id, incident.get("service", ""), incident.get("failure_type", ""),
            diagnosis.get("root_cause", ""), json.dumps(diagnosis.get("evidence", [])),
            remediation.get("action", ""), status,
        )
        with self._connect() as db:
            db.execute("""INSERT INTO incidents
                (incident_id,service,failure_type,root_cause,evidence,remediation,outcome)
                VALUES (?,?,?,?,?,?,?) ON CONFLICT(incident_id) DO UPDATE SET
                service=excluded.service, failure_type=excluded.failure_type,
                root_cause=excluded.root_cause, evidence=excluded.evidence,
                remediation=excluded.remediation, outcome=excluded.outcome""", values)

    def retrieve(self, incident: Dict[str, Any], limit=3) -> List[Dict[str, Any]]:
        if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 10:
            raise ValueError("limit must be between 1 and 10")
        evidence = incident.get("evidence", {}) or {}
        text = " ".join([
            str(incident.get("service", "")), str(incident.get("failure_type", "")),
            json.dumps(evidence.get("pod_status", {})),
            json.dumps(evidence.get("kubernetes_events", [])),
            json.dumps(evidence.get("logs", [])),
        ])
        query = self._tokens(text)
        with self._connect() as db:
            rows = db.execute("SELECT * FROM incidents WHERE incident_id != ?",
                              (incident.get("incident_id", ""),)).fetchall()
        ranked = []
        for row in rows:
            doc = " ".join([row["service"] or "", row["failure_type"] or "",
                            row["root_cause"] or "", row["evidence"] or "",
                            row["remediation"] or ""])
            tokens = self._tokens(doc)
            overlap = len(query & tokens)
            if row["failure_type"] == incident.get("failure_type"):
                overlap += 3
            if row["service"] == incident.get("service"):
                overlap += 2
            if overlap:
                ranked.append((overlap, row))
        ranked.sort(key=lambda item: (-item[0], item[1]["incident_id"]))
        return [{
            "incident_id": row["incident_id"], "service": row["service"],
            "failure_type": row["failure_type"], "root_cause": row["root_cause"],
            "evidence": json.loads(row["evidence"] or "[]"),
            "remediation": row["remediation"], "outcome": row["outcome"],
            "similarity_score": score,
        } for score, row in ranked[:limit]]
