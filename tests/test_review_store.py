"""Durability and tamper-evidence of the review log.

These test the claims ADR-022 rests on. An audit trail nobody has tried to break is not
evidence of anything, so the tampering tests write directly to the database and assert
the chain notices.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from ruleweaver.review import Decision, ReviewEvent, SeededError, Status
from ruleweaver.review.store import ReviewStore, build_engine

RULE = "rule.snap.gross_income_test"


@pytest.fixture()
def store(tmp_path):
    return ReviewStore(build_engine(f"sqlite:///{tmp_path / 'review.db'}"))


def event(**kw) -> ReviewEvent:
    base = {"rule_id": RULE, "reviewer": "alice", "decision": Decision.APPROVE,
                "rule_hash": "r1", "source_hash": "s1"}
    base.update(kw)
    return ReviewEvent(**base)


class TestPersistence:
    def test_round_trips_a_decision(self, store):
        store.append(event(duration_seconds=42.0, note="checked against 273.9(a)"))
        [loaded] = store.events()
        assert loaded.rule_id == RULE
        assert loaded.duration_seconds == 42.0
        assert loaded.note == "checked against 273.9(a)"

    def test_preserves_an_edited_rule(self, store):
        store.append(event(decision=Decision.EDIT, edited_to={"id": RULE, "fixed": True}))
        assert store.events()[0].edited_to == {"id": RULE, "fixed": True}

    def test_orders_by_sequence_not_timestamp(self, store):
        """Clocks differ across instances; the sequence does not."""
        for i in range(5):
            store.append(event(reviewer=f"r{i}", at="2026-01-01T00:00:00+00:00"))
        assert [e.reviewer for e in store.events()] == [f"r{i}" for i in range(5)]

    def test_filters_by_rule(self, store):
        store.append(event())
        store.append(event(rule_id="rule.other"))
        assert len(store.events(RULE)) == 1

    def test_rehydrates_a_working_log(self, store):
        store.append(event())
        log = store.load_log()
        assert log.status(RULE, rule_hash="r1", source_hash="s1") is Status.APPROVED

    def test_survives_reopening_the_database(self, tmp_path):
        url = f"sqlite:///{tmp_path / 'review.db'}"
        ReviewStore(build_engine(url)).append(event())
        assert len(ReviewStore(build_engine(url)).events()) == 1


class TestAppendOnly:
    def test_store_exposes_no_mutation_methods(self, store):
        for banned in ("update", "delete", "edit", "remove", "purge"):
            assert not hasattr(store, banned), f"ReviewStore must not expose {banned}()"

    def test_superseding_appends_rather_than_replaces(self, store):
        store.append(event())
        store.append(event(reviewer="bob", decision=Decision.REJECT, note="threshold wrong"))
        events = store.events(RULE)
        assert len(events) == 2
        assert events[0].decision is Decision.APPROVE  # the original still stands


class TestTamperEvidence:
    def test_an_untouched_chain_verifies(self, store):
        for i in range(5):
            store.append(event(reviewer=f"r{i}"))
        assert store.verify_chain() == (True, None)

    def test_editing_a_decision_breaks_the_chain(self, store):
        store.append(event(reviewer="alice"))
        store.append(event(reviewer="bob"))
        store.append(event(reviewer="carol"))

        # Someone with database access flips a rejection into an approval.
        with store.engine.begin() as conn:
            conn.execute(text(
                "UPDATE review_events SET decision = 'reject' WHERE reviewer = 'bob'"))

        intact, broken_at = store.verify_chain()
        assert not intact
        assert broken_at is not None

    def test_deleting_a_row_breaks_the_chain(self, store):
        for name in ("alice", "bob", "carol"):
            store.append(event(reviewer=name))
        with store.engine.begin() as conn:
            conn.execute(text("DELETE FROM review_events WHERE reviewer = 'bob'"))
        intact, _ = store.verify_chain()
        assert not intact

    def test_reports_the_earliest_break(self, store):
        for index in range(4):
            store.append(event(reviewer=f"r{index}"))
        rows = store.events()
        with store.engine.begin() as conn:
            conn.execute(text(
                "UPDATE review_events SET note = 'tampered' WHERE reviewer = 'r1'"))
        intact, broken_at = store.verify_chain()
        assert not intact
        assert broken_at == rows[1].id  # the first altered row, not a later one

    def test_appending_after_a_break_does_not_repair_it(self, store):
        store.append(event(reviewer="alice"))
        with store.engine.begin() as conn:
            conn.execute(text("UPDATE review_events SET note = 'x' WHERE reviewer = 'alice'"))
        store.append(event(reviewer="bob"))
        assert store.verify_chain()[0] is False


class TestSeededErrors:
    def test_seeds_persist(self, store):
        store.record_seed(SeededError(
            id="seed-1", rule_id=RULE, description="comparison flipped",
            mutated_rule={"id": RULE}))
        [seed] = store.seeds()
        assert seed["id"] == "seed-1"
        assert seed["expected_decision"] == "reject"
