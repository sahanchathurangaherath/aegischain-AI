from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class BlackboardEntry:
    agent: str
    key: str
    value: Any
    confidence: float
    source: str
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class Blackboard:
    """
    Shared working memory for a single deliberation so agents and tools reuse
    each other's verified outputs without redundant ERP calls.
    """

    event_id: str
    entries: dict[str, BlackboardEntry] = field(default_factory=dict)

    def write(
        self,
        agent: str,
        key: str,
        value: Any,
        confidence: float = 1.0,
        source: str = "live_erp",
    ) -> None:
        self.entries[key] = BlackboardEntry(
            agent=agent,
            key=key,
            value=value,
            confidence=confidence,
            source=source,
        )

    def read(self, key: str) -> BlackboardEntry | None:
        return self.entries.get(key)

    def snapshot(self) -> dict[str, Any]:
        return {
            key: {
                "agent": entry.agent,
                "value": entry.value,
                "confidence": entry.confidence,
                "source": entry.source,
                "updated_at": entry.updated_at,
            }
            for key, entry in self.entries.items()
        }
