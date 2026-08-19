"""Review decisions as an append-only log.

ADR-004 makes human approval the gate a rule must pass before it can execute, so the
record of that approval is the audit trail — and an audit trail held in mutable state is
not an audit trail. Every decision is an immutable event; approval status is *derived*
from the log rather than stored alongside it.

Two consequences fall out of that choice:

- An approval can be superseded but never erased, so "who approved this, when, and on
  what version of the source" always has an answer.
- A rule whose source or dependencies changed since approval goes stale automatically,
  because staleness is computed from hashes in the log rather than remembered by a flag
  someone has to update.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class Decision(StrEnum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"
    MARK_AMBIGUOUS = "mark_ambiguous"
    HUMAN_JUDGMENT_REQUIRED = "human_judgment_required"
    REQUEST_SOURCE_CLARIFICATION = "request_source_clarification"


class Status(StrEnum):
    """Derived from the log — never assigned directly."""

    UNREVIEWED = "unreviewed"
    APPROVED = "approved"
    REJECTED = "rejected"
    AMBIGUOUS = "ambiguous"
    HUMAN_JUDGMENT_REQUIRED = "human_judgment_required"
    STALE = "stale"


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class ReviewEvent:
    """One reviewer action. Immutable by construction."""

    rule_id: str
    reviewer: str
    decision: Decision
    # What the reviewer actually saw. An approval of a rule they never read is not an
    # approval, and without this the distinction is unrecoverable after the fact.
    rule_hash: str
    source_hash: str
    at: str = field(default_factory=_now)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    # Seconds from the rule being displayed to the decision being submitted. ADR-021
    # needs this: a median review time of four seconds is a rubber stamp, and no other
    # signal reveals it.
    duration_seconds: float | None = None
    note: str | None = None
    edited_to: dict | None = None
    # Set when this decision resolved a deliberately seeded error.
    seeded_error_id: str | None = None

    def __post_init__(self) -> None:
        if self.decision == Decision.EDIT and self.edited_to is None:
            raise ValueError("an edit decision must carry the edited rule")
        if self.decision in (Decision.REJECT, Decision.MARK_AMBIGUOUS) and not self.note:
            raise ValueError(
                f"{self.decision.value} requires a note — an unexplained rejection "
                "tells the next reviewer nothing"
            )


class ReviewLog:
    """Append-only store of review events."""

    def __init__(self) -> None:
        self._events: list[ReviewEvent] = []

    def append(self, event: ReviewEvent) -> ReviewEvent:
        self._events.append(event)
        return event

    @property
    def events(self) -> list[ReviewEvent]:
        return list(self._events)

    def events_for(self, rule_id: str) -> list[ReviewEvent]:
        return [e for e in self._events if e.rule_id == rule_id]

    def latest_for(self, rule_id: str) -> ReviewEvent | None:
        events = self.events_for(rule_id)
        return events[-1] if events else None

    def status(self, rule_id: str, *, rule_hash: str, source_hash: str) -> Status:
        """Current status, derived — including staleness.

        `rule_hash` and `source_hash` are the *current* values. If either differs from
        what the approving reviewer saw, the approval no longer applies.
        """
        latest = self.latest_for(rule_id)
        if latest is None:
            return Status.UNREVIEWED

        if latest.decision in (Decision.APPROVE, Decision.EDIT):
            if latest.rule_hash != rule_hash or latest.source_hash != source_hash:
                return Status.STALE
            return Status.APPROVED
        if latest.decision == Decision.REJECT:
            return Status.REJECTED
        if latest.decision == Decision.MARK_AMBIGUOUS:
            return Status.AMBIGUOUS
        if latest.decision == Decision.HUMAN_JUDGMENT_REQUIRED:
            return Status.HUMAN_JUDGMENT_REQUIRED
        return Status.UNREVIEWED

    def approved_rules(self, current: dict[str, tuple[str, str]]) -> set[str]:
        """Rule ids that may execute.

        `current` maps rule id to its (rule_hash, source_hash) as they are *now*, so a
        rule whose source moved under it is excluded without anyone remembering to.
        """
        return {
            rid for rid, (rh, sh) in current.items()
            if self.status(rid, rule_hash=rh, source_hash=sh) is Status.APPROVED
        }

    def reviewers_of(self, rule_id: str) -> list[str]:
        return [e.reviewer for e in self.events_for(rule_id)]
