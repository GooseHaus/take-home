from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ResolvedIngest:
    """An ingest request with every default filled in."""

    start: date
    end: date
    threshold_pct: float
    max_movements: int
    refresh: bool

    def as_params(self) -> dict:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "threshold_pct": self.threshold_pct,
            "max_movements": self.max_movements,
            "refresh": self.refresh,
        }
