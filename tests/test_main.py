
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app, cpu_alert_tracker
from app.prometheus_client import PrometheusClientError


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


def test_analyze_endpoint_healthy_system():
    with patch("app.main.psutil.cpu_percent", return_value=40), \
         patch("app.main.psutil.virtual_memory") as mock_memory, \
         patch("app.main.fetch_active_alerts", return_value=[]):

        mock_memory.return_value.percent = 60

        response = client.get("/analyze")

    assert response.status_code == 200

    data = response.json()

    assert data["project"] == "CloudOps Sentinel"
    assert data["prometheus_status"] == "connected"
    assert data["analysis"]["status"] == "healthy"
    assert data["analysis"]["incident_count"] == 0


def test_analyze_endpoint_detects_high_cpu():
    with patch("app.main.psutil.cpu_percent", return_value=92), \
         patch("app.main.psutil.virtual_memory") as mock_memory, \
         patch("app.main.fetch_active_alerts", return_value=[]):

        mock_memory.return_value.percent = 60

        response = client.get("/analyze")

    assert response.status_code == 200

    data = response.json()
    incident = data["analysis"]["incidents"][0]

    assert data["analysis"]["incident_count"] == 1
    assert incident["resource"] == "CPU"
    assert incident["severity"] == "warning"


def test_analyze_endpoint_detects_critical_memory():
    with patch("app.main.psutil.cpu_percent", return_value=40), \
         patch("app.main.psutil.virtual_memory") as mock_memory, \
         patch("app.main.fetch_active_alerts", return_value=[]):

        mock_memory.return_value.percent = 96

        response = client.get("/analyze")

    assert response.status_code == 200

    data = response.json()
    incident = data["analysis"]["incidents"][0]

    assert data["analysis"]["incident_count"] == 1
    assert incident["resource"] == "Memory"
    assert incident["severity"] == "critical"


def test_analyze_endpoint_detects_multiple_incidents():
    with patch("app.main.psutil.cpu_percent", return_value=98), \
         patch("app.main.psutil.virtual_memory") as mock_memory, \
         patch("app.main.fetch_active_alerts", return_value=[]):

        mock_memory.return_value.percent = 97

        response = client.get("/analyze")

    assert response.status_code == 200

    data = response.json()

    assert data["analysis"]["status"] == "incident_detected"
    assert data["analysis"]["incident_count"] == 2

    resources = [
        incident["resource"]
        for incident in data["analysis"]["incidents"]
    ]

    assert "CPU" in resources
    assert "Memory" in resources


def test_analyze_endpoint_includes_prometheus_alerts():
    alerts = [
        {
            "labels": {
                "alertname": "HighCPUUsage",
                "severity": "warning",
            },
            "annotations": {
                "summary": "High CPU usage detected",
                "description": "CPU exceeded 85% for 1 minute.",
            },
            "state": "firing",
        }
    ]

    with patch("app.main.psutil.cpu_percent", return_value=40), \
         patch("app.main.psutil.virtual_memory") as mock_memory, \
         patch("app.main.fetch_active_alerts", return_value=alerts):

        mock_memory.return_value.percent = 60

        response = client.get("/analyze")

    assert response.status_code == 200

    data = response.json()

    assert data["prometheus_status"] == "connected"
    assert data["analysis"]["prometheus_alert_count"] == 1
    assert data["analysis"]["prometheus_alerts"][0]["alert_name"] == "HighCPUUsage"
    assert data["analysis"]["prometheus_alerts"][0]["state"] == "firing"


def test_analyze_endpoint_handles_prometheus_unavailable():
    with patch("app.main.psutil.cpu_percent", return_value=40), \
         patch("app.main.psutil.virtual_memory") as mock_memory, \
         patch(
             "app.main.fetch_active_alerts",
             side_effect=PrometheusClientError("Connection refused"),
         ):

        mock_memory.return_value.percent = 60

        response = client.get("/analyze")

    assert response.status_code == 200

    data = response.json()

    assert data["prometheus_status"] == "unavailable"
    assert data["analysis"]["status"] == "healthy"
