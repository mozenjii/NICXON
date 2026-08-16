"""The review gate.

ADR-004 makes human approval the control that stops a wrong rule executing, so these
tests are about whether that control can be shown to work — not whether the workflow
compiles.
"""

from __future__ import annotations

import pytest

from ruleweaver.review import (
    AdversarialQueue,
    Decision,
    ReviewEvent,
    ReviewLog,
    SeededError,
    Status,
    deterministic_seed_choice,
    dual_encode_disagreements,
)

RULE = "rule.snap.gross_income_test"


def event(**kw) -> ReviewEvent:
    base = dict(rule_id=RULE, reviewer="alice", decision=Decision.APPROVE,
                rule_hash="r1", source_hash="s1")
    base.update(kw)
    return ReviewEvent(**base)


class TestDerivedStatus:
    """Approval is derived from the log, never stored — so it cannot drift."""

    def test_unreviewed_by_default(self):
        assert ReviewLog().status(RULE, rule_hash="r1", source_hash="s1") is Status.UNREVIEWED

    def test_approval_is_recorded(self):
        log = ReviewLog()
        log.append(event())
        assert log.status(RULE, rule_hash="r1", source_hash="s1") is Status.APPROVED

    def test_approval_goes_stale_when_the_rule_changes(self):
        log = ReviewLog()
        log.append(event())
        assert log.status(RULE, rule_hash="r2", source_hash="s1") is Status.STALE

    def test_approval_goes_stale_when_the_source_changes(self):
        """The clause moved under an approved rule. Nobody has to remember to notice."""
        log = ReviewLog()
        log.append(event())
        assert log.status(RULE, rule_hash="r1", source_hash="s2") is Status.STALE

    def test_later_decision_supersedes_earlier(self):
        log = ReviewLog()
        log.append(event())
        log.append(event(reviewer="bob", decision=Decision.REJECT, note="threshold is wrong"))
        assert log.status(RULE, rule_hash="r1", source_hash="s1") is Status.REJECTED

    def test_history_is_never_erased(self):
        log = ReviewLog()
        log.append(event())
        log.append(event(reviewer="bob", decision=Decision.REJECT, note="wrong"))
        assert len(log.events_for(RULE)) == 2
        assert log.reviewers_of(RULE) == ["alice", "bob"]

    def test_only_approved_rules_are_executable(self):
        log = ReviewLog()
        log.append(event())
        log.append(event(rule_id="rule.b", decision=Decision.REJECT, note="no"))
        executable = log.approved_rules({RULE: ("r1", "s1"), "rule.b": ("r1", "s1")})
        assert executable == {RULE}

    def test_stale_rules_are_not_executable(self):
        log = ReviewLog()
        log.append(event())
        assert log.approved_rules({RULE: ("CHANGED", "s1")}) == set()


class TestDecisionIntegrity:
    def test_edit_must_carry_the_edited_rule(self):
        with pytest.raises(ValueError, match="must carry the edited rule"):
            event(decision=Decision.EDIT)

    def test_rejection_requires_a_reason(self):
        """An unexplained rejection tells the next reviewer nothing."""
        with pytest.raises(ValueError, match="requires a note"):
            event(decision=Decision.REJECT)

    def test_ambiguous_requires_a_reason(self):
        with pytest.raises(ValueError, match="requires a note"):
            event(decision=Decision.MARK_AMBIGUOUS)

    def test_events_are_immutable(self):
        e = event()
        with pytest.raises(Exception):
            e.decision = Decision.REJECT  # type: ignore[misc]


class TestSeeding:
    def test_seeding_is_deterministic(self):
        first = [deterministic_seed_choice(f"rule.{i}", 0.3, "campaign-1") for i in range(50)]
        second = [deterministic_seed_choice(f"rule.{i}", 0.3, "campaign-1") for i in range(50)]
        assert first == second

    def test_salt_changes_which_rules_are_seeded(self):
        a = [deterministic_seed_choice(f"rule.{i}", 0.3, "campaign-1") for i in range(50)]
        b = [deterministic_seed_choice(f"rule.{i}", 0.3, "campaign-2") for i in range(50)]
        assert a != b

    def test_rate_is_roughly_honoured(self):
        hits = sum(deterministic_seed_choice(f"rule.{i}", 0.2, "s") for i in range(2000))
        assert 0.15 < hits / 2000 < 0.25

    def test_zero_rate_seeds_nothing(self):
        assert not any(deterministic_seed_choice(f"rule.{i}", 0.0) for i in range(100))

    def test_invalid_rate_rejected(self):
        with pytest.raises(ValueError):
            deterministic_seed_choice("rule.x", 1.5)


class TestCatchRate:
    def _queue(self):
        log = ReviewLog()
        queue = AdversarialQueue(log, seed_rate=0.5, salt="test")
        err = queue.register(SeededError(
            id="seed-1", rule_id=RULE, description="threshold flipped to lt",
            mutated_rule={"id": RULE},
        ))
        return log, queue, err

    def test_catching_a_seeded_error(self):
        log, queue, err = self._queue()
        log.append(event(decision=Decision.REJECT, note="operator is wrong",
                         seeded_error_id=err.id, duration_seconds=45.0))
        assert queue.was_caught(err.id)
        assert queue.metrics().catch_rate == 1.0

    def test_approving_a_seeded_error_is_a_miss(self):
        log, queue, err = self._queue()
        log.append(event(seeded_error_id=err.id, duration_seconds=3.0))
        assert not queue.was_caught(err.id)
        assert queue.metrics().catch_rate == 0.0

    def test_unresolved_seeds_are_excluded_not_counted_as_misses(self):
        """An unreviewed backlog must not look like a failing gate."""
        _, queue, err = self._queue()
        assert queue.unresolved() == [err]
        assert queue.metrics().catch_rate == 0.0  # nothing caught yet
        assert len(queue.unresolved()) == 1

    def test_no_seeds_gives_none_not_zero(self):
        """None means 'not measured'; zero means 'everything was missed'."""
        queue = AdversarialQueue(ReviewLog())
        assert queue.metrics().catch_rate is None


class TestRubberStampDetection:
    def test_low_catch_rate_warns(self):
        log = ReviewLog()
        queue = AdversarialQueue(log)
        for i in range(4):
            err = queue.register(SeededError(
                id=f"s{i}", rule_id=f"rule.{i}", description="fault", mutated_rule={}))
            log.append(event(rule_id=f"rule.{i}", seeded_error_id=err.id, duration_seconds=40.0))
        warnings = queue.metrics().warnings()
        assert any("not catching planted faults" in w for w in warnings)

    def test_fast_reviews_warn(self):
        log = ReviewLog()
        queue = AdversarialQueue(log)
        for i in range(10):
            log.append(event(rule_id=f"rule.{i}", duration_seconds=3.0))
        assert any("rubber-stamping" in w for w in queue.metrics().warnings())

    def test_universal_approval_warns(self):
        log = ReviewLog()
        queue = AdversarialQueue(log)
        for i in range(25):
            log.append(event(rule_id=f"rule.{i}", duration_seconds=60.0))
        assert any("is not a gate" in w for w in queue.metrics().warnings())

    def test_a_healthy_queue_warns_about_nothing(self):
        log = ReviewLog()
        queue = AdversarialQueue(log)
        for i in range(20):
            decision = Decision.REJECT if i % 4 == 0 else Decision.APPROVE
            kw = {"note": "incorrect threshold"} if decision == Decision.REJECT else {}
            log.append(event(rule_id=f"rule.{i}", decision=decision,
                             duration_seconds=90.0, **kw))
        err = queue.register(SeededError(id="s1", rule_id="rule.0",
                                         description="fault", mutated_rule={}))
        log.append(event(rule_id="rule.0", reviewer="bob", decision=Decision.REJECT,
                         note="caught it", seeded_error_id=err.id, duration_seconds=75.0))
        assert queue.metrics().warnings() == []

    def test_report_is_readable(self):
        log = ReviewLog()
        queue = AdversarialQueue(log)
        log.append(event(duration_seconds=30.0))
        assert "reviewed" in str(queue.metrics())


class TestDualEncoding:
    """Three experienced coders agreed on 0% of rules encoded independently
    (Artif Intell Law 10.1007/s10506-023-09350-1). Disagreement is the expected case."""

    def test_disagreement_is_surfaced(self):
        log = ReviewLog()
        log.append(event(reviewer="alice"))
        log.append(event(reviewer="bob", decision=Decision.REJECT, note="reads differently"))
        assert dual_encode_disagreements(log, [RULE]) == [RULE]

    def test_agreement_is_not_flagged(self):
        log = ReviewLog()
        log.append(event(reviewer="alice"))
        log.append(event(reviewer="bob"))
        assert dual_encode_disagreements(log, [RULE]) == []

    def test_single_reviewer_is_not_a_disagreement(self):
        log = ReviewLog()
        log.append(event(reviewer="alice"))
        assert dual_encode_disagreements(log, [RULE]) == []
