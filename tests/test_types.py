"""Type checking — RW2003 through RW2008.

The last P0 in the backlog. Before it, validation resolved every reference and detected
every cycle, but nothing checked that the types on either side of an operator could meet.
Python will compare a Decimal to an int and add True to a number, so several of these
mistakes did not even fail loudly at evaluation — they produced an answer.

Each test plants one mistake in the real fixture rather than in a toy package. A checker
that only rejects hand-made nonsense is not evidence it would reject the mistake somebody
actually makes.
"""

from __future__ import annotations

import copy
import json

import pytest

from conftest import FIXTURE
from ruleweaver.ir import RulePackage
from ruleweaver.verify import validate


@pytest.fixture(scope="module")
def document() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def checked(document: dict, mutate):
    doc = copy.deepcopy(document)
    mutate(doc)
    return validate(RulePackage.model_validate(doc))


def rule_of(doc: dict, rule_id: str) -> dict:
    return next(r for r in doc["rules"] if r["id"] == rule_id)


class TestTheFixture:
    def test_the_real_package_type_checks(self, package):
        report = validate(package)
        assert [d for d in report.diagnostics if d.code.startswith("RW200")] == []
        assert report.errors == []


class TestConditions:
    def test_a_non_boolean_rule_condition_is_an_error(self, document):
        def mutate(doc):
            rule_of(doc, "rule.snap.income_eligible")["when"] = {
                "op": "ref", "id": "var.household.size"}

        report = checked(document, mutate)
        [found] = report.by_code("RW2003")
        assert "must be boolean, not integer" in found.message

    def test_a_non_boolean_exception_guard_is_an_error(self, document):
        def mutate(doc):
            rule = next(r for r in doc["rules"] if r.get("exceptions"))
            rule["exceptions"][0]["when"] = {"op": "ref", "id": "var.household.size"}

        assert checked(document, mutate).by_code("RW2003")


class TestOperands:
    def test_conjunction_over_a_number_is_an_error(self, document):
        def mutate(doc):
            rule_of(doc, "rule.snap.income_eligible")["when"] = {
                "op": "all",
                "args": [{"op": "literal", "value": True},
                         {"op": "ref", "id": "var.household.size"}],
            }

        [found] = checked(document, mutate).by_code("RW2005")
        assert "boolean operands, got integer" in found.message

    def test_negating_a_number_is_an_error(self, document):
        def mutate(doc):
            rule_of(doc, "rule.snap.income_eligible")["when"] = {
                "op": "not", "arg": {"op": "ref", "id": "var.household.size"}}

        assert checked(document, mutate).by_code("RW2005")

    def test_arithmetic_over_a_string_is_an_error(self, document):
        def mutate(doc):
            rule_of(doc, "rule.snap.gross_monthly_income")["then"]["assign"]["value"] = {
                "op": "add",
                "args": [{"op": "ref", "id": "var.household.jurisdiction"},
                         {"op": "literal", "value": 1}],
            }

        [found] = checked(document, mutate).by_code("RW2007")
        assert "numeric operands, got enumeration" in found.message

    def test_summing_a_boolean_over_members_is_an_error(self, document):
        """`count_over` exists for counting. Summing a flag is a different mistake and
        would silently produce a number nobody meant."""
        def mutate(doc):
            rule_of(doc, "rule.snap.earned_income_total")["then"]["assign"]["value"] = {
                "op": "sum_over",
                "entity": "household_member",
                "scope": {"op": "ref", "id": "var.household"},
                "value": {"op": "ref", "id": "var.member.receives_disability_benefit"},
            }

        [found] = checked(document, mutate).by_code("RW2007")
        assert "aggregates numbers, got boolean" in found.message

    def test_an_existential_over_a_number_is_an_error(self, document):
        def mutate(doc):
            rule_of(doc, "rule.snap.household_has_elderly_or_disabled_member")[
                "then"]["assign"]["value"] = {
                "op": "any_over",
                "entity": "household_member",
                "scope": {"op": "ref", "id": "var.household"},
                "value": {"op": "ref", "id": "var.member.age"},
            }

        assert checked(document, mutate).by_code("RW2005")


class TestComparisons:
    def test_ordering_a_string_against_a_number_is_an_error(self, document):
        def mutate(doc):
            rule_of(doc, "rule.snap.income_eligible")["when"] = {
                "op": "gte",
                "left": {"op": "ref", "id": "var.household.jurisdiction"},
                "right": {"op": "literal", "value": 3},
            }

        [found] = checked(document, mutate).by_code("RW2006")
        assert "cannot order" in found.message

    def test_equality_that_can_never_hold_is_an_error(self, document):
        """Comparing a jurisdiction code to a number is always false, which is far more
        likely to be an encoding mistake than an intended test."""
        def mutate(doc):
            rule_of(doc, "rule.snap.income_eligible")["when"] = {
                "op": "eq",
                "left": {"op": "ref", "id": "var.household.jurisdiction"},
                "right": {"op": "literal", "value": 3},
            }

        [found] = checked(document, mutate).by_code("RW2006")
        assert "never be equal" in found.message

    def test_two_enumerations_may_be_compared_for_equality(self, document):
        """Ordering an enumeration is refused — member order is an artifact of how the
        list was written down. Equality is the operation that actually means something."""
        def mutate(doc):
            rule_of(doc, "rule.snap.income_eligible")["when"] = {
                "op": "eq",
                "left": {"op": "ref", "id": "var.household.jurisdiction"},
                "right": {"op": "ref", "id": "var.household.jurisdiction"},
            }

        assert checked(document, mutate).by_code("RW2006") == []

    def test_ordering_two_enumerations_is_refused(self, document):
        def mutate(doc):
            rule_of(doc, "rule.snap.income_eligible")["when"] = {
                "op": "gt",
                "left": {"op": "ref", "id": "var.household.jurisdiction"},
                "right": {"op": "ref", "id": "var.household.jurisdiction"},
            }

        assert checked(document, mutate).by_code("RW2006")

    def test_numbers_of_different_widths_compare_fine(self, document):
        def mutate(doc):
            rule_of(doc, "rule.snap.income_eligible")["when"] = {
                "op": "gte",
                "left": {"op": "ref", "id": "var.household.gross_monthly_income"},
                "right": {"op": "literal", "value": 0},
            }

        assert checked(document, mutate).by_code("RW2006") == []


class TestAssignment:
    def test_assigning_a_number_to_a_boolean_is_an_error(self, document):
        def mutate(doc):
            rule_of(doc, "rule.snap.income_eligible")["then"]["assign"]["value"] = {
                "op": "ref", "id": "var.household.size"}

        [found] = checked(document, mutate).by_code("RW2004")
        assert "declared boolean" in found.message

    def test_narrowing_money_to_a_count_is_an_error(self, document):
        """Widening is fine; narrowing discards what makes the amount an amount."""
        def mutate(doc):
            rule_of(doc, "rule.snap.income_eligible")["then"]["assign"] = {
                "target": "var.household.size",
                "value": {"op": "ref", "id": "var.household.gross_monthly_income"},
            }

        assert checked(document, mutate).by_code("RW2004")

    def test_dividing_whole_numbers_does_not_stay_whole(self, document):
        """Reporting integer division as an integer would let a rule assign a fraction to
        a count and pass."""
        def mutate(doc):
            rule_of(doc, "rule.snap.income_eligible")["then"]["assign"] = {
                "target": "var.household.size",
                "value": {"op": "divide",
                          "args": [{"op": "literal", "value": 7},
                                   {"op": "literal", "value": 2}]},
            }

        [found] = checked(document, mutate).by_code("RW2004")
        assert "assigns decimal" in found.message


class TestPiecewise:
    def test_branches_that_disagree_are_an_error(self, document):
        def mutate(doc):
            rule_of(doc, "rule.snap.income_eligible")["then"]["assign"]["value"] = {
                "op": "piecewise",
                "cases": [{"when": {"op": "literal", "value": True},
                           "then": {"op": "literal", "value": "yes"}}],
                "otherwise": {"op": "literal", "value": True},
            }

        [found] = checked(document, mutate).by_code("RW2008")
        assert "branches disagree" in found.message

    def test_numeric_branches_widen_rather_than_disagree(self, document):
        def mutate(doc):
            rule_of(doc, "rule.snap.gross_monthly_income")["then"]["assign"]["value"] = {
                "op": "piecewise",
                "cases": [{"when": {"op": "literal", "value": True},
                           "then": {"op": "literal", "value": 0}}],
                "otherwise": {"op": "ref", "id": "var.household.earned_income_total"},
            }

        report = checked(document, mutate)
        assert report.by_code("RW2008") == []
        assert report.by_code("RW2004") == []


class TestNoCascade:
    def test_an_unresolvable_reference_does_not_also_produce_type_errors(self, document):
        """The reference resolver already reports it. Six type errors on top bury the one
        diagnostic that says what to fix."""
        def mutate(doc):
            rule_of(doc, "rule.snap.income_eligible")["when"] = {
                "op": "all",
                "args": [{"op": "ref", "id": "var.household.does_not_exist"},
                         {"op": "ref", "id": "var.household.is_income_eligible"}],
            }

        report = checked(document, mutate)
        assert report.by_code("RW3001") or report.by_code("RW3002")
        assert [d for d in report.diagnostics if d.code.startswith("RW200")] == []
