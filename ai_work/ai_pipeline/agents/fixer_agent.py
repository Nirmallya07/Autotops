"""Fixer agent facade; policy and executor remain deterministic."""
from ai_work.ai_pipeline.fixer.proposal import RemediationProposal
from ai_work.ai_pipeline.fixer.orchestrator import RemediationOrchestrator


class FixerAgent:
    def __init__(self, orchestrator=None):
        self.proposer = RemediationProposal()
        self.orchestrator = orchestrator or RemediationOrchestrator()

    def propose(self, incident, diagnosis):
        return self.proposer.create(incident, diagnosis)

    def decide_and_execute(self, proposal, context):
        return self.orchestrator.run(proposal, context)
