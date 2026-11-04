"""Reporter agent persists machine-readable and human-readable reports."""
import json
from pathlib import Path
from ai_work.ai_pipeline.reporter.reporter import IncidentReporter


class ReporterAgent:
    def __init__(self, output_dir="artifacts/reports"):
        self.output_dir = Path(output_dir)
        self.reporter = IncidentReporter()

    def run(self, incident, diagnosis, proposal, approval, execution, recovery):
        report = self.reporter.generate(incident, diagnosis, proposal, approval, execution, recovery)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{incident.get('incident_id', 'unknown')}.json"
        temp = path.with_suffix(".json.tmp")
        temp.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        temp.replace(path)
        text_path = path.with_suffix(".txt")
        text_path.write_text(self.reporter.to_text(report), encoding="utf-8")
        return {"report": report, "json_path": str(path), "text_path": str(text_path)}
