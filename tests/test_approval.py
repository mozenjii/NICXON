"""The approval gate.

README principle 4 says no rule executes until it passes review. These tests exist because
that sentence was true of the documentation and false of the code: the evaluator ran
whatever it was given. Each test here pins one way the gate can fail open.
"""

from __future__ import annotations

import pytest

from conftest import PARAMETER_OVERRIDES, household, member
from ruleweaver.approval import (
    GateReport,
    NotApproved,
    approved_subset,
    check,
    current_hashes,
    enforce,
    rule_digest,
    source_digest,
)
from ruleweaver.ir import RulePackage
from ruleweaver.review import Decision, ReviewEvent, ReviewLog, Status
from ruleweaver.runtime import Evaluator, ParameterTable
from ruleweaver.runtime.values import UNKNOWN


def approve_all(package: RulePackage, reviewer: str = "alice") -> ReviewLog:
    log = ReviewLog()
    for rule_id, (rh, sh) in current_hashes(package).items():
        log.append(ReviewEvent(rule_id=rule_id, reviewer=reviewer,
                               decision=Decision.APPROVE, rule_hash=rh, source_hash=sh))
    return log


class TestCheck:
    def test_an_unreviewed_package_is_entirely_blocked(self, package):
        report = check(package, ReviewLog())
        assert report.approved == []
        assert len(report.blocked) == len(package.rules)
        assert set(report.blocked.values()) == {Status.UNREVIEWED}
        assert not report.ok

    def test_a_fully_reviewed_package_passes(self, package):
        report = check(package, approve_all(package))
        assert report.ok
        assert len(report.approved) == len(package.rules)

    def test_a_rejection_blocks(self, package):
        log = approve_all(package)
        target = package.rules[0]
        log.append(ReviewEvent(
            rule_id=target.id, reviewer="bob", decision=Decision.REJECT,
            rule_hash=rule_digest(target), source_hash=source_digest(target),
            note="the threshold does not match 273.9(a)(1)"))
        report = check(package, log)
        assert report.blocked == {target.id: Status.REJECTED}

    def test_editing_the_rule_after_approval_makes_it_stale(self, package):
        """The case the gate exists for: approval recorded against content that moved."""
        log = approve_all(package)
        target = package.rules[0]
        moved = package.model_copy(update={
            "rules": [
                r.model_copy(update={"effective_from": "2030-01-01"}) if r.id == target.id else r
                for r in package.rules
            ]
        })
        report = check(moved, log)
        assert report.blocked == {target.id: Status.STALE}

    def test_rewording_a_citation_makes_it_stale(self, package):
        """Source staleness is tracked separately, so a re-fetched clause is caught."""
        log = approve_all(package)
        target = package.rules[0]
        spans = [s.model_copy(update={"quote": "reworded by the publisher"})
                 for s in target.sources]
        moved = package.model_copy(update={
            "rules": [
                r.model_copy(update={"sources": spans}) if r.id == target.id else r
                for r in package.rules
            ]
        })
        assert check(moved, log).blocked == {target.id: Status.STALE}


class TestEnforce:
    def test_raises_on_an_unreviewed_package(self, package):
        with pytest.raises(NotApproved) as exc:
            enforce(package, ReviewLog())
        assert "not approved for execution" in str(exc.value)
        assert len(exc.value.statuses) == len(package.rules)

    def test_returns_the_package_when_everything_is_approved(self, package):
        assert enforce(package, approve_all(package)) is package


class TestApprovedSubset:
    def test_keeps_only_approved_rules(self, package):
        log = approve_all(package)
        dropped = package.rules[2]
        log.append(ReviewEvent(
            rule_id=dropped.id, reviewer="bob", decision=Decision.MARK_AMBIGUOUS,
            rule_hash=rule_digest(dropped), source_hash=source_digest(dropped),
            note="two readings of 'household' are defensible here"))

        subset, report = approved_subset(package, log)
        assert dropped.id not in {r.id for r in subset.rules}
        assert len(subset.rules) == len(package.rules) - 1
        assert report.blocked == {dropped.id: Status.AMBIGUOUS}

    def test_keeps_variables_and_parameters_whole(self, package):
        """Dropping a variable would report a reference error for a missing approval."""
        subset, _ = approved_subset(package, ReviewLog())
        assert subset.rules == []
        assert len(subset.variables) == len(package.variables)
        assert len(subset.parameters) == len(package.parameters)

    def test_an_excluded_rule_leaves_its_target_unknown_not_false(self, package):
        """The honest failure mode: no approval means no answer, not a denial."""
        log = approve_all(package)
        gate = package.rule("rule.snap.gross_income_test")
        assert gate is not None
        log.append(ReviewEvent(
            rule_id=gate.id, reviewer="bob", decision=Decision.REJECT,
            rule_hash=rule_digest(gate), source_hash=source_digest(gate),
            note="withdrawn pending clarification"))

        subset, _ = approved_subset(package, log)
        ctx = household([member(40, earned="900")], shelter="600")
        Evaluator(subset, ParameterTable(subset, overrides=PARAMETER_OVERRIDES)).run(ctx)

        eligible = ctx.household.get("var.household.is_income_eligible", UNKNOWN)
        assert eligible is UNKNOWN, "an unapproved rule must not produce a denial"


class TestGateReport:
    def test_summarises_by_status(self, package):
        report = check(package, ReviewLog())
        text = str(report)
        assert f"0 approved, {len(package.rules)} blocked" in text
        assert "unreviewed" in text

    def test_an_empty_report_says_so(self):
        assert str(GateReport()) == "no rules"
