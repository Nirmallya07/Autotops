from app.app import app


def test_health():
    client = app.test_client()

    response = client.get("/health")

    assert response.status_code == 200


def test_failure_endpoint():
    client = app.test_client()

    response = client.get("/failure")

    assert response.status_code == 500