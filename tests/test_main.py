from fastapi.testclient import TestClient
from unittest.mock import patch
from app.main import cpu_alert_tracker
from app.main import app

client = TestClient(app)


def test_root_endpoint():
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["project"] == "CloudOps Sentinel"
    assert response.json()["status"] == "running"


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_system_metrics_endpoint():
    response = client.get("/metrics/system")

    assert response.status_code == 200

    data = response.json()

    assert "cpu_percent" in data
    assert "memory" in data

    assert 0 <= data["cpu_percent"] <= 100

    assert "total_mb" in data["memory"]
    assert "used_mb" in data["memory"]
    assert "available_mb" in data["memory"]
    assert 0 <= data["memory"]["percent"] <= 100


def test_metrics_endpoint_returns_cpu_alert():
    cpu_alert_tracker.consecutive_high_count = 0

    with patch("app.main.psutil.cpu_percent", return_value=91), \
         patch("app.main.psutil.virtual_memory") as mock_memory:

        mock_memory.return_value.total = 16 * 1024**3
        mock_memory.return_value.used = 8 * 1024**3
        mock_memory.return_value.available = 8 * 1024**3
        mock_memory.return_value.percent = 50

        first = client.get("/metrics/system")
        second = client.get("/metrics/system")
        third = client.get("/metrics/system")

    assert first.json()["alert"]["status"] == "normal"
    assert second.json()["alert"]["status"] == "normal"
    assert third.json()["alert"]["status"] == "warning"

    cpu_alert_tracker.consecutive_high_count = 0


def test_metrics_endpoint_resets_alert_after_low_cpu():
    cpu_alert_tracker.consecutive_high_count = 0

    readings = [91, 91, 91, 70, 91]

    with patch("app.main.psutil.cpu_percent", side_effect=readings), \
         patch("app.main.psutil.virtual_memory") as mock_memory:

        mock_memory.return_value.total = 16 * 1024**3
        mock_memory.return_value.used = 8 * 1024**3
        mock_memory.return_value.available = 8 * 1024**3
        mock_memory.return_value.percent = 50

        responses = [
            client.get("/metrics/system").json()
            for _ in readings
        ]

    statuses = [response["alert"]["status"] for response in responses]

    assert statuses == [
        "normal",
        "normal",
        "warning",
        "normal",
        "normal",
    ]

    assert cpu_alert_tracker.consecutive_high_count == 1

    cpu_alert_tracker.consecutive_high_count = 0
