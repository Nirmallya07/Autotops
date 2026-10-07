import os

import requests

PROM_URL = os.getenv("PROM_URL", "http://localhost:9090")


def query(promql):
    r = requests.get(f"{PROM_URL}/api/v1/query", params={"query": promql}, timeout=5)
    r.raise_for_status()
    result = r.json()["data"]["result"]
    if not result:
        return None
    return float(result[0]["value"][1])
