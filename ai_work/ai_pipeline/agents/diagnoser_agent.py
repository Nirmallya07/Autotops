"""Diagnoser agent: evidence-grounded diagnosis with optional incident memory."""
from ai_work.ai_pipeline.diagnoser.context import DiagnosticContext
from ai_work.ai_pipeline.diagnoser.validator import DiagnosisValidator


class DiagnoserAgent:
    def __init__(self, diagnoser, memory=None):
        self.diagnoser = diagnoser
        self.memory = memory

    def run(self, incident):
        context = DiagnosticContext().build(incident)
        similar = self.memory.retrieve(incident) if self.memory else []
        context["historical_incidents"] = similar
        diagnosis = self.diagnoser.diagnose(context)
        diagnosis = DiagnosisValidator().validate(diagnosis, context)
        return diagnosis, similar
