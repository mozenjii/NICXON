"""The extraction pass: one clause in, one rule proposal out.

This is the module the whole project has been arranged around, so it is worth being exact
about what it does and does not do. It asks a model to propose a structured rule for a
clause. It then checks that proposal mechanically, and hands the result to a human. It
never decides anything.

Six checks run on every proposal, and none of them can be skipped:

1. **The output parses as IR.** A response that does not validate against the typed model
   is a provider failure, not a rule with problems.
2. **The rule cites the clause it was given.** A proposal that quietly attributes itself to
   a different clause has lost its provenance, and a reviewer reading the clause beside the
   rule would not notice.
3. **Every quote is present in the source.** Checked by `ingest.resolve_span` against the
   verified corpus, not against the model's own claim.
4. **The status is forced.** Whatever the model returns, the proposal is `needs_review`. A
   model may not mark its own work approved (ADR-004), and enforcing that in code rather
   than in the prompt is the difference between a control and a request.
5. **Confidence is recorded, never acted on.** It is carried into `interpretation` for
   audit. Nothing in this file branches on it.
6. **Injection findings escalate.** If the guard flagged the source text, or the model
   reports the clause tried to instruct it, the proposal gains a blocking ambiguity. It is
   never discarded silently — dropping it would hide the attempt from the only party who
   can act on it.

A proposal that fails a check still comes back, carrying diagnostics. The reviewer needs to
see what the model produced *and* why it was rejected; returning nothing teaches them
nothing and hides a systematic failure behind an empty queue.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pydantic

from ..ingest.document import Clause, SourceDocument, resolve_span
from ..ir.rules import Ambiguity, Interpretation, Interpretations, Rule
from ..models.base import ModelProvider, RunMetadata, Settings
from ..verify.diagnostics import Diagnostic
from . import prompts, schemas

PROMPT_ID = "extract-rule"
PROMPT_VERSION = "v1"


@dataclass
class Vocabulary:
    """The identifiers a proposal is allowed to use.

    ADR-018 puts the controlled vocabulary before extraction, and the *Encoding
    legislation* study is why: without shared terms, two competent encoders agreed on
    essentially nothing. A model given free rein over naming reproduces that problem at
    machine speed.
    """

    entities: list[dict] = field(default_factory=list)
    variables: list[dict] = field(default_factory=list)
    parameters: list[dict] = field(default_factory=list)

    @classmethod
    def from_package(cls, package) -> Vocabulary:
        return cls(
            entities=[{"id": e.id, "label": e.label, "kind": e.kind}
                      for e in package.entities],
            variables=[{"id": v.id, "entity": v.entity, "type": v.value_type,
                        "periodicity": v.periodicity, "input": v.input}
                       for v in package.variables],
            parameters=[{"id": p.id, "type": p.value_type,
                         "dimensions": p.dimensions} for p in package.parameters],
        )

    def as_dict(self) -> dict:
        return {"entities": self.entities, "variables": self.variables,
                "parameters": self.parameters}


@dataclass
class RuleProposal:
    """What one extraction attempt produced, and everything wrong with it."""

    clause: Clause
    rule: Rule | None
    ambiguities: list[Ambiguity] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    blocked_reason: str | None = None
    confidence: float | None = None
    notes: str | None = None
    injection_flags: list[str] = field(default_factory=list)
    metadata: RunMetadata | None = None
    raw: str = ""

    @property
    def usable(self) -> bool:
        """A rule survived the checks and may be shown to a reviewer as a candidate.

        Not "correct", and not "approved" — only that nothing mechanical rejected it.
        """
        return self.rule is not None and not [
            d for d in self.diagnostics if d.severity in ("error", "blocking")]

    @property
    def blocking(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == "blocking"]

    def __str__(self) -> str:
        if self.rule is not None:
            head = f"{self.clause.citation} -> {self.rule.id}"
        else:
            head = f"{self.clause.citation} -> declined: {self.blocked_reason}"
        if not self.diagnostics:
            return head
        return head + "\n" + "\n".join(f"    {d}" for d in self.diagnostics)


def _context(clause: Clause, document: SourceDocument, vocabulary: Vocabulary) -> dict:
    """What the model is shown.

    `source_text` is the key the injection guard fences, so the clause and its neighbours
    go there and nothing else does. The vocabulary and the citation are compiler-supplied
    and trusted; putting them inside the fence would tell the model to treat its own
    instructions as untrusted data.
    """
    parent = document.clause(clause.parent_id) if clause.parent_id else None
    children = document.children_of(clause.node_id)
    return {
        "citation": clause.citation,
        "node_id": clause.node_id,
        "source_id": document.source_id,
        "point_in_time": document.point_in_time,
        "source_text": document.subtree_text(clause.node_id),
        "context_text": parent.text if parent is not None else None,
        "has_children": len(children),
        "vocabulary": vocabulary.as_dict(),
    }


def _guard_ambiguity(clause: Clause, reasons: list[str]) -> Ambiguity:
    """An injection finding, expressed as something the review queue already handles.

    Modelling it as a blocking ambiguity rather than a bespoke alert means it inherits the
    behaviour that already exists: it blocks approval, it appears beside the rule, and it
    has to be resolved by a person rather than dismissed.
    """
    return Ambiguity(
        id=f"ambiguity.injection.{clause.node_id}",
        type="untrusted_instruction",
        blocking=True,
        question=(
            "The source text for this clause contains instruction-like content "
            f"({', '.join(reasons)}). Confirm the clause is authentic and that the "
            "proposal reflects the regulation rather than the injected text."
        ),
        interpretations=[
            Interpretations(
                id="authentic",
                description="The wording is genuinely part of the regulation and was "
                            "encoded as text."),
            Interpretations(
                id="tampered",
                description="The source has been altered; re-fetch it and discard this "
                            "proposal."),
        ],
    )


def propose(
    clause: Clause,
    document: SourceDocument,
    *,
    provider: ModelProvider,
    settings: Settings,
    vocabulary: Vocabulary | None = None,
    corpus: dict[str, SourceDocument] | None = None,
) -> RuleProposal:
    """Ask for a rule for one clause, then check what came back."""
    vocabulary = vocabulary or Vocabulary()
    prompt = prompts.load(PROMPT_ID, PROMPT_VERSION)
    context = _context(clause, document, vocabulary)

    proposal = provider.structured_generate(
        task=prompt.system(),
        context=context,
        schema=schemas.extract_schema(),
        settings=settings,
        prompt_id=prompt.id,
        prompt_version=prompt.version,
    )

    result = RuleProposal(
        clause=clause,
        rule=None,
        confidence=proposal.data.get("confidence"),
        notes=proposal.data.get("notes"),
        blocked_reason=proposal.data.get("blocked_reason"),
        injection_flags=list(proposal.injection_flags),
        metadata=proposal.metadata,
        raw=proposal.raw,
    )

    reasons = list(proposal.injection_flags)
    if proposal.data.get("contains_instructions"):
        reasons.append("model:reported_instructions")
    if reasons:
        result.ambiguities.append(_guard_ambiguity(clause, reasons))
        result.diagnostics.append(Diagnostic(
            "RW5010", "blocking",
            f"the source text for {clause.citation} contains instruction-like content",
            object_id=clause.node_id,
            suggestion="re-fetch the source and confirm it is authentic before reviewing",
            details={"flags": reasons}))

    for entry in proposal.data.get("ambiguities") or []:
        result.ambiguities.append(Ambiguity(
            id=f"ambiguity.{clause.node_id}.{len(result.ambiguities)}",
            type=entry.get("type") or "interpretation",
            blocking=bool(entry.get("blocking")),
            question=entry["question"],
            interpretations=entry.get("interpretations", []),
        ))

    payload = proposal.data.get("rule")
    if payload is None:
        if not result.blocked_reason:
            result.diagnostics.append(Diagnostic(
                "RW5011", "warning",
                "no rule was proposed and no reason was given",
                object_id=clause.node_id))
        return result

    try:
        rule = Rule.model_validate(payload)
    except pydantic.ValidationError as exc:
        result.diagnostics.append(Diagnostic(
            "RW2010", "error",
            f"the proposed rule is not valid IR: {exc.error_count()} problem(s)",
            object_id=clause.node_id,
            details={"errors": exc.errors(include_url=False)[:5]}))
        return result

    # Whatever the model asked for, the proposal is unreviewed. Recorded here rather than
    # left to the prompt: a control a model can decline to follow is not a control.
    rule = rule.model_copy(update={"interpretation": Interpretation(
        status="needs_review",
        note=result.notes,
        model_confidence=result.confidence,
    )})

    if not rule.sources:
        result.diagnostics.append(Diagnostic(
            "RW7010", "error", "the proposed rule cites no source",
            rule_id=rule.id, object_id=clause.node_id,
            suggestion="a rule with no provenance cannot be reviewed against anything"))
    else:
        # A span with neither a node id nor a citation identifies nothing. It is dropped
        # from the comparison rather than sorted alongside real addresses — sorting a set
        # containing None raises, and doing so here would crash the error path, which is
        # the worst possible place for a crash.
        cited = {s.node_id or s.citation for s in rule.sources}
        addressed = sorted(c for c in cited if c is not None)
        if clause.node_id not in cited and clause.citation not in cited:
            result.diagnostics.append(Diagnostic(
                "RW1002", "error",
                f"the proposed rule cites {addressed or 'nothing addressable'} but was "
                f"extracted from {clause.citation}",
                rule_id=rule.id, object_id=clause.node_id,
                suggestion="a proposal must cite the clause it was shown"))

    documents = corpus if corpus is not None else {document.source_id: document}
    for span in rule.sources:
        resolution = resolve_span(span, documents)
        if not resolution:
            result.diagnostics.append(Diagnostic(
                "RW1001", "error",
                f"proposed source span does not resolve: {resolution.reason}",
                rule_id=rule.id, object_id=clause.node_id,
                suggestion="quote contiguous text from the cited clause",
                details={"citation": span.citation}))

    result.rule = rule
    return result
