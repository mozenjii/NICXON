"""Source ingestion against the real SNAP snapshots.

These run on the actual regulation, not on a synthetic sample. A parser for legal
documents that only works on a document written to suit it is not evidence of anything —
every difficult case here (run-in headings, repeating digit levels, definitions with no
markers) came from the corpus rather than from imagination.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from ruleweaver.ingest import (
    Corpus,
    CorpusError,
    load_corpus,
    parse_file,
    resolve_span,
    verify_manifest,
)
from ruleweaver.ir import RulePackage, SourceSpan

SOURCES = Path(__file__).resolve().parents[1] / "examples" / "snap" / "sources"
MANIFEST = SOURCES / "manifest.json"


@pytest.fixture(scope="module")
def corpus() -> Corpus:
    return load_corpus(MANIFEST)


class TestManifestVerification:
    def test_the_committed_corpus_verifies(self):
        assert verify_manifest(MANIFEST) == []

    def test_a_modified_snapshot_is_caught(self, tmp_path):
        """The case that made this necessary: git rewrote line endings on checkout and
        every recorded digest silently stopped matching."""
        staged = tmp_path / "sources"
        shutil.copytree(SOURCES, staged)
        target = staged / "7cfr-273.9.xml"
        target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))

        problems = verify_manifest(staged / "manifest.json")
        assert len(problems) == 1
        assert "7cfr-273.9" in problems[0]

        with pytest.raises(CorpusError, match="does not match its manifest"):
            load_corpus(staged / "manifest.json")

    def test_a_missing_snapshot_is_named(self, tmp_path):
        staged = tmp_path / "sources"
        shutil.copytree(SOURCES, staged)
        (staged / "7cfr-271.2.xml").unlink()
        assert "is missing" in verify_manifest(staged / "manifest.json")[0]

    def test_skipping_verification_is_recorded(self, tmp_path):
        staged = tmp_path / "sources"
        shutil.copytree(SOURCES, staged)
        target = staged / "7cfr-273.9.xml"
        target.write_bytes(target.read_bytes().replace(b"\n", b"\r\n"))

        loaded = load_corpus(staged / "manifest.json", verify=False)
        assert any("provenance is not guaranteed" in note for note in loaded.notes)


class TestParsing:
    def test_every_source_is_present(self, corpus):
        assert set(corpus.documents) == {"7cfr-271.2", "7cfr-273.9", "7cfr-273.10"}

    def test_the_hierarchy_is_almost_entirely_certain(self, corpus):
        """Not a vanity metric: an uncertain clause has a citation that may be wrong, so
        this rate bounds how much of the corpus can carry trustworthy provenance."""
        assert corpus.clauses > 400
        assert corpus.uncertain / corpus.clauses < 0.02

    def test_the_deductions_subsection_is_addressable(self, corpus):
        """273.9(d) and its children are where most of the fixture's rules live. An
        earlier parser lost the whole subsection to a marker it could not place."""
        doc = corpus["7cfr-273.9"]
        for citation in ("7 CFR 273.9(d)", "7 CFR 273.9(d)(1)(i)",
                         "7 CFR 273.9(d)(1)(iii)", "7 CFR 273.9(d)(2)",
                         "7 CFR 273.9(d)(6)(ii)"):
            assert doc.by_citation(citation) is not None, citation

    def test_repeating_digit_levels_survive(self, corpus):
        """The CFR nests digits twice — (e)(2)(ii)(A)(1) is a real citation. A level model
        with one digit level reads the second as a restart of the first and reparents
        every clause after it."""
        doc = corpus["7cfr-273.10"]
        clause = doc.by_citation("7 CFR 273.10(e)(2)(ii)(A)(1)")
        assert clause is not None
        assert clause.depth == 5
        assert "round the 30 percent of net income up" in clause.text

    def test_a_run_in_heading_becomes_its_own_clause(self, corpus):
        """One paragraph, three clauses: (a) heading, then (1), then (i)."""
        doc = corpus["7cfr-273.10"]
        assert doc.by_citation("7 CFR 273.10(a)").text == "(a) Month of application"
        assert doc.by_citation("7 CFR 273.10(a)(1)") is not None
        assert doc.by_citation("7 CFR 273.10(a)(1)(i)") is not None

    def test_definitions_are_individually_addressable(self, corpus):
        doc = corpus["7cfr-271.2"]
        clause = doc.definition("Elderly or disabled member")
        assert clause is not None
        assert clause.node_id == "def-elderly-or-disabled-member"
        assert clause.heading == "Elderly or disabled member"

    def test_a_definition_owns_its_sub_items(self, corpus):
        """Without this the numbered items under a definition are filed at the top of the
        section, and the definition reads as one sentence long."""
        doc = corpus["7cfr-271.2"]
        text = doc.subtree_text("def-elderly-or-disabled-member")
        assert "Is 60 years of age or older" in text
        assert "Receives supplemental security income benefits" in text

    def test_character_offsets_address_the_canonical_text(self, corpus):
        doc = corpus["7cfr-273.9"]
        for clause in doc.clauses[:40]:
            assert doc.slice(clause.start_char, clause.end_char) == clause.text

    def test_a_cross_reference_is_not_mistaken_for_a_clause(self, corpus):
        """"as defined in section 273.2(j)(2)" must not open a clause (j) of this
        section."""
        doc = corpus["7cfr-273.9"]
        assert doc.by_citation("7 CFR 273.9(j)") is None

    def test_editorial_apparatus_is_not_ingested(self, corpus):
        """A source credit line is not law, and a rule must not be able to cite one."""
        doc = corpus["7cfr-273.9"]
        assert all("[FR Doc" not in clause.text for clause in doc.clauses)


class TestSpanResolution:
    def test_every_fixture_span_resolves(self, corpus):
        """The headline claim: each rule's quote is verbatim text from the clause it
        cites. That was false for 14 of 15 rules before ingestion existed to check it."""
        fixture = SOURCES.parent / "rules.json"
        package = RulePackage.model_validate(
            json.loads(fixture.read_text(encoding="utf-8")))

        failures = []
        for rule in package.rules:
            for span in rule.sources:
                result = resolve_span(span, corpus.documents)
                if not result:
                    failures.append(f"{rule.id} / {span.citation}: {result.reason}")
        assert failures == []

    def test_an_unknown_source_is_reported(self, corpus):
        result = resolve_span(SourceSpan(source_id="7cfr-999.9"), corpus.documents)
        assert not result
        assert "no ingested source" in result.reason

    def test_an_unknown_clause_is_reported(self, corpus):
        result = resolve_span(
            SourceSpan(source_id="7cfr-273.9", node_id="p-z-99"), corpus.documents)
        assert not result
        assert "has no clause" in result.reason

    def test_a_quote_that_is_not_there_is_reported(self, corpus):
        result = resolve_span(
            SourceSpan(source_id="7cfr-273.9", citation="7 CFR 273.9(d)(2)",
                       quote="Thirty percent of gross earned income."),
            corpus.documents)
        assert not result
        assert "quoted text is not present" in result.reason

    def test_an_unknown_term_is_reported(self, corpus):
        result = resolve_span(
            SourceSpan(source_id="7cfr-271.2", term="Imaginary member"), corpus.documents)
        assert not result
        assert "defines no term" in result.reason

    def test_whitespace_differences_do_not_fail_a_quote(self, corpus):
        """A quote transcribed from a rendered page differs in line breaks and spacing.
        Treating that as tampering would train reviewers to ignore the check."""
        clause = corpus["7cfr-273.9"].by_citation("7 CFR 273.9(d)(2)")
        spaced = clause.text[4:40].replace(" ", "\n   ")
        result = resolve_span(
            SourceSpan(source_id="7cfr-273.9", citation="7 CFR 273.9(d)(2)", quote=spaced),
            corpus.documents)
        assert result, result.reason

    def test_offsets_outside_the_document_are_rejected(self, corpus):
        result = resolve_span(
            SourceSpan(source_id="7cfr-273.9", start_char=0, end_char=10 ** 9),
            corpus.documents)
        assert not result
        assert "outside the document" in result.reason


class TestParseDirectly:
    def test_parsing_a_file_reads_its_own_heading(self):
        doc = parse_file(SOURCES / "7cfr-273.9.xml", source_id="7cfr-273.9")
        assert doc.citation == "7 CFR 273.9"
        assert doc.title == "Income and deductions"

    def test_the_content_hash_is_stable(self):
        """Two parses of the same bytes agree, so an approval pinned to the content hash
        does not go stale because the file was read twice."""
        first = parse_file(SOURCES / "7cfr-273.9.xml", source_id="7cfr-273.9")
        second = parse_file(SOURCES / "7cfr-273.9.xml", source_id="7cfr-273.9")
        assert first.content_hash == second.content_hash
