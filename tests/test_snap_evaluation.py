"""Behaviour of the SNAP fixture under the deterministic evaluator.

These are policy-intent tests: each asserts an outcome a caseworker would recognise, and
each cites the clause it is testing. They are hand-written, not generated, and per ADR-012
generated tests may never replace them.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from conftest import household, member
from ruleweaver.runtime import UNKNOWN, is_unknown

H = "var.household."


def run(ev, ctx):
    ev.run(ctx)
    return ctx.household


class TestBaselineHousehold:
    """A working parent with two children, 48 states and DC."""

    def test_income_aggregates_over_members(self, evaluator):
        h = run(evaluator, household([member(34, earned="1500"), member(8), member(6)], shelter="900"))
        assert h[H + "gross_monthly_income"] == Decimal("1500")

    def test_earned_income_deduction_is_twenty_percent(self, evaluator):
        # 7 CFR 273.9(d)(2)
        h = run(evaluator, household([member(34, earned="1500"), member(8), member(6)], shelter="900"))
        assert h[H + "earned_income_deduction"] == Decimal("300.00")

    def test_net_income_and_eligibility(self, evaluator):
        h = run(evaluator, household([member(34, earned="1500"), member(8), member(6)], shelter="900"))
        # 1500 - 204 standard - 300 earned = 996; shelter 900 - 498 = 402; net 594
        assert h[H + "income_after_other_deductions"] == Decimal("996.00")
        assert h[H + "excess_shelter_deduction"] == Decimal("402.0000")
        assert h[H + "net_monthly_income"] == Decimal("594.0000")
        assert h[H + "is_income_eligible"] is True


class TestSubstitutiveException:
    """7 CFR 273.9(d)(6)(ii) — the shelter cap applies only where the household has no
    elderly or disabled member. The canonical substitutive exception."""

    def test_cap_applies_without_elderly_member(self, evaluator):
        # Raw excess would be 2000 - 498 = 1502, above the 672 cap.
        h = run(evaluator, household([member(34, earned="1500"), member(8), member(6)], shelter="2000"))
        assert h[H + "has_elderly_or_disabled_member"] is False
        assert h[H + "excess_shelter_deduction"] == Decimal("672")

    def test_cap_does_not_apply_with_elderly_member(self, evaluator):
        h = run(evaluator, household([member(67, earned="1500"), member(8), member(6)], shelter="2000"))
        assert h[H + "has_elderly_or_disabled_member"] is True
        assert h[H + "excess_shelter_deduction"] == Decimal("1502.0000")

    def test_disability_benefit_qualifies_without_age(self, evaluator):
        # 271.2 branches (2)-(9): disability qualifies regardless of age.
        h = run(evaluator, household([member(30, earned="1500", disabled=True), member(8)], shelter="2000"))
        assert h[H + "has_elderly_or_disabled_member"] is True

    def test_exception_is_recorded_in_the_trace(self, evaluator):
        ctx = household([member(34, earned="1500"), member(8), member(6)], shelter="2000")
        evaluator.run(ctx)
        step = [s for s in ctx.trace if s.target == H + "excess_shelter_deduction"][-1]
        assert step.via == "exception:exception.snap.shelter_cap_applies"


class TestGrossIncomeTestWaiver:
    """7 CFR 273.9(a) — households with an elderly or disabled member are screened on
    net income only."""

    def test_high_income_household_fails_gross_test(self, evaluator):
        h = run(evaluator, household([member(34, earned="5000"), member(8), member(6)]))
        assert h[H + "meets_gross_income_test"] is False
        assert h[H + "is_income_eligible"] is False

    def test_elderly_household_is_exempt_from_gross_test(self, evaluator):
        h = run(evaluator, household([member(67, earned="5000"), member(8), member(6)]))
        assert h[H + "meets_gross_income_test"] is True


class TestNotwithstandingOverride:
    """7 CFR 273.9(d)(1) — the six-person ceiling, and the statutory minimum that
    overrides the computed deduction."""

    def test_deduction_index_clamps_at_six_persons(self, evaluator):
        # A household of eight must use the six-person deduction, 234.
        h = run(evaluator, household([member(40, earned="1000")] + [member(5)] * 7, size=8))
        assert h[H + "standard_deduction"] == Decimal("234")

    def test_minimum_overrides_the_computed_value(self, evaluator):
        h = run(evaluator, household([member(34, earned="1500"), member(8), member(6)]))
        assert h[H + "standard_deduction"] == Decimal("204")

    def test_override_rule_is_the_one_that_fired(self, evaluator):
        ctx = household([member(34, earned="1500"), member(8), member(6)])
        evaluator.run(ctx)
        step = [s for s in ctx.trace if s.target == H + "standard_deduction"][-1]
        assert step.rule_id == "rule.snap.standard_deduction_minimum"


class TestBoundaries:
    """Threshold behaviour at x-1 / x / x+1.

    Monthly gross limit for a household of three: ceil(26650 / 12 * 1.30) = 2888.
    """

    LIMIT = 2888

    @pytest.mark.parametrize(
        "income,expected",
        [(LIMIT - 1, True), (LIMIT, True), (LIMIT + 1, False)],
    )
    def test_gross_income_threshold(self, evaluator, income, expected):
        h = run(evaluator, household([member(34, earned=str(income)), member(8), member(6)]))
        assert h[H + "meets_gross_income_test"] is expected


class TestUnknownHandling:
    """docs/04_RULE_IR_SPEC.md forbids coercing a missing input to false or zero."""

    def test_missing_income_yields_unknown_not_zero(self, evaluator):
        ctx = household([member(34, earned="1500"), member(8)], shelter="900")
        del ctx.members[1]["var.member.earned_income"]
        h = run(evaluator, ctx)
        assert is_unknown(h[H + "gross_monthly_income"])

    def test_unknown_propagates_to_the_decision(self, evaluator):
        ctx = household([member(34, earned="1500"), member(8)], shelter="900")
        del ctx.members[1]["var.member.earned_income"]
        h = run(evaluator, ctx)
        assert is_unknown(h[H + "is_income_eligible"])

    def test_unknown_refuses_to_be_truthy(self):
        with pytest.raises(TypeError, match="no truth value"):
            bool(UNKNOWN)

    def test_missing_parameter_does_not_become_zero(self, evaluator):
        # Guam has no published values in the fixture's override table.
        h = run(evaluator, household([member(34, earned="1500"), member(8)], jurisdiction="guam"))
        assert is_unknown(h[H + "meets_gross_income_test"])


class TestEmptyGroupIdentities:
    """An empty group yields the operator identity, never unknown."""

    def test_no_members_gives_zero_income_and_false_existential(self, evaluator):
        h = run(evaluator, household([], size=1))
        assert h[H + "gross_monthly_income"] == Decimal("0")
        assert h[H + "has_elderly_or_disabled_member"] is False
