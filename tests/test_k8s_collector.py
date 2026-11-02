import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "watcher"))

from collectors import k8s


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.reason = message


class FakeCoreV1Api:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def read_namespaced_pod_log(self, pod_name, namespace, **kwargs):
        self.calls.append((pod_name, namespace, kwargs))
        key = (kwargs.get("container"), kwargs["previous"])
        value = self.responses[key]
        if isinstance(value, Exception):
            raise value
        return FakeResponse(value)


def test_collects_current_and_previous_logs_for_each_container(monkeypatch):
    api = FakeCoreV1Api({
        ("app", False): b"app current\n",
        ("app", True): b"app previous\n",
        ("sidecar", False): b"sidecar current\n",
        ("sidecar", True): b"sidecar previous\n",
    })
    monkeypatch.setattr(k8s, "get_kubernetes_client", lambda: api)

    result = k8s.get_log_evidence(
        "default", "demo-pod", container_names=["app", "sidecar", "app"]
    )

    assert result["current_logs"] == ["app current", "sidecar current"]
    assert result["previous_logs"] == ["app previous", "sidecar previous"]
    assert result["logs"] == result["current_logs"] + result["previous_logs"]
    assert set(result["log_collection"]["containers"]) == {"app", "sidecar"}
    assert len(api.calls) == 4
    assert all(call[2]["container"] in {"app", "sidecar"} for call in api.calls)
    assert all(call[2]["tail_lines"] == 300 for call in api.calls)
    assert all(call[2]["_preload_content"] is False for call in api.calls)


def test_log_collection_records_unavailable_previous_stream(monkeypatch):
    api = FakeCoreV1Api({
        ("app", False): b"app started\n",
        ("app", True): FakeApiError(404, "previous container instance not found"),
    })
    monkeypatch.setattr(k8s, "get_kubernetes_client", lambda: api)

    result = k8s.get_log_evidence(
        "default", "demo-pod", container_names=["app"]
    )

    assert result["current_logs"] == ["app started"]
    assert result["previous_logs"] == []
    previous = result["log_collection"]["containers"]["app"]["previous"]
    assert previous["status"] == "unavailable"
    assert previous["error"]["http_status"] == 404
    assert "not found" in previous["error"]["message"]


def test_log_collection_records_api_errors_without_fabricating_log_evidence(monkeypatch):
    api = FakeCoreV1Api({
        ("app", False): FakeApiError(403, "forbidden"),
        ("app", True): FakeApiError(403, "forbidden"),
    })
    monkeypatch.setattr(k8s, "get_kubernetes_client", lambda: api)

    result = k8s.get_log_evidence(
        "default", "demo-pod", container_names=["app"]
    )

    assert result["logs"] == []
    assert result["current_logs"] == []
    assert result["previous_logs"] == []
    for stream in result["log_collection"]["containers"]["app"].values():
        assert stream["status"] == "error"
        assert stream["error"]["http_status"] == 403


def test_log_collection_handles_empty_successful_stream(monkeypatch):
    api = FakeCoreV1Api({
        (None, False): b"",
        (None, True): b"",
    })
    monkeypatch.setattr(k8s, "get_kubernetes_client", lambda: api)

    result = k8s.get_log_evidence("default", "demo-pod")

    assert result["logs"] == []
    streams = result["log_collection"]["containers"]["default"]
    assert streams["current"]["status"] == "empty"
    assert streams["previous"]["status"] == "empty"


def test_log_collection_strips_ansi_and_health_noise(monkeypatch):
    api = FakeCoreV1Api({
        ("app", False): b"\x1b[31mERROR app failed\x1b[0m\nGET /health 200\n",
        ("app", True): b"",
    })
    monkeypatch.setattr(k8s, "get_kubernetes_client", lambda: api)

    result = k8s.get_log_evidence(
        "default", "demo-pod", container_names=["app"]
    )

    assert result["current_logs"] == ["ERROR app failed"]
