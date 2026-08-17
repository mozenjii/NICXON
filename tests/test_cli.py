"""The command line interface is the surface most people will meet first."""

from __future__ import annotations

import json

import pytest

from conftest import FIXTURE
from ruleweaver.cli import main

SCENARIO = FIXTURE.parent / "scenarios" / "baseline.json"


class TestValidate:
    def test_fixture_validates(self, capsys):
        assert main(["validate", str(FIXTURE)]) == 0
        assert "ok" in capsys.readouterr().out

    def test_broken_package_exits_nonzero(self, tmp_path, capsys):
        doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
        doc["rules"][3]["sources"] = []
        path = tmp_path / "broken.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        assert main(["validate", str(path)]) == 1
        assert "RW7001" in capsys.readouterr().out


class TestEvaluate:
    def test_baseline_scenario_is_eligible(self, capsys):
        assert main(["evaluate", str(FIXTURE), str(SCENARIO)]) == 0
        out = capsys.readouterr().out
        assert "is_income_eligible" in out
        assert "True" in out

    def test_trace_names_the_rule_that_fired(self, capsys):
        main(["evaluate", str(FIXTURE), str(SCENARIO), "--trace"])
        out = capsys.readouterr().out
        # The statutory minimum must win over the computed deduction.
        assert "rule.snap.standard_deduction_minimum" in out
        # And the shelter cap must arrive via the substitutive exception.
        assert "exception:exception.snap.shelter_cap_applies" in out

    def test_evaluating_an_invalid_package_exits_nonzero(self, tmp_path):
        doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
        doc["rules"][3]["sources"] = []
        path = tmp_path / "broken.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            main(["evaluate", str(path), str(SCENARIO)])
        assert exc.value.code == 1


class TestBoundaries:
    def test_generates_cases_and_labels_them_diagnostic(self, capsys):
        assert main(["boundaries", str(FIXTURE), str(SCENARIO),
                     "--observe", "var.household.is_income_eligible"]) == 0
        out = capsys.readouterr().out
        assert "generated boundary case" in out
        assert "not policy intent" in out


class TestSchema:
    def test_emits_valid_json_schema(self, capsys):
        assert main(["schema"]) == 0
        schema = json.loads(capsys.readouterr().out)
        assert schema["title"] == "RulePackage"
        assert "properties" in schema


AMENDMENT = FIXTURE.parent / "amendments" / "earned-deduction-25pct.json"


class TestDiff:
    def test_reports_the_semantic_change(self, capsys):
        assert main(["diff", str(FIXTURE), str(AMENDMENT)]) == 0
        out = capsys.readouterr().out
        assert "SEMANTIC" in out
        assert "0.20 -> 0.25" in out

    def test_identical_packages_report_no_changes(self, capsys):
        assert main(["diff", str(FIXTURE), str(FIXTURE)]) == 0
        assert "no changes" in capsys.readouterr().out

    def test_scenario_shows_what_actually_moves(self, capsys):
        main(["diff", str(FIXTURE), str(AMENDMENT),
              "--scenario", str(SCENARIO),
              "--observe", "var.household.net_monthly_income"])
        out = capsys.readouterr().out
        assert "LEGISLATIVE CHANGE IMPACT" in out
        assert "594.0000 -> 481.5000" in out
