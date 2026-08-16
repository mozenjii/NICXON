"""Adversarial review — ADR-021.

A review queue that only ever shows correct rules measures nothing. Reviewers see a long
run of good proposals, calibrate to approving, and the gate quietly stops being a gate.

Dratsch et al. (*Radiology* 2023, DOI 10.1148/radiol.222176) put numbers on it: shown
incorrect AI suggestions, correct ratings fell from 82.3% to **45.5% among very
experienced reviewers**, and to 19.8% among inexperienced ones. Expertise attenuates
automation bias; it does not prevent it.

So the queue seeds deliberate errors at a known rate and measures how many are caught.
That number is the evidence ADR-004's approval gate is doing anything — and it doubles as
EU AI Act Art. 14 automation-bias mitigation, since benefits eligibility is high-risk
under Annex III 5(a).

Nothing here decides anything. It measures whether the humans are.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import median

from .decisions import Decision, ReviewEvent, ReviewLog


@dataclass(frozen=True)
class SeededError:
    """A deliberate fault inserted into the review queue.

    `expected_decision` is what a reviewer who spotted it should choose. Anything else —
    including an approve — counts as missed.
    """

    id: str
    rule_id: str
    description: str
    mutated_rule: dict
    expected_decision: Decision = Decision.REJECT
    seeded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


def deterministic_seed_choice(rule_id: str, rate: float, salt: str = "") -> bool:
    """Whether this rule should carry a seeded error, decided by hash.

    Deterministic rather than random so a run is reproducible and a reviewer cannot
    learn the pattern by re-opening the queue. The salt rotates per campaign.
    """
    if not 0.0 <= rate <= 1.0:
        raise ValueError("rate must be between 0 and 1")
    if rate == 0.0:
        return False
    digest = hashlib.sha256(f"{salt}:{rule_id}".encode()).digest()
    # First 4 bytes as a fraction of the space.
    position = int.from_bytes(digest[:4], "big") / 0xFFFFFFFF
    return position < rate


@dataclass
class ReviewMetrics:
    """What the queue reveals about the reviewers."""

    total_reviewed: int
    seeded_total: int
    seeded_caught: int
    approvals: int
    rejections: int
    durations: list[float]

    @property
    def catch_rate(self) -> float | None:
        """None when nothing was seeded — distinct from zero, which means all missed."""
        if self.seeded_total == 0:
            return None
        return self.seeded_caught / self.seeded_total

    @property
    def approval_rate(self) -> float | None:
        if self.total_reviewed == 0:
            return None
        return self.approvals / self.total_reviewed

    @property
    def median_duration(self) -> float | None:
        return median(self.durations) if self.durations else None

    def warnings(self, *, min_catch_rate: float = 0.8,
                 min_median_seconds: float = 20.0) -> list[str]:
        """Signs the gate has stopped working.

        Thresholds are defaults, not findings. Calibrate them against your own corpus —
        but do not raise them to silence a warning.
        """
        out: list[str] = []
        if self.catch_rate is not None and self.catch_rate < min_catch_rate:
            out.append(
                f"seeded errors caught {self.catch_rate:.0%} of the time "
                f"(below {min_catch_rate:.0%}) — review is not catching planted faults"
            )
        if self.median_duration is not None and self.median_duration < min_median_seconds:
            out.append(
                f"median review time {self.median_duration:.0f}s "
                f"(below {min_median_seconds:.0f}s) — consistent with rubber-stamping"
            )
        if self.approval_rate is not None and self.approval_rate > 0.98 and self.total_reviewed >= 20:
            out.append(
                f"approval rate {self.approval_rate:.0%} across {self.total_reviewed} "
                "reviews — a queue where nothing is ever rejected is not a gate"
            )
        return out

    def __str__(self) -> str:
        lines = [
            f"reviewed          {self.total_reviewed}",
            f"approved          {self.approvals}",
            f"rejected          {self.rejections}",
        ]
        if self.catch_rate is not None:
            lines.append(f"seeded caught     {self.seeded_caught}/{self.seeded_total} "
                         f"({self.catch_rate:.0%})")
        if self.median_duration is not None:
            lines.append(f"median duration   {self.median_duration:.0f}s")
        for warning in self.warnings():
            lines.append(f"  WARNING  {warning}")
        return "\n".join(lines)


class AdversarialQueue:
    """Tracks seeded errors and scores the review log against them."""

    def __init__(self, log: ReviewLog, *, seed_rate: float = 0.1, salt: str = "") -> None:
        self.log = log
        self.seed_rate = seed_rate
        self.salt = salt
        self._seeded: dict[str, SeededError] = {}

    def should_seed(self, rule_id: str) -> bool:
        return deterministic_seed_choice(rule_id, self.seed_rate, self.salt)

    def register(self, error: SeededError) -> SeededError:
        self._seeded[error.id] = error
        return error

    @property
    def seeded(self) -> dict[str, SeededError]:
        return dict(self._seeded)

    def was_caught(self, error_id: str) -> bool:
        """True when a reviewer resolved the seeded rule with the expected decision."""
        error = self._seeded.get(error_id)
        if error is None:
            raise KeyError(f"unknown seeded error: {error_id}")
        for event in self.log.events_for(error.rule_id):
            if event.seeded_error_id != error_id:
                continue
            return event.decision == error.expected_decision
        return False

    def metrics(self) -> ReviewMetrics:
        events = self.log.events
        resolved = [e for e in events if e.seeded_error_id]
        return ReviewMetrics(
            total_reviewed=len(events),
            seeded_total=len(self._seeded),
            seeded_caught=sum(1 for eid in self._seeded if self.was_caught(eid)),
            approvals=sum(1 for e in events if e.decision == Decision.APPROVE),
            rejections=sum(1 for e in events if e.decision == Decision.REJECT),
            durations=[e.duration_seconds for e in events if e.duration_seconds is not None],
        )

    def unresolved(self) -> list[SeededError]:
        """Seeded errors still sitting in the queue — excluded from catch rate until
        someone rules on them, so an unreviewed backlog cannot look like a miss."""
        resolved_ids = {e.seeded_error_id for e in self.log.events if e.seeded_error_id}
        return [err for eid, err in self._seeded.items() if eid not in resolved_ids]


def dual_encode_disagreements(
    log: ReviewLog, rule_ids: list[str], *, min_reviewers: int = 2
) -> list[str]:
    """Rules where independent reviewers reached different conclusions.

    The *Encoding legislation* study found three experienced coders agreed on 0% of rules
    encoded independently. Disagreement is therefore the expected case, not an anomaly —
    and the rules where it happens are exactly the ones a vocabulary or a spec is failing
    to pin down.
    """
    out: list[str] = []
    for rule_id in rule_ids:
        events = log.events_for(rule_id)
        by_reviewer: dict[str, Decision] = {}
        for event in events:
            by_reviewer[event.reviewer] = event.decision
        if len(by_reviewer) >= min_reviewers and len(set(by_reviewer.values())) > 1:
            out.append(rule_id)
    return out
