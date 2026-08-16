"""Mutation testing: does the policy-intent suite actually catch broken rules?

A passing suite proves nothing by itself. This plants the faults a mis-extraction would
realistically produce and measures how many the suite detects. The resulting catch rate
is the evidence ADR-021 requires, and the second real number in the project.
"""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from conftest import FIXTURE, PARAMETER_OVERRIDES, household, member
from ruleweaver.ir import RulePackage
from ruleweaver.runtime import Evaluator, ParameterTable, is_unknown
from ruleweaver.testgen import generate_mutants, run

H = "var.household."


def _eval(pkg: RulePackage, ctx):
    Evaluator(pkg, ParameterTable(pkg, overrides=PARAMETER_OVERRIDES)).run(ctx)
    return ctx.household


def policy_intent_holds(pkg: RulePackage) -> bool:
    """The scenarios a caseworker would recognise. True when every one still holds.

    Deliberately mirrors the hand-written tests rather than the generated cases: per
    ADR-012 only policy intent may serve as the oracle.
    """
    try:
        baseline = _eval(pkg, household([member(34, earned="1500"), member(8), member(6)], shelter="900"))
        if baseline[H + "gross_monthly_income"] != Decimal("1500"):
            return False
        if baseline[H + "net_monthly_income"] != Decimal("594.0000"):
            return False
        if baseline[H + "is_income_eligible"] is not True:
            return False

        # Shelter cap applies without an elderly member, and not with one.
        capped = _eval(pkg, household([member(34, earned="1500"), member(8), member(6)], shelter="2000"))
        if capped[H + "excess_shelter_deduction"] != Decimal("672"):
            return False
        uncapped = _eval(pkg, household([member(67, earned="1500"), member(8), member(6)], shelter="2000"))
        if uncapped[H + "excess_shelter_deduction"] != Decimal("1502.0000"):
            return False

        # Gross income test, and its waiver for elderly households.
        rich = _eval(pkg, household([member(34, earned="5000"), member(8), member(6)]))
        if rich[H + "meets_gross_income_test"] is not False:
            return False
        rich_elderly = _eval(pkg, household([member(67, earned="5000"), member(8), member(6)]))
        if rich_elderly[H + "meets_gross_income_test"] is not True:
            return False

        # Six-person ceiling and the statutory minimum.
        large = _eval(pkg, household([member(40, earned="1000")] + [member(5)] * 7, size=8))
        if large[H + "standard_deduction"] != Decimal("234"):
            return False
        if baseline[H + "standard_deduction"] != Decimal("204"):
            return False

        # Threshold edge: 2888 passes, 2889 does not.
        at = _eval(pkg, household([member(34, earned="2888"), member(8), member(6)]))
        above = _eval(pkg, household([member(34, earned="2889"), member(8), member(6)]))
        if at[H + "meets_gross_income_test"] is not True:
            return False
        if above[H + "meets_gross_income_test"] is not False:
            return False

        # An elderly household with no shelter costs exercises the UNCAPPED branch's
        # floor. Without this the base rule's max(0, ...) is never observed, because
        # every other elderly scenario has shelter high enough to clear it.
        elderly_no_shelter = _eval(pkg, household(
            [member(67, earned="1500"), member(8), member(6)], shelter="0"))
        if elderly_no_shelter[H + "excess_shelter_deduction"] != Decimal("0"):
            return False

        # Age exactly 60 qualifies: 271.2 says "60 years of age or older".
        sixty = _eval(pkg, household([member(60, earned="1500"), member(8), member(6)], shelter="2000"))
        if sixty[H + "has_elderly_or_disabled_member"] is not True:
            return False

        # Gross test passes while the net test fails. Distinguishes conjunction from
        # disjunction in the final decision, which nothing else here does.
        unearned = _eval(pkg, household(
            [member(34, unearned="2500"), member(8), member(6)]))
        if unearned[H + "meets_gross_income_test"] is not True:
            return False
        if unearned[H + "meets_net_income_test"] is not False:
            return False
        if unearned[H + "is_income_eligible"] is not False:
            return False
        # Shelter expenses of zero must floor at zero, not go negative.
        if unearned[H + "excess_shelter_deduction"] != Decimal("0"):
            return False

        # Net income exactly at the limit. Pins both the comparison operator and the
        # rounding direction: ceil(26650/12) = 2221, floor would give 2220.
        at_net = _eval(pkg, household([member(34, unearned="2425"), member(8), member(6)]))
        if at_net[H + "net_monthly_income"] != Decimal("2221"):
            return False
        if at_net[H + "meets_net_income_test"] is not True:
            return False

        # Deductions exceeding income must floor at zero rather than going negative.
        tiny = _eval(pkg, household([member(34, earned="100"), member(8), member(6)]))
        if tiny[H + "income_after_other_deductions"] != Decimal("0"):
            return False

        # Shelter exceeding remaining income must floor net income at zero.
        sheltered = _eval(pkg, household([member(34, earned="300"), member(8), member(6)], shelter="500"))
        if sheltered[H + "net_monthly_income"] != Decimal("0"):
            return False

        # A missing input must not become a denial.
        ctx = household([member(34, earned="1500"), member(8)], shelter="900")
        del ctx.members[1]["var.member.earned_income"]
        if not is_unknown(_eval(pkg, ctx)[H + "is_income_eligible"]):
            return False
    except Exception:
        return False
    return True


@pytest.fixture(scope="module")
def report(package_module):
    return run(generate_mutants(package_module), policy_intent_holds)


@pytest.fixture(scope="module")
def package_module() -> RulePackage:
    return RulePackage.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_suite_passes_on_the_unmutated_package(package_module):
    assert policy_intent_holds(package_module) is True


def test_mutants_are_generated(report):
    # Seven fault classes over 13 rules. If this collapses, the harness has gone blind.
    assert report.total >= 15


def test_catch_rate_meets_the_floor(report):
    """Every planted fault must be caught.

    Do not lower this to go green. If a genuinely equivalent mutant appears — one that
    cannot change behaviour, as mutating an unconditionally overridden rule does — exclude
    it in generate_mutants with a stated reason, the way overridden rules already are.
    A survivor that is not provably equivalent is a missing policy-intent test.
    """
    assert report.catch_rate == 1.0, f"\n{report}"


def test_structural_faults_are_always_caught(report):
    """Dropping an exception or a notwithstanding override changes who gets a benefit.
    A suite that misses those is not protecting anything."""
    structural = [m for m in report.survivors if m.operator in {"drop_exception", "drop_override"}]
    assert not structural, f"structural faults survived:\n{report}"


def test_report_is_readable(report):
    assert "mutation score" in str(report)
