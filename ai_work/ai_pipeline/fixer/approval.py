from typing import Any, Dict


class ApprovalManager:
    """Record explicit approval or rejection of a remediation proposal."""

    def approve(
        self,
        proposal: Dict[str, Any],
        approved_by: str,
    ) -> Dict[str, Any]:
        if proposal.get("status") != "PROPOSED":
            raise ValueError("Only PROPOSED remediation proposals can be approved.")

        if not isinstance(approved_by, str) or not approved_by.strip():
            raise ValueError("A non-empty approver identity is required.")

        approved_proposal = proposal.copy()
        approved_proposal["status"] = "APPROVED"
        approved_proposal["approved_by"] = approved_by.strip()
        approved_proposal["approval_required"] = True
        return approved_proposal

    def reject(
        self,
        proposal: Dict[str, Any],
        rejected_by: str,
    ) -> Dict[str, Any]:
        if proposal.get("status") != "PROPOSED":
            raise ValueError("Only PROPOSED remediation proposals can be rejected.")

        if not isinstance(rejected_by, str) or not rejected_by.strip():
            raise ValueError("A non-empty reviewer identity is required.")

        rejected_proposal = proposal.copy()
        rejected_proposal["status"] = "REJECTED"
        rejected_proposal["approved_by"] = rejected_by.strip()
        rejected_proposal["approval_required"] = True
        return rejected_proposal
