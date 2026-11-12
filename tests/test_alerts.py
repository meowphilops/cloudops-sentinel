
from app.alerts import CPUAlertTracker


def test_warning_after_three_consecutive_high_readings():
    tracker = CPUAlertTracker()

    assert tracker.evaluate(91)["status"] == "normal"
    assert tracker.evaluate(88)["status"] == "normal"
    assert tracker.evaluate(93)["status"] == "warning"


def test_counter_resets_when_cpu_returns_below_threshold():
    tracker = CPUAlertTracker()

    tracker.evaluate(91)
    tracker.evaluate(88)

    result = tracker.evaluate(70)

    assert result["status"] == "normal"
    assert tracker.consecutive_high_count == 0


def test_exact_threshold_does_not_trigger_alert():
    tracker = CPUAlertTracker()

    result = tracker.evaluate(85)

    assert result["status"] == "normal"
    assert tracker.consecutive_high_count == 0

