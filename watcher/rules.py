from datetime import datetime, timezone

from collectors import prom

ERRORS_5XX_THRESHOLD = 5
ERRORS_5XX_QUERY = 'sum(increase(http_requests_total{status=~"5.."}[1m]))'
REQUEST_RATE_QUERY = 'sum(rate(http_requests_total[1m]))'
OOM_FRESHNESS_SECONDS = 120


def check_crashloop(status, events=None, now=None):
    """Detect the live CrashLoopBackOff state or its fresh kubelet BackOff evidence.

    Kubelet's waiting reason can disappear quickly when a container restarts.
    A fresh 'Back-off restarting failed container' event plus a nonzero restart
    count preserves that evidence without treating ordinary restarts as a loop.
    """
    for c in status["containers"]:
        if c["waiting_reason"] == "CrashLoopBackOff":
            return "HIGH"

    now = now or datetime.now(timezone.utc)
    for event in events or []:
        if event.get("reason") != "BackOff":
            continue
        message = (event.get("message") or "").lower()
        if "restarting failed container" not in message:
            continue
        try:
            stamp = datetime.fromisoformat(
                event["last_timestamp"].replace("Z", "+00:00")
            )
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            age = (now - stamp).total_seconds()
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= age <= 120 and any(c.get("restart_count", 0) > 0 for c in status["containers"]):
            return "HIGH"
    return None


def check_oom(status, now=None):
    """Detect a recent OOM termination, not a stale lastState from an old restart."""
    now = now or datetime.now(timezone.utc)
    for c in status["containers"]:
        if c.get("last_terminated_reason") != "OOMKilled":
            continue
        finished_at = c.get("last_terminated_at")
        if not finished_at:
            continue
        try:
            finished = datetime.fromisoformat(finished_at.replace("Z", "+00:00"))
            if finished.tzinfo is None:
                finished = finished.replace(tzinfo=timezone.utc)
            age = (now - finished).total_seconds()
        except (TypeError, ValueError):
            continue
        if 0 <= age <= OOM_FRESHNESS_SECONDS:
            return "HIGH"
    return None


def check_5xx():
    errors = prom.query(ERRORS_5XX_QUERY)
    rate = prom.query(REQUEST_RATE_QUERY)
    metrics = {
        "http_5xx_last_minute": round(errors, 1) if errors is not None else 0,
        "request_rate_per_sec": round(rate, 3) if rate is not None else 0,
        "threshold": ERRORS_5XX_THRESHOLD,
    }
    if errors is not None and errors > ERRORS_5XX_THRESHOLD:
        return "HIGH", metrics
    return None, metrics
