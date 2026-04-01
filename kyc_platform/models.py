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
    sector: str = ""


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

    def completed_agents(self) -> list:
        return list(self.results.keys())

    def all_findings_text(self) -> str:
        """Return all collected findings as a single formatted string."""
        parts = []
        for name, findings in self.results.items():
            label = name.upper().replace("_", " ")
            parts.append(f"{'='*60}\n## {label}\n{'='*60}\n{findings}")
        return "\n\n".join(parts)
