
import os
import psutil

from app.prometheus_client import (
    fetch_active_alerts,
    PrometheusClientError,
)


def get_cpu_status():
    """Return the current CPU utilization percentage."""

    cpu_percent = psutil.cpu_percent(interval=1)

    return {
        "cpu_percent": cpu_percent,
        "unit": "percent",
        "status": "success",
    }


def get_memory_status():
    """Return the current system memory utilization."""

    memory = psutil.virtual_memory()

    return {
        "memory_percent": memory.percent,
        "total_mb": round(memory.total / (1024 ** 2), 2),
        "used_mb": round(memory.used / (1024 ** 2), 2),
        "available_mb": round(memory.available / (1024 ** 2), 2),
        "status": "success",
    }


def get_prometheus_alerts():
    """Retrieve and summarize active and pending Prometheus alerts."""

    prometheus_url = os.getenv(
        "PROMETHEUS_URL",
        "http://prometheus:9090",
    )

    try:
        alerts = fetch_active_alerts(
            prometheus_url=prometheus_url
        )

    except PrometheusClientError as error:
        return {
            "status": "unavailable",
            "alert_count": None,
            "alerts": [],
            "message": str(error),
        }

    alert_details = []

    for alert in alerts:
        if not isinstance(alert, dict):
            continue

        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})

        if not isinstance(labels, dict):
            labels = {}

        if not isinstance(annotations, dict):
            annotations = {}

        alert_details.append({
            "alert_name": labels.get("alertname", "Unknown"),
            "state": alert.get("state", "unknown"),
            "severity": labels.get("severity", "unknown"),
            "summary": annotations.get(
                "summary", "No summary provided."
            ),
            "description": annotations.get(
                "description", "No description provided."
            ),
        })

    return {
        "status": "success",
        "alert_count": len(alert_details),
        "alerts": alert_details,
    }


AVAILABLE_TOOLS = {
    "get_cpu_status": get_cpu_status,
    "get_memory_status": get_memory_status,
    "get_prometheus_alerts": get_prometheus_alerts,
}


def execute_tool(tool_name):
    """Execute an approved tool from the registry."""

    tool_function = AVAILABLE_TOOLS.get(tool_name)

    if tool_function is None:
        return {
            "status": "error",
            "message": f"Tool '{tool_name}' is not allowed.",
        }

    return tool_function()
