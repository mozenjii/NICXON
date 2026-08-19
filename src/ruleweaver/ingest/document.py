"""The canonical source document model.

Everything downstream cites into this. A rule's `SourceSpan` names a `source_id` and a
`node_id`, and unless those resolve to a real clause with the quoted text still in it, the
provenance guarantee in README principle 2 is a claim rather than a fact.

The model is deliberately flat with explicit parents rather than nested. Legal hierarchy is
reconstructed from paragraph markers, and reconstruction is fallible: a flat list with a
`parent_id` that may be wrong is honest about that, whereas a tree makes a bad guess
structural and unrecoverable.

Character offsets are into `text`, the document's canonical plain-text rendering. They are
not offsets into the XML: the XML is a transport format that the publisher may reflow,
whereas the canonical text is what a reviewer reads and what a quote is checked against.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..hashing import digest

# What separates clauses in a document's canonical text. Character offsets are into
# that rendering, so this cannot change without invalidating every recorded span.
PARAGRAPH_BREAK = "\n\n"


@dataclass(frozen=True)
class Clause:
    """One addressable unit of a source document.

    `node_id` is a path built from the paragraph markers — `p-a-1-i` for (a)(1)(i) — and is
    stable as long as the publisher does not renumber. `citation` is the human form,
    `7 CFR 273.9(a)(1)(i)`, which is what appears in review and in a rule's provenance.
    """

    node_id: str
    citation: str
    text: str
    start_char: int
    end_char: int
    depth: int
    marker: str | None = None
    parent_id: str | None = None
    heading: str | None = None
    # Set when the marker sequence could not be reconciled with the open hierarchy, so a
    # consumer can tell a confident parse from a salvaged one.
    uncertain_depth: bool = False

    @property
    def path(self) -> list[str]:
        return [p for p in self.node_id.split("-")[1:] if p]


@dataclass
class SourceDocument:
    """A verified snapshot of one authoritative source."""

    source_id: str
    citation: str
    title: str
    text: str
    clauses: list[Clause] = field(default_factory=list)
    point_in_time: str | None = None
    retrieved_at: str | None = None
    sha256: str | None = None
    # Non-fatal parse observations, e.g. a marker sequence that had to be salvaged.
    notes: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self._by_id = {c.node_id: c for c in self.clauses}
        self._by_citation = {c.citation: c for c in self.clauses}

    def clause(self, node_id: str) -> Clause | None:
        return self._by_id.get(node_id)

    def by_citation(self, citation: str) -> Clause | None:
        return self._by_citation.get(citation)

    def children_of(self, node_id: str | None) -> list[Clause]:
        return [c for c in self.clauses if c.parent_id == node_id]

    def subtree(self, node_id: str) -> list[Clause]:
        """A clause and everything nested under it, in document order.

        A citation names a subsection, not a paragraph: "7 CFR 273.9(d)" covers (d) and
        all of (d)(1) through (d)(6). Checking a quote against the lead-in paragraph alone
        would reject a correct citation whose quote sits in a child.
        """
        root = self.clause(node_id)
        if root is None:
            return []
        collected = [root]
        frontier = [root.node_id]
        while frontier:
            parent = frontier.pop()
            for child in self.clauses:
                if child.parent_id == parent and child not in collected:
                    collected.append(child)
                    frontier.append(child.node_id)
        return sorted(collected, key=lambda c: c.start_char)

    def subtree_text(self, node_id: str) -> str:
        return PARAGRAPH_BREAK.join(c.text for c in self.subtree(node_id))

    def slice(self, start: int, end: int) -> str:
        return self.text[start:end]

    @property
    def content_hash(self) -> str:
        """Digest of the canonical text, not of the transport bytes.

        The manifest's sha256 pins the file as retrieved; this pins what was read out of
        it. They answer different questions, and an approval that goes stale because the
        publisher reformatted whitespace would be noise.
        """
        return digest(self.text)

    def find(self, needle: str) -> list[Clause]:
        """Clauses whose text contains `needle`. Used to locate a quote's home."""
        return [c for c in self.clauses if needle in c.text]


@dataclass(frozen=True)
class SpanResolution:
    """The outcome of checking one `SourceSpan` against the ingested corpus."""

    ok: bool
    reason: str | None = None
    clause: Clause | None = None

    def __bool__(self) -> bool:
        return self.ok


def resolve_span(span, documents: dict[str, SourceDocument]) -> SpanResolution:
    """Check that a provenance span still points at what it claims to.

    Four separate failures, reported separately because they need different fixes: the
    corpus does not contain the source; the source does not contain the node; the node
    does not contain the quote; the offsets do not agree with the node. The last two are
    the ones that catch a rule whose clause was amended underneath it.
    """
    document = documents.get(span.source_id)
    if document is None:
        return SpanResolution(False, f"no ingested source with id {span.source_id!r}")

    clause = None
    if span.node_id:
        clause = document.clause(span.node_id)
        if clause is None:
            return SpanResolution(
                False, f"{span.source_id} has no clause {span.node_id!r}")
    elif span.citation:
        clause = document.by_citation(span.citation)
        if clause is None:
            return SpanResolution(
                False, f"{span.source_id} has no clause cited as {span.citation!r}")

    if span.quote:
        wanted = _normalise(span.quote)
        if clause is not None:
            # The clause itself, then its subtree. Citing a subsection and quoting one of
            # its paragraphs is normal legal practice, not a provenance failure.
            found = (wanted in _normalise(clause.text)
                     or wanted in _normalise(document.subtree_text(clause.node_id)))
            where = clause.citation
        else:
            found = wanted in _normalise(document.text)
            where = document.citation
        if not found:
            return SpanResolution(
                False, f"the quoted text is not present in {where}", clause)

    if span.start_char is not None and span.end_char is not None:
        if span.end_char > len(document.text) or span.start_char < 0:
            return SpanResolution(
                False, "the character offsets fall outside the document", clause)
        excerpt = document.slice(span.start_char, span.end_char)
        if span.quote and _normalise(span.quote) not in _normalise(excerpt):
            return SpanResolution(
                False, "the character offsets do not contain the quoted text", clause)

    return SpanResolution(True, None, clause)


def _normalise(text: str) -> str:
    """Collapse whitespace before comparing.

    A quote transcribed from a rendered page differs from the source in line breaks and
    runs of spaces. Treating that as a provenance failure would train reviewers to ignore
    the check, which is worse than the laxity.
    """
    return " ".join(text.split())
