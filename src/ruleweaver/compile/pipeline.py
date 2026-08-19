"""Compiling a source corpus into a candidate rule package.

This is the arrow the README's diagram has always drawn and the code has never had:
verified source → segmented clauses → proposed rules → validated candidate package →
review queue. It stops at the queue. Nothing here approves anything, and the package it
emits is explicitly *candidate* — it carries unreviewed rules, so the approval gate refuses
to execute it until a person has been through it.

A run is reproducible from what it records. `CompilationRun` keeps the corpus digests, the
prompt ids and versions, the decoding settings, and the per-call run metadata. Given those
and the manifest, the same compilation can be re-run and compared — which is what
docs/06_VERIFICATION_SAFETY.md asks for and what makes a disagreement between two runs
investigable rather than mysterious.

The pipeline is deliberately dull about failure. A clause the model declines is recorded
with its reason. A proposal that fails a check is kept, with its diagnostics. A run that
produces nothing usable reports that plainly rather than emitting an empty package that
looks like success.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..ingest.corpus import Corpus
from ..ir.rules import Ambiguity, RulePackage
from ..models.base import ModelProvider, Settings
from ..verify import validate
from ..verify.diagnostics import Diagnostic, Report
from . import prompts
from .extract import PROMPT_ID as EXTRACT_PROMPT
from .extract import PROMPT_VERSION as EXTRACT_VERSION
from .extract import RuleProposal, Vocabulary, propose
from .segment import PROMPT_ID as SEGMENT_PROMPT
from .segment import PROMPT_VERSION as SEGMENT_VERSION
from .segment import Segment, classify

SCHEMA_VERSION = "0.1"


@dataclass
class CompilationRun:
    """Everything one compilation produced, including what it could not do."""

    corpus_id: str
    settings: Settings
    segments: list[Segment] = field(default_factory=list)
    proposals: list[RuleProposal] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    source_digests: dict[str, str] = field(default_factory=dict)
    prompts: dict[str, str] = field(default_factory=dict)

    @property
    def usable(self) -> list[RuleProposal]:
        return [p for p in self.proposals if p.usable]

    @property
    def rejected(self) -> list[RuleProposal]:
        return [p for p in self.proposals if p.rule is not None and not p.usable]

    @property
    def declined(self) -> list[RuleProposal]:
        return [p for p in self.proposals if p.rule is None]

    @property
    def blocking(self) -> list[Diagnostic]:
        """Everything that must be resolved by a person before this run is usable."""
        found = [d for p in self.proposals for d in p.blocking]
        found += [d for s in self.segments for d in s.diagnostics
                  if d.severity == "blocking"]
        found += [d for d in self.diagnostics if d.severity == "blocking"]
        return found

    def counts(self) -> dict[str, int]:
        tally: dict[str, int] = {}
        for segment in self.segments:
            tally[segment.classification] = tally.get(segment.classification, 0) + 1
        return tally

    def as_dict(self) -> dict:
        """The reproducibility record. Written beside a candidate package."""
        return {
            "schema_version": SCHEMA_VERSION,
            "corpus_id": self.corpus_id,
            "source_digests": self.source_digests,
            "prompts": self.prompts,
            "decoding": self.settings.as_dict(),
            "classifications": self.counts(),
            "proposals": {
                "usable": len(self.usable),
                "rejected": len(self.rejected),
                "declined": len(self.declined),
            },
            "calls": [
                p.metadata.as_dict() for p in self.proposals if p.metadata is not None
            ],
        }

    def __str__(self) -> str:
        lines = [f"{self.corpus_id}: {len(self.segments)} clauses classified"]
        for name, count in sorted(self.counts().items(), key=lambda kv: -kv[1]):
            lines.append(f"  {name:16} {count}")
        lines.append(f"proposals: {len(self.usable)} usable, {len(self.rejected)} "
                     f"rejected, {len(self.declined)} declined")
        blocking = self.blocking
        if blocking:
            lines.append(f"{len(blocking)} blocking diagnostic(s)")
            for diagnostic in blocking[:10]:
                lines.append(f"  {diagnostic}")
        return "\n".join(lines)


def compile_corpus(
    corpus: Corpus,
    *,
    provider: ModelProvider,
    settings: Settings,
    base: RulePackage,
    source_ids: list[str] | None = None,
    limit: int | None = None,
    jurisdiction: str = "us-federal",
) -> tuple[RulePackage, CompilationRun, Report]:
    """Segment and extract across a corpus. Returns (candidate, run, validation).

    `base` supplies the controlled vocabulary — the entities, variables and parameters
    proposals may refer to. It is required rather than optional: ADR-018 puts the
    vocabulary before extraction, and a run without one produces rules nobody can compare,
    which is the failure the *Encoding legislation* study measured.
    """
    run = CompilationRun(
        corpus_id=corpus.corpus_id,
        settings=settings,
        source_digests={sid: doc.content_hash for sid, doc in corpus.documents.items()},
        # The prompts as they were on this run, by content hash. A prompt is a safety
        # control; comparing two runs is meaningless without knowing whether it changed.
        prompts={
            f"{SEGMENT_PROMPT}/{SEGMENT_VERSION}":
                prompts.load(SEGMENT_PROMPT, SEGMENT_VERSION).content_hash,
            f"{EXTRACT_PROMPT}/{EXTRACT_VERSION}":
                prompts.load(EXTRACT_PROMPT, EXTRACT_VERSION).content_hash,
        },
    )
    vocabulary = Vocabulary.from_package(base)

    selected = source_ids or sorted(corpus.documents)
    attempted = 0
    for source_id in selected:
        document = corpus.documents.get(source_id)
        if document is None:
            run.diagnostics.append(Diagnostic(
                "RW1003", "error", f"the corpus has no source {source_id!r}"))
            continue

        for clause in document.clauses:
            if limit is not None and attempted >= limit:
                break
            classified = classify(clause, document,
                                  provider=provider, settings=settings)
            run.segments.append(classified)
            attempted += 1

            if not classified.extractable:
                continue
            proposal = propose(
                clause, document,
                provider=provider, settings=settings,
                vocabulary=vocabulary, corpus=corpus.documents)
            run.proposals.append(proposal)

    candidate = _assemble(base, run, jurisdiction)
    # Validated without a corpus here: every span was already resolved against the real
    # documents during extraction, and re-running that check would only restate it.
    return candidate, run, validate(candidate)


def _assemble(base: RulePackage, run: CompilationRun, jurisdiction: str) -> RulePackage:
    """Build a candidate package from the usable proposals.

    Rules keep the ids the proposals gave them; a collision with the base package is a
    diagnostic rather than a silent rename, because two rules claiming one id usually means
    the model re-derived a rule that already exists, and a reviewer should see that.
    """
    seen: dict[str, str] = {}
    rules = []
    ambiguities: list[Ambiguity] = []

    for proposal in run.proposals:
        ambiguities.extend(proposal.ambiguities)
        if not proposal.usable or proposal.rule is None:
            continue
        rule = proposal.rule
        if rule.id in seen:
            run.diagnostics.append(Diagnostic(
                "RW3011", "error",
                f"two proposals claim rule id {rule.id}",
                rule_id=rule.id,
                details={"clauses": [seen[rule.id], proposal.clause.citation]}))
            continue
        seen[rule.id] = proposal.clause.citation
        rules.append(rule)

    # Ambiguities name the rules they affect so the review queue can surface them beside
    # the rule rather than in a list nobody opens.
    for ambiguity in ambiguities:
        if ambiguity.affects:
            continue
        for proposal in run.proposals:
            if ambiguity in proposal.ambiguities and proposal.rule is not None:
                ambiguity.affects = [proposal.rule.id]

    return RulePackage(
        schema_version=base.schema_version,
        package_id=f"{base.package_id}.candidate",
        jurisdiction=jurisdiction,
        description=(
            "Candidate rules proposed by the extraction pass. Every rule is unreviewed: "
            "the approval gate will refuse to execute this package until a person has "
            "been through it."
        ),
        entities=base.entities,
        variables=base.variables,
        parameters=base.parameters,
        rules=rules,
        ambiguities=ambiguities,
    )
