"""The segmentation pass: decide what kind of statement a clause makes.

Extraction is expensive and its failure mode is bad — a procedural clause pushed through a
rule extractor produces a plausible rule that encodes nothing. Segmenting first means the
compiler spends its attempts on clauses that can carry a rule, and, more importantly, that
a clause it cannot represent is recorded as such rather than quietly skipped.

The classification is advisory in one direction only. A clause the model calls
`non_computable` is not extracted, and that is a decision the model effectively makes — so
it is recorded with its rationale, appears in the compilation report, and a reviewer can
override it. A clause the model calls `computable` still has to survive extraction and
every check in `extract.py`; nothing here shortens that path.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..ingest.document import Clause, SourceDocument
from ..models.base import ModelProvider, RunMetadata, Settings
from ..verify.diagnostics import Diagnostic
from . import prompts, schemas

PROMPT_ID = "segment"
PROMPT_VERSION = "v1"

# Only these are sent to extraction. Definitions become vocabulary rather than rules, and
# the rest are recorded so the corpus is accounted for end to end — a clause nobody
# classified is indistinguishable from one nobody noticed.
EXTRACTABLE = ("computable",)


@dataclass
class Segment:
    """One clause and what the model made of it."""

    clause: Clause
    classification: str
    rationale: str = ""
    alternative: str | None = None
    confidence: float | None = None
    contains_instructions: bool = False
    injection_flags: list[str] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    metadata: RunMetadata | None = None

    @property
    def extractable(self) -> bool:
        return self.classification in EXTRACTABLE

    @property
    def contested(self) -> bool:
        """The model saw a second defensible reading. Worth a reviewer's attention even
        when the chosen reading is right."""
        return self.alternative is not None and self.alternative != self.classification

    def __str__(self) -> str:
        mark = "*" if self.contested else " "
        return f"{mark} {self.classification:16} {self.clause.citation}"


def classify(
    clause: Clause,
    document: SourceDocument,
    *,
    provider: ModelProvider,
    settings: Settings,
) -> Segment:
    """Classify one clause."""
    prompt = prompts.load(PROMPT_ID, PROMPT_VERSION)
    context = {
        "citation": clause.citation,
        "node_id": clause.node_id,
        # The only untrusted key, and the one the guard fences.
        "source_text": clause.text,
        "depth": clause.depth,
        "has_children": len(document.children_of(clause.node_id)),
    }

    proposal = provider.structured_generate(
        task=prompt.system(),
        context=context,
        schema=schemas.SEGMENT_SCHEMA,
        settings=settings,
        prompt_id=prompt.id,
        prompt_version=prompt.version,
    )

    data = proposal.data
    segment = Segment(
        clause=clause,
        classification=data.get("classification", "structural"),
        rationale=data.get("rationale", ""),
        alternative=data.get("alternative"),
        confidence=data.get("confidence"),
        contains_instructions=bool(data.get("contains_instructions")),
        injection_flags=list(proposal.injection_flags),
        metadata=proposal.metadata,
    )

    if segment.classification not in schemas.CLASSIFICATIONS:
        # Reachable when a provider does not enforce the schema. Treated as unclassified
        # rather than coerced, because guessing which category was meant is exactly the
        # kind of silent repair this compiler is supposed to refuse.
        segment.diagnostics.append(Diagnostic(
            "RW2011", "error",
            f"unknown classification {segment.classification!r}",
            object_id=clause.node_id))
        segment.classification = "structural"

    if segment.injection_flags or segment.contains_instructions:
        segment.diagnostics.append(Diagnostic(
            "RW5010", "blocking",
            f"the text of {clause.citation} contains instruction-like content",
            object_id=clause.node_id,
            details={"flags": segment.injection_flags,
                     "model_reported": segment.contains_instructions}))

    return segment
