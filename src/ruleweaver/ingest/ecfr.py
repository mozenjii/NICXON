"""Ingesting eCFR section XML.

eCFR serves a section as a `DIV8` element containing a `HEAD` and a flat run of `P`
elements. Structure is carried by the paragraph markers, not by nesting, so hierarchy is
reconstructed here (see `markers.py`) rather than read off the tree.

Two things are deliberately not done:

**No network access.** This parses bytes already on disk and verified against the manifest.
Fetching is a separate, auditable step: a compiler pass that silently re-downloads its
input cannot be reproduced, and eCFR directs programmatic use to its API rather than to
the HTML site.

**No text normalisation beyond whitespace.** The canonical text is what a reviewer reads
and what a quote is checked against, so rewriting it — expanding abbreviations, fixing
typography — would break provenance for a cosmetic gain.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .document import PARAGRAPH_BREAK, Clause, SourceDocument, slugify
from .markers import Hierarchy, MARKER_RE, split_runin

# Editorial apparatus, not regulatory text. `CITA` is the source credit line, `EDNOTE` an
# editorial note, `PSPACE`/`HED` layout. Ingesting them as clauses would let a rule cite a
# footnote as if it were law.
_SKIP_TAGS = {"CITA", "EDNOTE", "HED", "PSPACE", "SECAUTH", "AUTH", "SOURCE"}

_HEADING_RE = re.compile(r"^§+\s*([\d.]+[A-Za-z]?)\s+(.*?)\.?$")


# A definitions paragraph: "Access device means any card, plate, ...". These carry no
# marker, so without this every definition in 7 CFR 271.2 would share one citation and
# none would be individually addressable — which defeats ADR-018, where the controlled
# vocabulary is meant to be traceable term by term.
_DEFINITION_RE = re.compile(r"^(?P<term>[A-Z][^.]{0,79}?)\s+means\b")


def _flatten(element: ET.Element) -> str:
    """All text under `element`, with inline markup dropped and whitespace collapsed.

    `<I>` marks defined terms and `<E>` emphasis; both are typography. Keeping them would
    mean every quote comparison had to strip tags, and dropping them costs nothing a
    reviewer needs.
    """
    parts: list[str] = []
    if element.text:
        parts.append(element.text)
    for child in element:
        if child.tag == "img":
            # A rendered formula image. Recorded so the clause is not silently truncated;
            # a rule depending on one must be encoded by hand.
            parts.append("[formula image]")
        else:
            parts.append(_flatten(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join("".join(parts).split())


def _heading(root: ET.Element) -> tuple[str | None, str | None]:
    head = root.find("HEAD")
    if head is None:
        return None, None
    text = _flatten(head)
    match = _HEADING_RE.match(text)
    if match:
        return match.group(1), match.group(2)
    return None, text or None


def parse_section(
    xml_bytes: bytes,
    *,
    source_id: str,
    citation: str | None = None,
    title: str | None = None,
    point_in_time: str | None = None,
    retrieved_at: str | None = None,
    sha256: str | None = None,
) -> SourceDocument:
    """Parse one eCFR section into a `SourceDocument`.

    `citation` and `title` are read from the document's own heading when not supplied, so
    the manifest and the document cannot disagree without it being visible.
    """
    root = ET.fromstring(xml_bytes)
    number, heading_text = _heading(root)
    section = number or (root.get("N") or source_id)
    base_citation = citation or f"7 CFR {section}"
    doc_title = title or heading_text

    hierarchy = Hierarchy()
    # The definition currently being read, if any. Sub-items of a definition carry
    # ordinary markers and no indication of which definition they belong to, so
    # without this every one of them would be filed at the top of the section.
    definition_root: str | None = None
    clauses: list[Clause] = []
    notes: list[str] = []
    chunks: list[str] = []
    cursor = 0

    for element in root:
        if element.tag in _SKIP_TAGS or element.tag == "HEAD":
            continue
        text = _flatten(element)
        if not text:
            continue

        for segment in split_runin(text, hierarchy):
            match = MARKER_RE.match(segment)
            definition = None
            if match:
                marker = match.group(1)
                path, uncertain = hierarchy.place(marker)
            else:
                # An unmarked paragraph continues whatever is currently open —
                # introductory text under a heading, or a second paragraph of the same
                # subsection.
                marker = None
                definition = _DEFINITION_RE.match(segment)
                if definition is not None:
                    # A new definition is a new top-level entry, so it closes every open
                    # level. Without this reset a definition that follows a numbered
                    # sub-list inherits that list's depth and is filed underneath it.
                    hierarchy.levels = []
                path, uncertain = [lv.marker for lv in hierarchy.levels], False

            if definition is not None and not path:
                term = definition.group("term")
                node_id = f"def-{slugify(term)}"
                clause_citation = f'{base_citation} (definition of "{term}")'
            else:
                node_id = "p" + "".join(f"-{p}" for p in path) if path else "p"
                clause_citation = base_citation + "".join(f"({p})" for p in path)

            # An unmarked continuation shares its parent's identity, which would collide.
            # Suffixing keeps every clause individually addressable.
            if any(c.node_id == node_id for c in clauses):
                existing = sum(1 for c in clauses if c.node_id.split("#")[0] == node_id)
                node_id = f"{node_id}#{existing}"

            start_char = cursor
            end_char = start_char + len(segment)
            chunks.append(segment)
            cursor = end_char + len(PARAGRAPH_BREAK)

            parent_path = path[:-1]
            if parent_path:
                parent_id = "p" + "".join(f"-{p}" for p in parent_path)
            else:
                parent_id = definition_root
            if parent_id is not None and not any(
                    c.node_id.split("#")[0] == parent_id for c in clauses):
                # A child whose parent was never emitted. Real in amended sections;
                # recorded so a broken citation chain is visible, not inferred later.
                notes.append(f"{clause_citation} has no ingested parent {parent_id}")
                parent_id = None

            if uncertain:
                notes.append(f"marker sequence unclear at {clause_citation}")

            clauses.append(Clause(
                node_id=node_id,
                citation=clause_citation,
                text=segment,
                start_char=start_char,
                end_char=end_char,
                depth=len(path),
                marker=marker,
                parent_id=parent_id,
                heading=definition.group("term") if definition is not None else None,
                uncertain_depth=uncertain,
            ))

            if definition is not None:
                definition_root = node_id
            elif not path:
                # Unmarked, undefined text ends the definition it followed.
                definition_root = None

    return SourceDocument(
        source_id=source_id,
        citation=base_citation,
        title=doc_title or base_citation,
        text=PARAGRAPH_BREAK.join(chunks),
        clauses=clauses,
        point_in_time=point_in_time,
        retrieved_at=retrieved_at,
        sha256=sha256,
        notes=notes,
    )


def parse_file(path: str | Path, **kwargs) -> SourceDocument:
    """Parse from disk. Reads bytes, not text, so the digest is over what was retrieved."""
    return parse_section(Path(path).read_bytes(), **kwargs)
