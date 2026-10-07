from app.app import app


def test_health():
    client = app.test_client()
    response = client.get("/health")
    assert response.status_code == 200


def test_failure_endpoint():
    client = app.test_client()
    response = client.get("/failure")
    assert response.status_code == 500


def test_metrics_endpoint_and_500_counter():
    client = app.test_client()

    # Ensure metrics endpoint exists
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "http_requests_total" in r.get_data(as_text=True)

    # Call /failure and then check metrics contains status="500"
    client.get("/failure")
    metrics_text = client.get("/metrics").get_data(as_text=True)

    assert "http_requests_total" in metrics_text
    # Check presence of status="500" label in the metric output
    assert 'status="500"' in metrics_text


def test_metrics_contains_2xx_after_health():
    client = app.test_client()
    client.get("/health")
    metrics_text = client.get("/metrics").get_data(as_text=True)
    assert 'status="200"' in metrics_text