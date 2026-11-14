
import pytest

from app.remediation import (
    RemediationManager,
    RemediationNotFoundError,
    RemediationStateError,
    RemediationExecutionError,
)


def test_create_pending_proposal():
    manager = RemediationManager()

    proposal = manager.propose(
        "restart_demo_service",
        "Demo service requires a restart.",
    )

    assert proposal["status"] == "pending"
    assert proposal["action"] == "restart_demo_service"
    assert proposal["result"] is None


def test_reject_unknown_action():
    manager = RemediationManager()

    with pytest.raises(ValueError, match="not allowed"):
        manager.propose(
            "execute_arbitrary_command",
            "Invalid action.",
        )


def test_reject_empty_reason():
    manager = RemediationManager()

    with pytest.raises(ValueError, match="reason is required"):
        manager.propose("restart_demo_service", "  ")


def test_get_pending_proposals():
    manager = RemediationManager()

    manager.propose(
        "restart_demo_service",
        "Demo service restart.",
    )

    assert len(manager.get_pending()) == 1


def test_approve_executes_remediation(monkeypatch):
    import app.remediation as remediation

    manager = RemediationManager()

    proposal = manager.propose(
        "restart_demo_service",
        "Testing approval.",
    )

    monkeypatch.setattr(
        remediation,
        "ALLOWED_REMEDIATIONS",
        {
            "restart_demo_service": lambda: {
                "status": "success",
                "execution_mode": "test",
            }
        },
    )

    result = manager.approve(proposal["id"])

    assert result["status"] == "executed"
    assert result["result"]["status"] == "success"


def test_reject_proposal():
    manager = RemediationManager()

    proposal = manager.propose(
        "restart_demo_service",
        "Testing rejection.",
    )

    result = manager.reject(proposal["id"])

    assert result["status"] == "rejected"


def test_cannot_approve_proposal_twice():
    manager = RemediationManager()

    proposal = manager.propose(
        "restart_demo_service",
        "Testing duplicate approval.",
    )

    manager.approve(proposal["id"])

    with pytest.raises(RemediationStateError):
        manager.approve(proposal["id"])


def test_cannot_execute_rejected_proposal():
    manager = RemediationManager()

    proposal = manager.propose(
        "restart_demo_service",
        "Testing rejected proposal.",
    )

    manager.reject(proposal["id"])

    with pytest.raises(RemediationStateError):
        manager.approve(proposal["id"])


def test_unknown_proposal():
    manager = RemediationManager()

    with pytest.raises(RemediationNotFoundError):
        manager.approve("unknown-id")


def test_execution_failure(monkeypatch):
    import app.remediation as remediation

    manager = RemediationManager()

    proposal = manager.propose(
        "restart_demo_service",
        "Testing execution failure.",
    )

    def failing_action():
        raise RuntimeError("Simulated failure")

    monkeypatch.setattr(
        remediation,
        "ALLOWED_REMEDIATIONS",
        {"restart_demo_service": failing_action},
    )

    with pytest.raises(RemediationExecutionError):
        manager.approve(proposal["id"])

    assert manager.proposals[proposal["id"]]["status"] == "failed"


def test_concurrent_approval_executes_action_only_once(monkeypatch):
    import threading
    import app.remediation as remediation

    manager = RemediationManager()

    proposal = manager.propose(
        "restart_demo_service",
        "Testing concurrent approval.",
    )

    action_started = threading.Event()
    allow_action_to_finish = threading.Event()
    execution_count = 0

    def slow_action():
        nonlocal execution_count
        execution_count += 1
        action_started.set()
        allow_action_to_finish.wait(timeout=2)

        return {"status": "success"}

    monkeypatch.setattr(
        remediation,
        "ALLOWED_REMEDIATIONS",
        {"restart_demo_service": slow_action},
    )

    results = []

    def first_approval():
        results.append(manager.approve(proposal["id"]))

    worker = threading.Thread(target=first_approval)
    worker.start()

    try:
        assert action_started.wait(timeout=2)

        with pytest.raises(RemediationStateError):
            manager.approve(proposal["id"])

    finally:
        allow_action_to_finish.set()
        worker.join(timeout=3)

    assert not worker.is_alive()
    assert execution_count == 1
    assert len(results) == 1
    assert results[0]["status"] == "executed"
