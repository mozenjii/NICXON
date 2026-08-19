"""The extract command.

Kept separate from `test_cli.py` because these need the source corpus and a replay file,
and because the behaviour under test is mostly about refusing to do the wrong thing:
reaching a paid API by default, reporting an empty run as a success, or writing a candidate
package that looks approved.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from conftest import FIXTURE
from ruleweaver.cli import main
from ruleweaver.ingest import load_corpus
from ruleweaver.ir import RulePackage

MANIFEST = FIXTURE.parent / "sources" / "manifest.json"


@pytest.fixture(scope="module")
def base() -> RulePackage:
    return RulePackage.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


@pytest.fixture()
def replay(tmp_path, base) -> str:
    """Two clauses classified computable, each proposing a rule that cites itself."""
    corpus = load_corpus(MANIFEST)
    template = base.rule("rule.snap.earned_income_deduction").model_dump(
        mode="json", by_alias=True, exclude_none=True)

    responses = []
    for index, clause in enumerate(corpus["7cfr-273.9"].clauses[:2]):
        responses.append({"classification": "computable", "rationale": "a threshold",
                          "confidence": 0.7, "contains_instructions": False})
        rule = dict(template)
        rule["id"] = f"rule.proposed.{index}"
        rule["sources"] = [{"source_id": "7cfr-273.9", "citation": clause.citation,
                            "node_id": clause.node_id, "quote": clause.text[:60]}]
        responses.append({"rule": rule, "blocked_reason": None, "ambiguities": [],
                          "confidence": 0.75, "notes": None,
                          "contains_instructions": False})

    path = tmp_path / "replay.json"
    path.write_text(json.dumps(responses), encoding="utf-8")
    return str(path)


def run(*args) -> int:
    return main(["extract", str(MANIFEST), str(FIXTURE), *args])


class TestDefaults:
    def test_no_provider_means_no_network(self, capsys):
        """Reaching a paid API because a flag was forgotten is a bill and a rate limit at
        the same time."""
        assert run("--limit", "1") == 2
        assert "no model will be called" not in capsys.readouterr().out

    def test_an_unknown_provider_is_a_usage_error(self, capsys):
        with pytest.raises(SystemExit):
            run("--provider", "telepathy")


class TestCompiling:
    def test_a_replayed_run_produces_candidates(self, replay, capsys):
        assert run("--source", "7cfr-273.9", "--limit", "2", "--replay", replay) == 0
        out = capsys.readouterr().out
        assert "2 clauses classified" in out
        assert "2 usable" in out

    def test_the_candidate_and_its_run_record_are_written(self, replay, tmp_path, capsys):
        out_path = tmp_path / "candidate.json"
        assert run("--source", "7cfr-273.9", "--limit", "2",
                   "--replay", replay, "--out", str(out_path)) == 0

        candidate = json.loads(out_path.read_text(encoding="utf-8"))
        assert candidate["package_id"].endswith(".candidate")
        assert len(candidate["rules"]) == 2

        record = json.loads(
            out_path.with_suffix(".run.json").read_text(encoding="utf-8"))
        assert record["prompts"]["extract-rule/v1"].startswith("sha256:")
        assert record["source_digests"]["7cfr-273.9"].startswith("sha256:")

    def test_the_written_candidate_validates(self, replay, tmp_path):
        out_path = tmp_path / "candidate.json"
        run("--source", "7cfr-273.9", "--limit", "2", "--replay", replay,
            "--out", str(out_path))
        assert main(["validate", str(out_path)]) == 0

    def test_every_written_rule_is_unreviewed(self, replay, tmp_path):
        out_path = tmp_path / "candidate.json"
        run("--source", "7cfr-273.9", "--limit", "2", "--replay", replay,
            "--out", str(out_path))
        candidate = json.loads(out_path.read_text(encoding="utf-8"))
        assert all(r["interpretation"]["status"] == "needs_review"
                   for r in candidate["rules"])

    def test_the_gate_refuses_a_fresh_candidate(self, replay, tmp_path, capsys):
        out_path = tmp_path / "candidate.json"
        run("--source", "7cfr-273.9", "--limit", "2", "--replay", replay,
            "--out", str(out_path))
        capsys.readouterr()

        database = f"sqlite:///{tmp_path / 'review.db'}"
        assert main(["approvals", str(out_path), "--database", database]) == 1
        assert "0 approved, 2 blocked" in capsys.readouterr().out

    def test_a_run_that_proposes_nothing_exits_nonzero(self, tmp_path, capsys):
        """An empty queue is how a broken prompt looks like success."""
        path = tmp_path / "replay.json"
        path.write_text(json.dumps([
            {"classification": "procedural", "rationale": "directs the agency",
             "confidence": 0.5, "contains_instructions": False},
        ]), encoding="utf-8")

        assert run("--source", "7cfr-273.9", "--limit", "1", "--replay", str(path)) == 1
        assert "0 usable" in capsys.readouterr().out

    def test_running_out_of_recorded_responses_is_reported(self, tmp_path, capsys):
        path = tmp_path / "replay.json"
        path.write_text("[]", encoding="utf-8")
        assert run("--limit", "1", "--replay", str(path)) == 1
        assert "provider failed" in capsys.readouterr().err
