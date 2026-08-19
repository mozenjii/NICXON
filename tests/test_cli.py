"""The command line interface is the surface most people will meet first."""

from __future__ import annotations

import json

import pytest

from conftest import FIXTURE
from ruleweaver.cli import main
from ruleweaver.ir import RulePackage

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


class TestApprovalGate:
    """The gate as a user meets it. `--require-approval` is opt-in, so the default
    behaviour is also pinned here: silently gating every existing caller would be a
    breaking change dressed up as a safety improvement."""

    @pytest.fixture()
    def db(self, tmp_path):
        return f"sqlite:///{tmp_path / 'review.db'}"

    def approve_everything(self, db):
        from ruleweaver.approval import current_hashes
        from ruleweaver.review import Decision, ReviewEvent
        from ruleweaver.review.store import ReviewStore, build_engine

        package = RulePackage.model_validate(
            json.loads(FIXTURE.read_text(encoding="utf-8")))
        store = ReviewStore(build_engine(db))
        for rule_id, (rh, sh) in current_hashes(package).items():
            store.append(ReviewEvent(rule_id=rule_id, reviewer="alice",
                                     decision=Decision.APPROVE,
                                     rule_hash=rh, source_hash=sh))

    def test_evaluate_without_the_flag_does_not_gate(self, capsys):
        assert main(["evaluate", str(FIXTURE), str(SCENARIO)]) == 0
        assert "approval gate" not in capsys.readouterr().err

    def test_unreviewed_rules_refuse_to_execute(self, db, capsys):
        assert main(["evaluate", str(FIXTURE), str(SCENARIO),
                     "--require-approval", "--database", db]) == 1
        err = capsys.readouterr().err
        assert "approval gate" in err
        assert "nothing was evaluated" in err

    def test_partial_evaluates_the_approved_subset(self, db, capsys):
        assert main(["evaluate", str(FIXTURE), str(SCENARIO),
                     "--require-approval", "--partial", "--database", db]) == 0
        out = capsys.readouterr().out
        # Inputs still appear; nothing a rule would have decided does.
        assert "var.household.size" in out
        assert "is_income_eligible" not in out

    def test_an_approved_package_evaluates_under_the_gate(self, db, capsys):
        self.approve_everything(db)
        assert main(["evaluate", str(FIXTURE), str(SCENARIO),
                     "--require-approval", "--database", db]) == 0
        out = capsys.readouterr().out
        assert "is_income_eligible" in out
        assert "True" in out


class TestApprovalsCommand:
    @pytest.fixture()
    def db(self, tmp_path):
        return f"sqlite:///{tmp_path / 'review.db'}"

    def test_reports_every_rule_as_unreviewed(self, db, capsys):
        assert main(["approvals", str(FIXTURE), "--database", db]) == 1
        out = capsys.readouterr().out
        assert "0 approved, 15 blocked" in out
        assert "rule.snap.allotment" in out

    def test_exits_zero_once_everything_is_approved(self, db, capsys):
        TestApprovalGate().approve_everything(db)
        assert main(["approvals", str(FIXTURE), "--database", db]) == 0
        assert "15 approved, 0 blocked" in capsys.readouterr().out


class TestIngestCommand:
    MANIFEST = FIXTURE.parent / "sources" / "manifest.json"

    def test_reports_the_corpus(self, capsys):
        assert main(["ingest", str(self.MANIFEST)]) == 0
        out = capsys.readouterr().out
        assert "snap-us-federal" in out
        assert "3 sources" in out

    def test_prints_a_clause_by_citation(self, capsys):
        assert main(["ingest", str(self.MANIFEST), "--clause", "7 CFR 273.9(d)(2)"]) == 0
        assert "Twenty percent of gross earned income" in capsys.readouterr().out

    def test_an_unknown_clause_exits_nonzero(self, capsys):
        assert main(["ingest", str(self.MANIFEST), "--clause", "7 CFR 273.9(zz)"]) == 1
        assert "no clause" in capsys.readouterr().err

    def test_a_corrupted_corpus_stops_the_command(self, tmp_path, capsys):
        import shutil

        staged = tmp_path / "sources"
        shutil.copytree(self.MANIFEST.parent, staged)
        target = staged / "7cfr-273.9.xml"
        target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))

        with pytest.raises(SystemExit) as exc:
            main(["ingest", str(staged / "manifest.json")])
        assert exc.value.code == 1
        assert "does not match its manifest" in capsys.readouterr().err

    def test_validate_with_sources_checks_citations(self, capsys):
        assert main(["validate", str(FIXTURE), "--sources", str(self.MANIFEST)]) == 0
        assert "RW1001" not in capsys.readouterr().out

    def test_validate_with_sources_reports_a_drifted_quote(self, tmp_path, capsys):
        doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
        doc["rules"][3]["sources"][0]["quote"] = "Forty percent of gross earned income."
        path = tmp_path / "drifted.json"
        path.write_text(json.dumps(doc), encoding="utf-8")

        assert main(["validate", str(path), "--sources", str(self.MANIFEST)]) == 1
        assert "RW1001" in capsys.readouterr().out


class TestTokenCommand:
    SECRET = "z" * 48

    def test_a_minted_token_verifies(self, monkeypatch, capsys):
        from ruleweaver.review.identity import ENV_SECRET, SignedTokenResolver

        monkeypatch.setenv(ENV_SECRET, self.SECRET)
        assert main(["token", "alice@example.gov"]) == 0
        token = capsys.readouterr().out.strip()
        assert SignedTokenResolver(self.SECRET).verify(token) == "alice@example.gov"

    def test_only_the_token_reaches_stdout(self, monkeypatch, capsys):
        """So it can be piped. The guidance goes to stderr."""
        from ruleweaver.review.identity import ENV_SECRET

        monkeypatch.setenv(ENV_SECRET, self.SECRET)
        main(["token", "alice"])
        captured = capsys.readouterr()
        assert len(captured.out.strip().splitlines()) == 1
        assert "valid for" in captured.err

    def test_no_secret_is_an_error_with_a_way_out(self, monkeypatch, capsys):
        from ruleweaver.review.identity import ENV_SECRET

        monkeypatch.delenv(ENV_SECRET, raising=False)
        assert main(["token", "alice"]) == 1
        assert "token_urlsafe" in capsys.readouterr().err

    def test_a_reviewer_id_that_would_forge_an_expiry_is_refused(self, monkeypatch, capsys):
        from ruleweaver.review.identity import ENV_SECRET

        monkeypatch.setenv(ENV_SECRET, self.SECRET)
        assert main(["token", "alice|99999999999"]) == 2
        assert "may not contain" in capsys.readouterr().err
