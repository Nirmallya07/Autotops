from collectors import prom

ERRORS_5XX_THRESHOLD = 5
ERRORS_5XX_QUERY = 'sum(increase(http_requests_total{status=~"5.."}[1m]))'
REQUEST_RATE_QUERY = 'sum(rate(http_requests_total[1m]))'


def check_crashloop(status):
    for c in status["containers"]:
        if c["waiting_reason"] == "CrashLoopBackOff":
            return "HIGH"
    return None


def check_oom(status):
    for c in status["containers"]:
        if c["last_terminated_reason"] == "OOMKilled" or c["last_exit_code"] == 137:
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
