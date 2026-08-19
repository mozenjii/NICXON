"""Date transition cases.

A rule applied a day early, or a repealed rule still firing, produces a wrong
determination that no threshold test would catch.
"""

from __future__ import annotations

import copy
import json

import pytest

from conftest import FIXTURE, PARAMETER_OVERRIDES, household, member
from ruleweaver.ir import RulePackage
from ruleweaver.runtime import Evaluator, ParameterTable
from ruleweaver.testgen import boundaries, generate_dates, transitions

H = "var.household."
ELIGIBLE = H + "is_income_eligible"


@pytest.fixture(scope="module")
def raw() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _cases(doc: dict, observe=(ELIGIBLE,)):
    pkg = RulePackage.model_validate(doc)
    ev = Evaluator(pkg, ParameterTable(pkg, overrides=PARAMETER_OVERRIDES))
    base = household([member(34, earned="1500"), member(8), member(6)], shelter="900")
    return pkg, generate_dates(pkg, base, ev, observe=list(observe))


class TestBoundaryDiscovery:
    def test_finds_the_effective_from_date(self, raw):
        pkg = RulePackage.model_validate(raw)
        dates = {d for d, _ in boundaries(pkg)}
        assert "2026-01-01" in dates

    def test_finds_parameter_value_boundaries(self, raw):
        pkg = RulePackage.model_validate(raw)
        dates = {d for d, _ in boundaries(pkg)}
        assert "1978-01-01" in dates  # the multiplier and rate parameters

    def test_every_boundary_yields_three_cases(self, raw):
        pkg, cases = _cases(raw)
        assert len(cases) == 3 * len(boundaries(pkg))
        assert {c.position for c in cases} == {"before", "on", "after"}


class TestCommencement:
    """Rules commence on 2026-01-01. The day before, nothing should apply."""

    def test_rules_do_not_apply_before_commencement(self, raw):
        _, cases = _cases(raw)
        before = [c for c in cases if c.boundary == "2026-01-01" and c.position == "before"]
        assert before
        for case in before:
            assert case.observed[ELIGIBLE] is None  # no rule fired, so nothing was assigned

    def test_rules_apply_on_and_after_commencement(self, raw):
        _, cases = _cases(raw)
        for position in ("on", "after"):
            got = [c for c in cases if c.boundary == "2026-01-01" and c.position == position]
            assert got and all(c.observed[ELIGIBLE] is True for c in got)

    def test_commencement_is_reported_as_a_transition(self, raw):
        _, cases = _cases(raw)
        changed = dict((b, (x, y)) for b, x, y in transitions(cases, ELIGIBLE))
        assert "2026-01-01" in changed
        assert changed["2026-01-01"] == (None, True)


class TestRepeal:
    """effective_to is exclusive: a rule applies the day before and not on the day."""

    def test_repeal_stops_the_rule_on_the_day(self, raw):
        doc = copy.deepcopy(raw)
        for rule in doc["rules"]:
            rule["effective_to"] = "2027-01-01"
        _, cases = _cases(doc)
        by_pos = {c.position: c for c in cases if c.boundary == "2027-01-01"}
        assert by_pos["before"].observed[ELIGIBLE] is True
        assert by_pos["on"].observed[ELIGIBLE] is None
        assert by_pos["after"].observed[ELIGIBLE] is None

    def test_repeal_is_reported_as_a_transition(self, raw):
        doc = copy.deepcopy(raw)
        for rule in doc["rules"]:
            rule["effective_to"] = "2027-01-01"
        _, cases = _cases(doc)
        assert any(b == "2027-01-01" for b, _, _ in transitions(cases, ELIGIBLE))


class TestLabelling:
    def test_cases_are_marked_generated(self, raw):
        _, cases = _cases(raw)
        assert cases and all(c.origin == "generated" for c in cases)

    def test_cases_carry_a_rationale(self, raw):
        _, cases = _cases(raw)
        assert all(c.rationale for c in cases)
