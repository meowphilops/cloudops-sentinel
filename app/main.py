import psutil
from fastapi import FastAPI
from fastapi.responses import Response
from app.incident_analyzer import analyze_incident
from prometheus_client import Gauge, generate_latest, CONTENT_TYPE_LATEST
from app.prometheus_client import (
    fetch_active_alerts,
    PrometheusClientError,
)
from app.alerts import CPUAlertTracker

app = FastAPI(
    title="CloudOps Sentinel",
    description="Infrastructure health and diagnostics API",
    version="1.0.0",
)

cpu_alert_tracker = CPUAlertTracker()

# Prometheus metrics
cpu_usage = Gauge(
    "cloudops_cpu_usage_percent",
    "Current CPU usage percentage",
)

memory_usage = Gauge(
    "cloudops_memory_usage_percent",
    "Current memory usage percentage",
)

memory_used = Gauge(
    "cloudops_memory_used_bytes",
    "Amount of memory currently used in bytes",
)

memory_available = Gauge(
    "cloudops_memory_available_bytes",
    "Amount of available memory in bytes",
)


@app.get("/")
def root():
    return {
        "project": "CloudOps Sentinel",
        "status": "running",
    }


@app.get("/health")
def health_check():
    return {"status": "healthy"}


@app.get("/metrics/system")
def system_metrics():
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()

    alert = cpu_alert_tracker.evaluate(cpu_percent)

    return {
        "cpu_percent": cpu_percent,
        "memory": {
            "total_mb": round(memory.total / (1024 ** 2), 2),
            "used_mb": round(memory.used / (1024 ** 2), 2),
            "available_mb": round(memory.available / (1024 ** 2), 2),
            "percent": memory.percent,
        },
        "alert": alert,
    }

@app.get("/analyze")
def analyze_system():
    # Collect local system metrics
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()

    # Fetch alerts from Prometheus
    prometheus_status = "connected"

    try:
        prometheus_alerts = fetch_active_alerts()

    except PrometheusClientError:
        prometheus_alerts = []
        prometheus_status = "unavailable"

    # Generate combined diagnostic report
    report = analyze_incident(
        cpu_percent=cpu_percent,
        memory_percent=memory.percent,
        prometheus_alerts=prometheus_alerts,
    )

    return {
        "project": "CloudOps Sentinel",
        "prometheus_status": prometheus_status,
        "analysis": report,
    }

@app.get("/metrics")
def prometheus_metrics():
    cpu_percent = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()

    cpu_usage.set(cpu_percent)
    memory_usage.set(memory.percent)
    memory_used.set(memory.used)
    memory_available.set(memory.available)

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
  
