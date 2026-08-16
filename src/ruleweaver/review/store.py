"""Durable storage for the review log.

The audit trail is the deployed artifact that matters. ADR-022's position — a
deterministic runtime defensible under GDPR Art. 22 — depends on being able to show who
approved which rule, when, and against which version of the source. A log that can be
edited, or that loses a write when a request half-fails, does not support that claim.

Three properties are enforced here rather than hoped for:

- **Append-only.** No update or delete path exists on review events. Superseding a
  decision means appending another one.
- **Atomic.** A decision and its audit row are the same row, written in one transaction.
  There is no window where a rule is approved but the approval is unrecorded.
- **Hash-chained.** Each event carries the digest of its predecessor, so a row deleted or
  altered directly in the database breaks the chain and `verify_chain` reports where.

SQLite by default per ADR-015; PostgreSQL by setting `RULEWEAVER_DATABASE_URL`. Same code
either way — the choice is a deployment decision, not a rewrite.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
    select,
)
from sqlalchemy.engine import Engine

from .decisions import Decision, ReviewEvent, ReviewLog

DEFAULT_URL = "sqlite:///ruleweaver-review.db"

metadata = MetaData()

review_events = Table(
    "review_events", metadata,
    # Monotonic ordering independent of clock skew across app instances.
    Column("seq", Integer, primary_key=True, autoincrement=True),
    Column("id", String(64), nullable=False, unique=True),
    Column("rule_id", String(256), nullable=False, index=True),
    Column("reviewer", String(256), nullable=False),
    Column("decision", String(64), nullable=False),
    Column("rule_hash", String(128), nullable=False),
    Column("source_hash", String(128), nullable=False),
    Column("at", String(64), nullable=False),
    Column("duration_seconds", Float, nullable=True),
    Column("note", Text, nullable=True),
    Column("edited_to", Text, nullable=True),
    Column("seeded_error_id", String(64), nullable=True, index=True),
    # Tamper evidence: digest of (previous chain value + this row's content).
    Column("prev_hash", String(128), nullable=False),
    Column("chain_hash", String(128), nullable=False),
    Column("recorded_at", DateTime(timezone=True), server_default=func.now()),
)

seeded_errors = Table(
    "seeded_errors", metadata,
    Column("id", String(64), primary_key=True),
    Column("rule_id", String(256), nullable=False, index=True),
    Column("description", Text, nullable=False),
    Column("mutated_rule", Text, nullable=False),
    Column("expected_decision", String(64), nullable=False),
    Column("seeded_at", String(64), nullable=False),
)

GENESIS = "0" * 64


def _digest_fields(
    *, id: str, rule_id: str, reviewer: str, decision: str, rule_hash: str,
    source_hash: str, at: str, note: str | None, edited_to: str | None,
    seeded_error_id: str | None,
) -> str:
    """Hash of the fields that must not change after the fact.

    Deliberately takes primitives, not a ReviewEvent. Verification has to work on what is
    actually stored: a tampered row may no longer satisfy the domain invariants, and a
    verifier that reconstructs objects would raise on exactly the rows it exists to
    catch. `edited_to` is hashed as its stored JSON string so re-serialisation cannot
    shift the digest.
    """
    payload = json.dumps(
        {
            "id": id, "rule_id": rule_id, "reviewer": reviewer, "decision": decision,
            "rule_hash": rule_hash, "source_hash": source_hash, "at": at,
            "note": note, "edited_to": edited_to, "seeded_error_id": seeded_error_id,
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _chain_from_fields(prev_hash: str, content_digest: str) -> str:
    return hashlib.sha256(f"{prev_hash}{content_digest}".encode()).hexdigest()


def build_engine(url: str | None = None) -> Engine:
    url = url or os.environ.get("RULEWEAVER_DATABASE_URL") or DEFAULT_URL
    # future=True keeps SQLAlchemy 2.x semantics explicit rather than inherited.
    engine = create_engine(url, future=True)
    metadata.create_all(engine)
    return engine


class ReviewStore:
    """Append-only, hash-chained persistence for review decisions."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    @contextmanager
    def _connect(self) -> Iterator:
        with self.engine.begin() as conn:  # begin() commits on exit, rolls back on error
            yield conn

    def _head(self, conn) -> str:
        row = conn.execute(
            select(review_events.c.chain_hash).order_by(review_events.c.seq.desc()).limit(1)
        ).first()
        return row[0] if row else GENESIS

    def append(self, event: ReviewEvent) -> str:
        """Record a decision. Returns the new chain head.

        The decision and its audit row are one row in one transaction — there is no
        state in which a rule is approved but the approval is unrecorded.
        """
        edited_to = json.dumps(event.edited_to) if event.edited_to else None
        with self._connect() as conn:
            prev = self._head(conn)
            content = _digest_fields(
                id=event.id, rule_id=event.rule_id, reviewer=event.reviewer,
                decision=event.decision.value, rule_hash=event.rule_hash,
                source_hash=event.source_hash, at=event.at, note=event.note,
                edited_to=edited_to, seeded_error_id=event.seeded_error_id,
            )
            chain_hash = _chain_from_fields(prev, content)
            conn.execute(review_events.insert().values(
                id=event.id,
                rule_id=event.rule_id,
                reviewer=event.reviewer,
                decision=event.decision.value,
                rule_hash=event.rule_hash,
                source_hash=event.source_hash,
                at=event.at,
                duration_seconds=event.duration_seconds,
                note=event.note,
                edited_to=edited_to,
                seeded_error_id=event.seeded_error_id,
                prev_hash=prev,
                chain_hash=chain_hash,
            ))
            return chain_hash

    def _row_to_event(self, row) -> ReviewEvent:
        return ReviewEvent(
            id=row.id,
            rule_id=row.rule_id,
            reviewer=row.reviewer,
            decision=Decision(row.decision),
            rule_hash=row.rule_hash,
            source_hash=row.source_hash,
            at=row.at,
            duration_seconds=row.duration_seconds,
            note=row.note,
            edited_to=json.loads(row.edited_to) if row.edited_to else None,
            seeded_error_id=row.seeded_error_id,
        )

    def events(self, rule_id: str | None = None) -> list[ReviewEvent]:
        query = select(review_events).order_by(review_events.c.seq)
        if rule_id is not None:
            query = query.where(review_events.c.rule_id == rule_id)
        with self.engine.connect() as conn:
            return [self._row_to_event(r) for r in conn.execute(query)]

    def load_log(self) -> ReviewLog:
        """Rehydrate the in-memory log used by the status and metrics logic."""
        log = ReviewLog()
        for event in self.events():
            log.append(event)
        return log

    def verify_chain(self) -> tuple[bool, str | None]:
        """Recompute the chain. Returns (intact, first_broken_event_id).

        A row altered or removed with direct database access breaks every link after it,
        so this reports the earliest point where the record stops being trustworthy.
        """
        query = select(review_events).order_by(review_events.c.seq)
        prev = GENESIS
        with self.engine.connect() as conn:
            for row in conn.execute(query):
                content = _digest_fields(
                    id=row.id, rule_id=row.rule_id, reviewer=row.reviewer,
                    decision=row.decision, rule_hash=row.rule_hash,
                    source_hash=row.source_hash, at=row.at, note=row.note,
                    edited_to=row.edited_to, seeded_error_id=row.seeded_error_id,
                )
                expected = _chain_from_fields(prev, content)
                if row.prev_hash != prev or row.chain_hash != expected:
                    return False, row.id
                prev = row.chain_hash
        return True, None

    # ---------- seeded errors ----------

    def record_seed(self, error) -> None:
        with self._connect() as conn:
            conn.execute(seeded_errors.insert().values(
                id=error.id,
                rule_id=error.rule_id,
                description=error.description,
                mutated_rule=json.dumps(error.mutated_rule),
                expected_decision=error.expected_decision.value,
                seeded_at=error.seeded_at,
            ))

    def seeds(self) -> list[dict]:
        with self.engine.connect() as conn:
            return [
                {
                    "id": r.id,
                    "rule_id": r.rule_id,
                    "description": r.description,
                    "mutated_rule": json.loads(r.mutated_rule),
                    "expected_decision": r.expected_decision,
                    "seeded_at": r.seeded_at,
                }
                for r in conn.execute(select(seeded_errors))
            ]
