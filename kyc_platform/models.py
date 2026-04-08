"""Shared data models for the KYC platform."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict


@dataclass
class CaseContext:
    """Basic information about the case under analysis."""
    company_name: str = ""
    country: str = ""
    case_id: str = ""


@dataclass
class SessionState:
    """Accumulates results across all agents in a session."""
    case: CaseContext = field(default_factory=CaseContext)
    results: Dict[str, str] = field(default_factory=dict)
    started_at: datetime = field(default_factory=datetime.now)

    def add_result(self, agent_name: str, text: str) -> None:
        self.results[agent_name] = text

    def has_result(self, agent_name: str) -> bool:
        return bool(self.results.get(agent_name))
