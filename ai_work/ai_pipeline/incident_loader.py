import json
from pathlib import Path
from typing import Any, Dict

from jsonschema import ValidationError, validate


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "incident.json"
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


class IncidentLoader:
    """Load and validate incidents against the shared JSON schema."""

    def load(self, file_path: str) -> Dict[str, Any]:
        path = Path(file_path)
        if not path.is_file():
            raise FileNotFoundError(f"Incident file not found: {file_path}")

        try:
            with path.open("r", encoding="utf-8") as file:
                incident = json.load(file)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"Invalid incident JSON in {file_path}: {exc.msg}"
            ) from exc

        try:
            validate(instance=incident, schema=SCHEMA)
        except ValidationError as exc:
            location = ".".join(str(part) for part in exc.absolute_path)
            field = f" at '{location}'" if location else ""
            raise ValueError(
                f"Invalid incident schema{field}: {exc.message}"
            ) from exc

        return incident
