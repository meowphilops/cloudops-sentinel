
def analyze_incident(cpu_percent, memory_percent, prometheus_alerts=None):
    """Analyze system metrics and Prometheus alerts."""

    incidents = []
    prometheus_findings = []

    # CPU analysis
    if cpu_percent > 85:
        incidents.append({
            "resource": "CPU",
            "severity": "critical" if cpu_percent > 95 else "warning",
            "observed_value": cpu_percent,
            "summary": "CPU utilization is above the configured threshold.",
            "possible_causes": [
                "High application workload",
                "CPU-intensive background processes",
                "Unexpected traffic spike",
            ],
            "investigation_steps": [
                "Identify processes consuming the most CPU.",
                "Check application logs for unusual activity.",
                "Inspect recent traffic and workload changes.",
            ],
            "recommended_actions": [
                "Investigate high CPU-consuming processes.",
                "Review application workload and resource limits.",
                "Consider scaling if sustained demand exceeds capacity.",
            ],
        })

    # Memory analysis
    if memory_percent > 90:
        incidents.append({
            "resource": "Memory",
            "severity": "critical" if memory_percent > 95 else "warning",
            "observed_value": memory_percent,
            "summary": "Memory utilization is above the configured threshold.",
            "possible_causes": [
                "Memory-intensive application workload",
                "Possible memory leak",
                "Insufficient available memory",
            ],
            "investigation_steps": [
                "Identify processes consuming the most memory.",
                "Inspect application memory trends.",
                "Check system logs for out-of-memory events.",
            ],
            "recommended_actions": [
                "Investigate memory-heavy processes.",
                "Check for potential memory leaks.",
                "Consider increasing available memory if justified.",
            ],
        })

    # Prometheus alert analysis
    for alert in prometheus_alerts or []:
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})

        prometheus_findings.append({
            "source": "Prometheus",
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

    has_findings = bool(incidents or prometheus_findings)

    return {
        "status": "incident_detected" if has_findings else "healthy",
        "incident_count": len(incidents),
        "prometheus_alert_count": len(prometheus_findings),
        "incidents": incidents,
        "prometheus_alerts": prometheus_findings,
    }
