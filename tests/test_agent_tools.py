
import pytest

from app import agent_tools
from app.prometheus_client import PrometheusClientError


def test_prometheus_tool_returns_alert_details(monkeypatch):
    sample_alerts = [
        {
            "labels": {
                "alertname": "HighCPUUsage",
                "severity": "warning",
            },
            "annotations": {
                "summary": "High CPU usage detected",
                "description": "CPU usage exceeded 85%.",
            },
            "state": "firing",
        }
    ]

    monkeypatch.setattr(
        agent_tools,
        "fetch_active_alerts",
        lambda prometheus_url: sample_alerts,
    )

    result = agent_tools.get_prometheus_alerts()

    assert result["status"] == "success"
    assert result["alert_count"] == 1
    assert result["alerts"][0]["alert_name"] == "HighCPUUsage"


def test_prometheus_tool_handles_no_alerts(monkeypatch):
    monkeypatch.setattr(
        agent_tools,
        "fetch_active_alerts",
        lambda prometheus_url: [],
    )

    result = agent_tools.get_prometheus_alerts()

    assert result["status"] == "success"
    assert result["alert_count"] == 0
    assert result["alerts"] == []


def test_prometheus_tool_handles_unavailable_service(monkeypatch):
    def raise_error(prometheus_url):
        raise PrometheusClientError("Connection refused")

    monkeypatch.setattr(
        agent_tools,
        "fetch_active_alerts",
        raise_error,
    )

    result = agent_tools.get_prometheus_alerts()

    assert result["status"] == "unavailable"
    assert result["alert_count"] is None
    assert result["alerts"] == []


def test_prometheus_tool_handles_malformed_alert(monkeypatch):
    sample_alerts = [
        "invalid alert",
        {
            "labels": "invalid labels",
            "annotations": None,
            "state": "pending",
        },
    ]

    monkeypatch.setattr(
        agent_tools,
        "fetch_active_alerts",
        lambda prometheus_url: sample_alerts,
    )

    result = agent_tools.get_prometheus_alerts()

    assert result["status"] == "success"
    assert result["alert_count"] == 1
    assert result["alerts"][0]["alert_name"] == "Unknown"
