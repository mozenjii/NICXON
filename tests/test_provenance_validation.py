"""Provenance validation — RW1001.

Separate from `test_validators.py` because these need the source snapshots on disk. The
split matters: validation has to work without them, so that a deployment executing an
approved package does not have to ship the originals.
"""

from __future__ import annotations

import json

import pytest

from conftest import FIXTURE
from ruleweaver.ingest import load_corpus
from ruleweaver.ir import RulePackage
from ruleweaver.verify import validate

MANIFEST = FIXTURE.parent / "sources" / "manifest.json"


@pytest.fixture(scope="module")
def corpus():
    return load_corpus(MANIFEST)


def package_with(mutate) -> RulePackage:
    doc = json.loads(FIXTURE.read_text(encoding="utf-8"))
    mutate(doc)
    return RulePackage.model_validate(doc)


class TestSpansResolve:
    def test_the_fixture_has_no_provenance_errors(self, package, corpus):
        report = validate(package, corpus=corpus)
        assert report.by_code("RW1001") == []
        assert report.errors == []

    def test_validation_without_a_corpus_skips_the_check(self, package):
        """A deployment that only executes approved rules has no source snapshots."""
        assert validate(package).by_code("RW1001") == []

    def test_a_quote_that_drifted_from_the_source_is_an_error(self, corpus):
        def mutate(doc):
            doc["rules"][3]["sources"][0]["quote"] = "Forty percent of gross earned income."

        report = validate(package_with(mutate), corpus=corpus)
        [found] = report.by_code("RW1001")
        assert found.severity == "error"
        assert "quoted text is not present" in found.message

    def test_a_citation_that_does_not_exist_is_an_error(self, corpus):
        def mutate(doc):
            doc["rules"][0]["sources"][0]["citation"] = "7 CFR 273.9(zz)(99)"
            doc["rules"][0]["sources"][0].pop("term", None)
            doc["rules"][0]["sources"][0].pop("quote", None)

        report = validate(package_with(mutate), corpus=corpus)
        assert any("has no clause cited as" in d.message
                   for d in report.by_code("RW1001"))

    def test_an_unknown_source_id_is_an_error(self, corpus):
        def mutate(doc):
            doc["rules"][0]["sources"][0]["source_id"] = "7cfr-000.0"

        report = validate(package_with(mutate), corpus=corpus)
        assert any("no ingested source" in d.message for d in report.by_code("RW1001"))

    def test_the_diagnostic_names_the_rule_and_the_source(self, corpus):
        def mutate(doc):
            doc["rules"][3]["sources"][0]["quote"] = "not in the regulation"

        [found] = validate(package_with(mutate), corpus=corpus).by_code("RW1001")
        assert found.rule_id == "rule.snap.earned_income_total"
        assert found.details["source_id"] == "7cfr-273.9"

    def test_parameter_spans_are_checked_too(self, corpus):
        """A threshold traceable to nothing is the failure mode that matters most —
        a wrong number with a citation nobody checked."""
        def mutate(doc):
            for param in doc["parameters"]:
                if param.get("sources"):
                    param["sources"][0]["quote"] = "an amount the regulation never states"
                    return
            raise AssertionError("no parameter carries a source span")

        report = validate(package_with(mutate), corpus=corpus)
        assert any(d.object_id and d.object_id.startswith("param.")
                   for d in report.by_code("RW1001"))
