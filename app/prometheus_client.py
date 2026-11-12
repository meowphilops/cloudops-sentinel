import json
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


class PrometheusClientError(Exception):
    """Raised when Prometheus cannot provide alert information."""


def fetch_active_alerts(
    prometheus_url="http://prometheus:9090",
    timeout=3,
):
    """Fetch active and pending alerts from Prometheus."""

    endpoint = f"{prometheus_url.rstrip('/')}/api/v1/alerts"

    try:
        with urlopen(endpoint, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))

    except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError) as error:
        raise PrometheusClientError(
            f"Unable to retrieve alerts from Prometheus: {error}"
        ) from error

    # Validate the top-level JSON structure
    if not isinstance(data, dict):
        raise PrometheusClientError(
            "Invalid response format received from Prometheus."
        )

    if data.get("status") != "success":
        raise PrometheusClientError(
            "Prometheus returned an unsuccessful response."
        )

    # Validate the nested data structure
    response_data = data.get("data")

    if not isinstance(response_data, dict):
        raise PrometheusClientError(
            "Invalid alert data received from Prometheus."
        )

    alerts = response_data.get("alerts")

    if not isinstance(alerts, list):
        raise PrometheusClientError(
            "Invalid alert data received from Prometheus."
        )

    return alerts
