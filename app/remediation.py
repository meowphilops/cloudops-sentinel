import threading
import uuid


class RemediationError(Exception):
    """Base exception for remediation operations."""


class RemediationNotFoundError(RemediationError):
    """Raised when a remediation proposal does not exist."""


class RemediationStateError(RemediationError):
    """Raised when a proposal is not in the required state."""


class RemediationExecutionError(RemediationError):
    """Raised when a remediation action fails."""


def simulate_demo_service_restart():
    """
    Simulate restarting a controlled demo service.

    Does not execute shell commands or restart actual services.
    """

    return {
        "status": "success",
        "action": "restart_demo_service",
        "execution_mode": "simulated",
        "message": "Demo service restart simulated successfully.",
    }


ALLOWED_REMEDIATIONS = {
    "restart_demo_service": simulate_demo_service_restart,
}


class RemediationManager:
    """Manage remediation proposals and human-approved execution."""

    def __init__(self):
        self.proposals = {}
        self.lock = threading.Lock()

    def propose(self, action, reason):
        """Create a pending proposal for an allowlisted action."""

        if action not in ALLOWED_REMEDIATIONS:
            raise ValueError(
                f"Remediation action '{action}' is not allowed."
            )

        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("A valid reason is required.")

        proposal = {
            "id": str(uuid.uuid4()),
            "action": action,
            "reason": reason.strip(),
            "status": "pending",
            "result": None,
        }

        with self.lock:
            self.proposals[proposal["id"]] = proposal

        return proposal.copy()

    def get_pending(self):
        """Return proposals awaiting human approval."""

        with self.lock:
            return [
                proposal.copy()
                for proposal in self.proposals.values()
                if proposal["status"] == "pending"
            ]

    def approve(self, proposal_id):
        """Approve and execute a pending remediation proposal."""

        # Claim the proposal while holding the lock.
        with self.lock:
            proposal = self.proposals.get(proposal_id)

            if proposal is None:
                raise RemediationNotFoundError(
                    "Remediation proposal not found."
                )

            if proposal["status"] != "pending":
                raise RemediationStateError(
                    "Only pending proposals can be approved."
                )

            handler = ALLOWED_REMEDIATIONS[proposal["action"]]

            proposal["status"] = "executing"

        # Execute outside the lock.
        try:
            result = handler()

        except Exception as error:
            with self.lock:
                proposal["status"] = "failed"
                proposal["result"] = {
                    "status": "error",
                    "message": str(error),
                }

            raise RemediationExecutionError(
                "Remediation execution failed."
            ) from error

        # Store the execution result safely.
        with self.lock:
            proposal["status"] = "executed"
            proposal["result"] = result

            return proposal.copy()

    def reject(self, proposal_id):
        """Reject a pending remediation proposal."""

        with self.lock:
            proposal = self.proposals.get(proposal_id)

            if proposal is None:
                raise RemediationNotFoundError(
                    "Remediation proposal not found."
                )

            if proposal["status"] != "pending":
                raise RemediationStateError(
                    "Only pending proposals can be rejected."
                )

            proposal["status"] = "rejected"

            return proposal.copy()
