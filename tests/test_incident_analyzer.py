
from app.incident_analyzer import analyze_incident


def test_healthy_system():
    result = analyze_incident(40, 60)

    assert result["status"] == "healthy"
    assert result["incident_count"] == 0
    assert result["incidents"] == []


def test_high_cpu_warning():
    result = analyze_incident(90, 60)

    assert result["status"] == "incident_detected"
    assert result["incident_count"] == 1
    assert result["incidents"][0]["resource"] == "CPU"
    assert result["incidents"][0]["severity"] == "warning"


def test_critical_cpu():
    result = analyze_incident(98, 60)

    assert result["incidents"][0]["severity"] == "critical"


def test_high_memory_warning():
    result = analyze_incident(40, 93)

    assert result["incident_count"] == 1
    assert result["incidents"][0]["resource"] == "Memory"
    assert result["incidents"][0]["severity"] == "warning"


def test_multiple_critical_incidents():
    result = analyze_incident(98, 97)

    assert result["status"] == "incident_detected"
    assert result["incident_count"] == 2

    resources = [incident["resource"] for incident in result["incidents"]]

    assert "CPU" in resources
    assert "Memory" in resources


def test_analyzer_includes_prometheus_alerts():
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

    result = analyze_incident(40, 60, alerts)

    assert result["status"] == "incident_detected"
    assert result["incident_count"] == 0
    assert result["prometheus_alert_count"] == 1
    assert result["prometheus_alerts"][0]["alert_name"] == "HighCPUUsage"
    assert result["prometheus_alerts"][0]["state"] == "firing"


def test_analyzer_without_prometheus_alerts():
    result = analyze_incident(40, 60)

    assert result["status"] == "healthy"
    assert result["prometheus_alert_count"] == 0
    assert result["prometheus_alerts"] == []
