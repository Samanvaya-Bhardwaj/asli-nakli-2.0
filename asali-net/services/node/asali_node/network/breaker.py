"""Stop asking a node that keeps failing: after two failures in a row, skip it for 30 seconds."""

from dataclasses import dataclass, field

FAILURES_TO_OPEN = 2
SKIP_SECONDS = 30.0


@dataclass
class Breaker:
    failures: dict[str, int] = field(default_factory=dict)
    skip_until: dict[str, float] = field(default_factory=dict)

    def is_open(self, org_id: str, now: float) -> bool:
        return now < self.skip_until.get(org_id, 0.0)

    def record_success(self, org_id: str) -> None:
        self.failures.pop(org_id, None)
        self.skip_until.pop(org_id, None)

    def record_failure(self, org_id: str, now: float) -> None:
        self.failures[org_id] = self.failures.get(org_id, 0) + 1
        if self.failures[org_id] >= FAILURES_TO_OPEN:
            self.skip_until[org_id] = now + SKIP_SECONDS
            self.failures[org_id] = 0
