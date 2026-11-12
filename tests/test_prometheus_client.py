import json
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest

from app.prometheus_client import (
    PrometheusClientError,
    fetch_active_alerts,
)


def test_fetch_active_alerts_success():
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "status": "success",
        "data": {
            "alerts": [
                {
                    "labels": {"alertname": "HighCPUUsage"},
                    "state": "firing",
                }
            ]
        },
    }).encode("utf-8")

    with patch("app.prometheus_client.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        alerts = fetch_active_alerts()

    assert len(alerts) == 1
    assert alerts[0]["labels"]["alertname"] == "HighCPUUsage"
    assert alerts[0]["state"] == "firing"


def test_fetch_active_alerts_empty():
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "status": "success",
        "data": {"alerts": []},
    }).encode("utf-8")

    with patch("app.prometheus_client.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        alerts = fetch_active_alerts()

    assert alerts == []


def test_fetch_active_alerts_connection_error():
    with patch(
        "app.prometheus_client.urlopen",
        side_effect=URLError("Connection refused"),
    ):
        with pytest.raises(PrometheusClientError):
            fetch_active_alerts()


def test_fetch_active_alerts_unsuccessful_response():
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "status": "error",
        "error": "Internal server error",
    }).encode("utf-8")

    with patch("app.prometheus_client.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(PrometheusClientError):
            fetch_active_alerts()


def test_fetch_active_alerts_invalid_json():
    mock_response = MagicMock()
    mock_response.read.return_value = b"invalid json"

    with patch("app.prometheus_client.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(PrometheusClientError):
            fetch_active_alerts()


def test_fetch_active_alerts_invalid_top_level_structure():
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps([
        "unexpected",
        "list",
    ]).encode("utf-8")

    with patch("app.prometheus_client.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(PrometheusClientError):
            fetch_active_alerts()


def test_fetch_active_alerts_invalid_nested_structure():
    mock_response = MagicMock()
    mock_response.read.return_value = json.dumps({
        "status": "success",
        "data": ["unexpected", "list"],
    }).encode("utf-8")

    with patch("app.prometheus_client.urlopen") as mock_urlopen:
        mock_urlopen.return_value.__enter__.return_value = mock_response

        with pytest.raises(PrometheusClientError):
            fetch_active_alerts()
