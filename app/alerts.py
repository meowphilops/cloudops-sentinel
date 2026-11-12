class CPUAlertTracker:
    def __init__(self, threshold=85, required_readings=3):
        self.threshold = threshold
        self.required_readings = required_readings
        self.consecutive_high_count = 0


    def evaluate(self, cpu_percent):
        if cpu_percent > self.threshold:
            self.consecutive_high_count +=1
        else: 
            self.consecutive_high_count = 0

        if self.consecutive_high_count >= self.required_readings:
            return {
                    "status": "warning",
                    "message": "CPU usage exceeded the threshold for 3 consecutive readings.",
                    "cpu_percent": cpu_percent,
            }

        return {
                "status": "normal",
            "message": "CPU usage is within the alert rule.",
            "cpu_percent": cpu_percent,
        }



