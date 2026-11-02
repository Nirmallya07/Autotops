"""Observe a pod repeatedly before declaring an incident recovered."""

import math
import time
from datetime import datetime, timezone

from ai_work.ai_pipeline.recovery.health_checker import (
    HEALTHY_NOW,
    IDENTITY_CHANGED,
    POD_NOT_FOUND,
    UNHEALTHY,
    UNKNOWN,
)


RECOVERED = "RECOVERED"
NEEDS_REVIEW = "NEEDS_REVIEW"


class RecoveryStabilityMonitor:
    """Require healthy observations of the same pod for a configured window.

    This monitor is read-only. It delegates every observation to the existing
    KubernetesHealthChecker and stops early if health becomes uncertain,
    unhealthy, or the original pod identity can no longer be verified.
    """

    def __init__(
        self,
        health_checker,
        window_seconds=60,
        interval_seconds=10,
        sleep_fn=time.sleep,
    ):
        self._validate_duration("window_seconds", window_seconds)
        self._validate_duration("interval_seconds", interval_seconds)
        self.health_checker = health_checker
        self.window_seconds = float(window_seconds)
        self.interval_seconds = float(interval_seconds)
        self.sleep = sleep_fn

    def monitor(self, incident, initial_result=None):
        """Return RECOVERED only after the same pod stays healthy for the window."""
        started_at = datetime.now(timezone.utc).isoformat()
        first = initial_result or self.health_checker.assess(incident)
        observations = [first]

        if first.get("status") != HEALTHY_NOW:
            return self._result(
                incident,
                self._map_status(first.get("status")),
                "The initial health observation was not healthy; stability monitoring was not started.",
                started_at,
                observations,
            )

        original_uid = first.get("pod_uid")
        if not first.get("identity_verified") or not original_uid:
            return self._result(
                incident,
                UNKNOWN,
                "The initial observation did not verify the original pod identity.",
                started_at,
                observations,
            )

        elapsed = 0.0
        while elapsed < self.window_seconds:
            wait_seconds = min(self.interval_seconds, self.window_seconds - elapsed)
            self.sleep(wait_seconds)
            elapsed += wait_seconds

            observation = self.health_checker.assess(incident)
            observations.append(observation)
            status = observation.get("status")

            if status != HEALTHY_NOW:
                return self._result(
                    incident,
                    self._map_status(status),
                    observation.get("reason") or "A later health observation was not healthy.",
                    started_at,
                    observations,
                )

            if (
                not observation.get("identity_verified")
                or not observation.get("pod_uid")
                or observation.get("pod_uid") != original_uid
            ):
                return self._result(
                    incident,
                    NEEDS_REVIEW,
                    "The pod identity changed or could not be verified during the stability window.",
                    started_at,
                    observations,
                )

        return self._result(
            incident,
            RECOVERED,
            f"The same pod remained healthy for {self.window_seconds:g} seconds.",
            started_at,
            observations,
        )

    @staticmethod
    def _map_status(status):
        if status == UNHEALTHY:
            return UNHEALTHY
        if status in {POD_NOT_FOUND, IDENTITY_CHANGED}:
            return NEEDS_REVIEW
        return UNKNOWN

    @staticmethod
    def _validate_duration(name, value):
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value <= 0
        ):
            raise ValueError(f"{name} must be a positive finite number.")

    def _result(self, incident, status, reason, started_at, observations):
        return {
            "incident_id": incident.get("incident_id"),
            "status": status,
            "reason": reason,
            "started_at": started_at,
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "window_seconds": self.window_seconds,
            "sample_count": len(observations),
            "observations": observations,
        }
