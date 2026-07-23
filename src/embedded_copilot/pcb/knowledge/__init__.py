"""Explicitly injected PCB rule knowledge interfaces."""

from embedded_copilot.pcb.knowledge.models import PCBRuleDocument
from embedded_copilot.pcb.knowledge.retriever import PCBKnowledgeRetriever

__all__ = ["PCBKnowledgeRetriever", "PCBRuleDocument"]
