"""Validators must fire on broken packages, not just pass on good ones.

A validator nobody has seen fail is not evidence of anything, so each test here breaks
the fixture in one specific way and asserts the corresponding diagnostic.
"""

from __future__ import annotations

import copy
import json

import pytest

from conftest import FIXTURE
from ruleweaver.ir import RulePackage
from ruleweaver.verify import validate


@pytest.fixture(scope="module")
def raw() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def check(raw: dict, mutate) -> "Report":
    doc = copy.deepcopy(raw)
    mutate(doc)
    return validate(RulePackage.model_validate(doc))


class TestCleanPackage:
    def test_fixture_is_evaluable(self, raw):
        assert validate(RulePackage.model_validate(raw)).ok

    def test_fixture_has_no_blocking_diagnostics(self, raw):
        assert validate(RulePackage.model_validate(raw)).blocking == []

    def test_dead_rule_is_reported(self, raw):
        """standard_deduction_computed is unconditionally overridden, so it never fires.
        The mutation harness independently treats it as an equivalent-mutant source."""
        report = validate(RulePackage.model_validate(raw))
        codes = [d.code for d in report.diagnostics]
        assert "RW3009" in codes


class TestReferences:
    def test_undeclared_variable_blocks(self, raw):
        def m(d):
            d["rules"][2]["then"]["assign"]["value"] = {"op": "ref", "id": "var.household.nope"}
        assert check(raw, m).by_code("RW3001")

    def test_undeclared_parameter_blocks(self, raw):
        def m(d):
            d["rules"][7]["then"]["assign"]["value"] = {
                "op": "parameter", "id": "param.snap.nope", "args": {}}
        assert check(raw, m).by_code("RW3002")

    def test_aggregation_over_unknown_entity_blocks(self, raw):
        def m(d):
            d["rules"][2]["then"]["assign"]["value"]["args"][0]["entity"] = "goldfish"
        assert check(raw, m).by_code("RW3007")

    def test_assignment_to_undeclared_variable_blocks(self, raw):
        def m(d):
            d["rules"][2]["then"]["assign"]["target"] = "var.household.nope"
        assert check(raw, m).by_code("RW3003")


class TestOverrides:
    def test_override_of_unknown_rule_blocks(self, raw):
        def m(d):
            d["rules"][6]["overrides"] = ["rule.snap.does_not_exist"]
        assert check(raw, m).by_code("RW3005")

    def test_override_of_different_target_is_an_error(self, raw):
        def m(d):
            d["rules"][6]["overrides"] = ["rule.snap.earned_income_deduction"]
        report = check(raw, m)
        assert report.by_code("RW3006")
        assert not report.ok

    def test_override_cycle_blocks(self, raw):
        def m(d):
            d["rules"][5]["overrides"] = ["rule.snap.standard_deduction_minimum"]
            d["rules"][6]["overrides"] = ["rule.snap.standard_deduction_computed"]
        assert check(raw, m).by_code("RW3008")


class TestCycles:
    def test_variable_dependency_cycle_blocks(self, raw):
        def m(d):
            # Make gross income depend on net income, which already depends on it.
            d["rules"][2]["then"]["assign"]["value"] = {
                "op": "ref", "id": "var.household.net_monthly_income"}
        report = check(raw, m)
        assert report.by_code("RW3010")
        assert not report.ok


class TestTemporal:
    def test_empty_rule_interval_blocks(self, raw):
        def m(d):
            d["rules"][0]["effective_from"] = "2026-01-01"
            d["rules"][0]["effective_to"] = "2025-01-01"
        assert check(raw, m).by_code("RW4001")

    def test_overlapping_parameter_intervals_are_an_error(self, raw):
        def m(d):
            d["parameters"][1]["values"].append(
                {"effective_from": "2000-01-01", "effective_to": None, "value": "1.50", "at": {}})
        assert check(raw, m).by_code("RW4003")


class TestProvenance:
    def test_rule_without_source_is_an_error(self, raw):
        def m(d):
            d["rules"][3]["sources"] = []
        report = check(raw, m)
        assert report.by_code("RW7001")
        assert not report.ok

    def test_exception_without_source_warns(self, raw):
        def m(d):
            d["rules"][4]["exceptions"][0]["sources"] = []
        report = check(raw, m)
        assert report.by_code("RW7002")
        assert report.ok  # a warning must not block


class TestAmbiguity:
    def test_unresolved_blocking_ambiguity_blocks(self, raw):
        def m(d):
            d["ambiguities"][0]["blocking"] = True
            d["ambiguities"][0]["resolution"] = None
        report = check(raw, m)
        assert report.by_code("RW5002")
        assert not report.ok

    def test_ambiguity_affecting_unknown_rule_is_an_error(self, raw):
        def m(d):
            d["ambiguities"][0]["affects"] = ["rule.snap.does_not_exist"]
        assert check(raw, m).by_code("RW5001")


class TestDuplicates:
    def test_duplicate_rule_id_blocks(self, raw):
        def m(d):
            d["rules"].append(copy.deepcopy(d["rules"][0]))
        assert check(raw, m).by_code("RW2001")


class TestReportShape:
    def test_codes_are_stable_and_prefixed(self, raw):
        for d in validate(RulePackage.model_validate(raw)).diagnostics:
            assert d.code.startswith("RW")
            assert d.severity in ("info", "warning", "error", "blocking")
