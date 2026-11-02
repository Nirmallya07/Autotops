
import json
import ast
import requests

from .interface import Diagnoser


class OllamaDiagnoser(Diagnoser):

    def __init__(
        self,
        model="llama3.2:3b",
        url="http://localhost:11434/api/generate"
    ):
        self.model = model
        self.url = url

    def diagnose(self, incident):
        prompt = self._build_prompt(incident)

        response = requests.post(
            self.url,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "format": "json",
            },
            timeout=120,
        )

        response.raise_for_status()

        data = response.json()
        model_output = data.get("response", "").strip()

        return self._parse_response(incident, model_output)

    def _build_prompt(self, context):
        # Prefer the separated log streams. The legacy combined "logs"
        # field often contains the same entries and would duplicate evidence.
        current_logs = context.get("current_logs")
        previous_logs = context.get("previous_logs")

        if current_logs is None:
            current_logs = context.get("logs", [])

        # Remove repeated lines while preserving their original order.
        def unique_lines(lines):
            if not isinstance(lines, list):
                return []
            seen = set()
            result = []
            for line in lines:
                key = str(line).strip()
                if key and key not in seen:
                    seen.add(key)
                    result.append(line)
            return result

        evidence = {
            "pod_status": context.get("pod_status", {}),
            "kubernetes_events": context.get("kubernetes_events", []),
            "metrics": context.get("metrics", {}),
            "current_logs": unique_lines(current_logs),
            "previous_logs": unique_lines(previous_logs),
            "log_collection": context.get("log_collection", {}),
            "event_collection": context.get("event_collection", {}),
        }

        return f"""
You are the diagnostic component of AutoTops.

Analyze only the supplied incident evidence.
Do not invent evidence.
Log and event collection metadata describes what the watcher could retrieve; it is an observability record, not proof of an application failure.
Do not execute commands.
Do not claim that remediation has been executed.

Incident ID: {context.get("incident_id", "UNKNOWN")}
Service: {context.get("service", "UNKNOWN")}
Namespace: {context.get("namespace", "UNKNOWN")}
Failure Type: {context.get("failure_type", "UNKNOWN")}
Severity: {context.get("severity", "UNKNOWN")}

Evidence:
{json.dumps(evidence, indent=2)}

Return exactly one JSON object with these four fields:
{{
  "root_cause": "brief explanation based on evidence",
  "evidence": ["specific evidence supporting the diagnosis"],
  "confidence": 0.0,
  "recommended_action": "recommended next action"
}}

Diagnostic reasoning rules:
- Distinguish observed facts from hypotheses. Never present a hypothesis as a confirmed cause.
- CrashLoopBackOff is a Kubernetes symptom describing repeated container failures, not the underlying application root cause.
- A non-zero exit code or last termination reason of Error confirms an unsuccessful termination, but does not by itself explain why it happened.
- Examine application log messages for explicit descriptions of the action or error immediately associated with termination before relying on generic Kubernetes status fields.
- Evidence priority: (1) explicit application error or termination messages, (2) surrounding previous-container logs, (3) current-container logs, (4) Kubernetes events and termination details, (5) metrics and generic runtime messages.
- When an application log explicitly identifies the action that terminated the process, state that action as the evidence-supported cause. Do not replace it with the less-informative statement that the container merely exited with an error.
- Treat startup messages, routine informational output, and generic runtime warnings as context, not causal evidence, unless the supplied evidence directly connects them to the failure.
- Use only the supplied logs, pod status, events, metrics, and collection metadata. Do not infer a specific code defect, configuration error, resource shortage, or dependency failure unless the evidence supports it.
- Treat log_collection and event_collection statuses and error messages only as collection diagnostics. Never cite a Kubernetes API error, missing previous-log stream, permission problem, or empty log response as the application root cause.
- If a log stream or event collection has status "error" or "unavailable", explicitly account for that evidence gap when choosing confidence and the recommended next diagnostic step. Do not describe a failed collection request as proof that the application produced no logs or events.
- If no application log or other evidence identifies the underlying cause, explicitly say that the exact root cause cannot yet be determined; state the observed termination separately.
- Recommend the most useful next diagnostic step. For CrashLoopBackOff, prioritize inspecting current and previous container logs and correlating them with termination details and recent events. Do not recommend increasing retry counts, changing restart policies, or restarting a pod as a substitute for identifying the cause unless the evidence specifically justifies that action.
- Keep recommendations operational, specific, and proportional to the evidence.
- Do not treat generic runtime or development-server warnings as the cause unless they are linked to the observed failure.
- Prefer specific error messages that directly explain the failure; do not cite unrelated startup messages or generic warnings as supporting evidence.
- Do not repeat the same evidence item more than once in the evidence list.

Output requirements:
- root_cause must be a plain string that clearly labels confirmed facts and, where needed, an unconfirmed hypothesis.
- evidence must be a list of strings containing only facts present in the supplied incident.
- confidence must be a number from 0 to 1 and reflect how strongly the evidence supports the stated root cause. Use lower confidence when the exact cause is unknown.
- recommended_action must be a plain string.
- Return exactly the four requested fields, with no surrounding text.
"""

    def _decode_json(self, value):
        """
        Decode JSON repeatedly when a JSON object has been
        encoded inside one or more JSON strings.
        """
        current = value

        for _ in range(5):
            if isinstance(current, dict):
                return current

            if not isinstance(current, str):
                return None

            try:
                decoded = json.loads(current)
            except (json.JSONDecodeError, TypeError):
                break

            if isinstance(decoded, dict):
                return decoded

            if isinstance(decoded, str):
                current = decoded
            else:
                return None

        # Some model responses use Python-style dictionary strings.
        if isinstance(current, str):
            try:
                decoded = ast.literal_eval(current)
                if isinstance(decoded, dict):
                    return decoded
            except (ValueError, SyntaxError):
                pass

        return None

    def _parse_response(self, incident, model_output):
        result = self._decode_json(model_output.strip())

        # Try extracting a JSON object if extra text surrounds it.
        if not isinstance(result, dict):
            start = model_output.find("{")
            end = model_output.rfind("}")

            if start != -1 and end > start:
                candidate = model_output[start:end + 1]
                result = self._decode_json(candidate)

        # Handle JSON mistakenly returned inside the root_cause field.
        if isinstance(result, dict):
            nested_text = result.get("root_cause")

            if isinstance(nested_text, str):
                nested = self._decode_json(nested_text)

                if isinstance(nested, dict) and "root_cause" in nested:
                    result = nested

        # Safe fallback if parsing genuinely fails.
        if not isinstance(result, dict):
            result = {
                "root_cause": "Unable to parse the model response.",
                "evidence": [],
                "confidence": 0.0,
                "recommended_action":
                    "Review the supplied evidence manually.",
            }

        # Normalize and validate individual fields.
        root_cause = result.get("root_cause")
        if not isinstance(root_cause, str):
            root_cause = "Unable to determine root cause."

        evidence = result.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = []

        confidence = result.get("confidence", 0.0)
        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0 <= confidence <= 1
        ):
            confidence = 0.0

        recommended_action = result.get("recommended_action")
        if not isinstance(recommended_action, str):
            recommended_action = "Collect additional diagnostic evidence."

        return {
            "incident_id": incident.get("incident_id", "UNKNOWN"),
            "root_cause": root_cause,
            "evidence": evidence,
            "confidence": confidence,
            "recommended_action": recommended_action,
        }
