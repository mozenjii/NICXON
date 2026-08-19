"""Amendment impact.

The scenario throughout is a real one: Congress raises the earned income deduction from
20 to 25 percent. The question a policy team asks is not "which lines changed" but "who
becomes eligible who was not before", and that is what these tests pin down.
"""

from __future__ import annotations

import copy
import json
from decimal import Decimal

import pytest

from conftest import FIXTURE, PARAMETER_OVERRIDES, household, member
from ruleweaver.diff import analyse, compare, dependency_closure
from ruleweaver.ir import RulePackage

H = "var.household."
OBSERVE = [H + "is_income_eligible", H + "net_monthly_income", H + "earned_income_deduction"]


@pytest.fixture(scope="module")
def raw() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


@pytest.fixture()
def before(raw) -> RulePackage:
    return RulePackage.model_validate(raw)


@pytest.fixture()
def after_rate_rise(raw) -> RulePackage:
    """The amendment: earned income deduction 20% -> 25%."""
    doc = copy.deepcopy(raw)
    for param in doc["parameters"]:
        if param["id"] == "param.snap.earned_income_deduction_rate":
            param["values"][0]["value"] = "0.25"
    return RulePackage.model_validate(doc)


def scenarios():
    return {
        "working parent, two children": (
            household([member(34, earned="1500"), member(8), member(6)], shelter="900"), PARAMETER_OVERRIDES),
        "single earner, no shelter costs": (
            household([member(40, earned="2400")], size=1), PARAMETER_OVERRIDES),
        "elderly household": (
            household([member(70, unearned="900")], size=1, shelter="600"), PARAMETER_OVERRIDES),
    }


class TestSemanticDiff:
    def test_parameter_change_is_semantic(self, before, after_rate_rise):
        diff = compare(before, after_rate_rise)
        assert diff.semantic
        assert "param.snap.earned_income_deduction_rate" in diff.changed_parameters

    def test_change_is_described_with_both_values(self, before, after_rate_rise):
        diff = compare(before, after_rate_rise)
        change = diff.semantic[0]
        assert change.before == "0.20"
        assert change.after == "0.25"

    def test_identical_packages_report_no_changes(self, before, raw):
        assert compare(before, RulePackage.model_validate(raw)).changes == []

    def test_reworded_citation_is_cosmetic_not_semantic(self, before, raw):
        doc = copy.deepcopy(raw)
        doc["rules"][0]["sources"][0]["quote"] = "reworded for clarity"
        diff = compare(before, RulePackage.model_validate(doc))
        assert diff.cosmetic
        assert not diff.semantic

    def test_removing_an_exception_is_semantic(self, before, raw):
        doc = copy.deepcopy(raw)
        doc["rules"][9]["exceptions"] = []
        diff = compare(before, RulePackage.model_validate(doc))
        assert any(c.field_name == "exceptions" for c in diff.semantic)


class TestDependencyClosure:
    def test_rate_change_reaches_the_eligibility_decision(self, before, after_rate_rise):
        diff = compare(before, after_rate_rise)
        direct, transitive = dependency_closure(
            after_rate_rise, diff.changed_rules, diff.changed_parameters)
        assert "rule.snap.earned_income_deduction" in direct
        # The decision is several hops downstream and must still be reached.
        assert "rule.snap.income_eligible" in transitive
        assert "rule.snap.net_monthly_income" in transitive

    def test_unrelated_rules_are_not_flagged(self, before, after_rate_rise):
        diff = compare(before, after_rate_rise)
        direct, transitive = dependency_closure(
            after_rate_rise, diff.changed_rules, diff.changed_parameters)
        assert "rule.snap.member_is_elderly_or_disabled" not in direct | transitive


class TestOutcomeImpact:
    def test_reports_which_scenarios_actually_move(self, before, after_rate_rise):
        diff = compare(before, after_rate_rise)
        report = analyse(before, after_rate_rise, diff, scenarios(), OBSERVE)
        assert report.scenarios_run == 3
        assert report.scenarios_changed >= 1

    def test_deduction_rises_and_net_income_falls(self, before, after_rate_rise):
        diff = compare(before, after_rate_rise)
        report = analyse(before, after_rate_rise, diff, scenarios(), OBSERVE)
        deduction = [c for c in report.outcome_changes
                     if c.variable.endswith("earned_income_deduction")
                     and c.scenario == "working parent, two children"]
        assert deduction
        assert deduction[0].before == Decimal("300.00")
        assert deduction[0].after == Decimal("375.00")

    def test_household_without_earnings_is_unaffected(self, before, after_rate_rise):
        diff = compare(before, after_rate_rise)
        report = analyse(before, after_rate_rise, diff, scenarios(), OBSERVE)
        # The elderly household has only unearned income, so an earned-income rate
        # change must not move it.
        assert not [c for c in report.outcome_changes if c.scenario == "elderly household"]

    def test_report_reads_as_a_change_notice(self, before, after_rate_rise):
        diff = compare(before, after_rate_rise)
        report = analyse(before, after_rate_rise, diff, scenarios(), OBSERVE)
        text = str(report)
        assert "LEGISLATIVE CHANGE IMPACT" in text
        assert "transitively affected" in text


class TestEligibilityFlip:
    """The case that matters: an amendment that changes who qualifies."""

    def test_threshold_rise_makes_a_household_newly_eligible(self, before, raw):
        doc = copy.deepcopy(raw)
        for param in doc["parameters"]:
            if param["id"] == "param.snap.gross_income_multiplier":
                param["values"][0]["value"] = "2.00"  # a large rise in the gross limit
        after = RulePackage.model_validate(doc)

        borderline = {"borderline household": (
            household([member(34, earned="3000"), member(8), member(6)]), PARAMETER_OVERRIDES)}
        report = analyse(before, after, compare(before, after), borderline, OBSERVE)

        flips = [c for c in report.outcome_changes
                 if c.variable.endswith("meets_gross_income_test")
                 or c.variable.endswith("is_income_eligible")]
        assert flips, str(report)
