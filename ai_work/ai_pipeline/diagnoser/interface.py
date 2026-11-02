from abc import ABC, abstractmethod
from typing import Any, Dict


class Diagnoser(ABC):
    """
    Base interface for all AutoTops diagnosers.

    A diagnoser receives an incident and its evidence,
    then returns a structured diagnosis.
    """

    @abstractmethod
    def diagnose(self, incident: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze the incident and return a diagnosis.

        Expected output:
        {
            "incident_id": "...",
            "root_cause": "...",
            "evidence": [...],
            "confidence": 0.0,
            "recommended_action": "..."
        }
        """
        pass