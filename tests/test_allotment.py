"""Benefit calculation — 7 CFR 273.10(e).

Eligibility answers whether a household qualifies. This answers the question people
actually ask, which is how much they receive.
"""

from __future__ import annotations

from decimal import Decimal

from conftest import household, member
from ruleweaver.runtime import is_unknown

H = "var.household."


def run(ev, ctx):
    ev.run(ctx)
    return ctx.household


class TestAllotmentCalculation:
    """allotment = maximum allotment for the size, less 30 percent of net income."""

    def test_reduction_is_thirty_percent_rounded_up(self, evaluator):
        # Net income 594 -> 0.30 * 594 = 178.20 -> rounds up to 179.
        h = run(evaluator, household([member(34, earned="1500"), member(8), member(6)], shelter="900"))
        assert h[H + "net_monthly_income"] == Decimal("594.0000")
        assert h[H + "benefit_reduction"] == Decimal("179")

    def test_allotment_is_maximum_less_the_reduction(self, evaluator):
        h = run(evaluator, household([member(34, earned="1500"), member(8), member(6)], shelter="900"))
        assert h[H + "allotment"] == Decimal("606")  # 785 - 179

    def test_rounding_direction_matters(self, evaluator):
        """The regulation offers the State agency a choice of rounding methods and this
        package implements one of them. Pin it, because the other yields a different
        amount and the difference is a real dollar in someone's benefit."""
        h = run(evaluator, household([member(34, earned="1500"), member(8), member(6)], shelter="900"))
        # 178.20 rounded up is 179, not 178.
        assert h[H + "benefit_reduction"] == Decimal("179")


class TestMinimumBenefit:
    """273.10(e)(2)(ii)(C): eligible one and two person households receive at least the
    minimum benefit, even where the computed allotment would be lower."""

    def test_small_household_receives_the_minimum(self, evaluator):
        # One person, earned 1600: net 1076, reduction 323, computed 292 - 323 -> floors to 0.
        h = run(evaluator, household([member(45, earned="1600")], size=1))
        assert h[H + "is_income_eligible"] is True
        assert h[H + "benefit_reduction"] == Decimal("323")
        assert h[H + "allotment"] == Decimal("23")

    def test_minimum_arrives_via_the_exception(self, evaluator):
        ctx = household([member(45, earned="1600")], size=1)
        evaluator.run(ctx)
        step = [s for s in ctx.trace if s.target == H + "allotment"][-1]
        assert step.via == "exception:exception.snap.minimum_benefit_small_household"

    def test_small_household_with_low_income_keeps_the_higher_computed_amount(self, evaluator):
        # The minimum is a floor, not a cap.
        h = run(evaluator, household([member(45, earned="200")], size=1))
        assert h[H + "allotment"] > Decimal("23")

    def test_three_person_household_gets_no_minimum(self, evaluator):
        ctx = household([member(34, earned="1500"), member(8), member(6)], shelter="900")
        evaluator.run(ctx)
        step = [s for s in ctx.trace if s.target == H + "allotment"][-1]
        assert step.via == "base"


class TestEligibilityGuard:
    """The allotment rule is guarded on eligibility, so an ineligible household gets no
    determination rather than a zero. Zero would read as 'entitled to nothing'; absent
    reads as 'not determined', which is the truthful state."""

    def test_ineligible_household_has_no_allotment(self, evaluator):
        h = run(evaluator, household([member(34, earned="5000"), member(8), member(6)]))
        assert h[H + "is_income_eligible"] is False
        assert H + "allotment" not in h

    def test_unknown_eligibility_produces_no_allotment(self, evaluator):
        ctx = household([member(34, earned="1500"), member(8)], shelter="900")
        del ctx.members[1]["var.member.earned_income"]
        h = run(evaluator, ctx)
        assert is_unknown(h[H + "is_income_eligible"])
        assert H + "allotment" not in h


class TestFloor:
    def test_allotment_never_goes_negative(self, evaluator):
        h = run(evaluator, household([member(45, earned="1600")], size=1))
        assert h[H + "allotment"] >= Decimal("0")
