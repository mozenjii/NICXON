"""Loading a verified corpus from a source manifest.

The manifest records, for each authoritative snapshot, the citation it represents, the
point in time it was retrieved for, and the sha256 of the bytes retrieved. Loading a
corpus checks those digests. That check is the difference between a provenance claim and a
provenance guarantee, and it is cheap enough that there is no reason to make it optional.

It caught a real failure on first use: with `core.autocrlf` enabled, git rewrote the line
endings of every snapshot on checkout, so every recorded digest failed. The repository now
pins those files as binary — but the check is what made a silent corruption visible, which
is exactly the argument for running it every time rather than trusting the checkout.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

from .document import SourceDocument
from .ecfr import parse_file


class CorpusError(Exception):
    """The corpus on disk does not match what the manifest says it should be."""


@dataclass
class Corpus:
    """Every ingested source, addressed by the id that rules cite."""

    corpus_id: str
    documents: dict[str, SourceDocument] = field(default_factory=dict)
    rights: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def __getitem__(self, source_id: str) -> SourceDocument:
        return self.documents[source_id]

    def __contains__(self, source_id: str) -> bool:
        return source_id in self.documents

    def __len__(self) -> int:
        return len(self.documents)

    @property
    def clauses(self) -> int:
        return sum(len(d.clauses) for d in self.documents.values())

    @property
    def uncertain(self) -> int:
        """Clauses whose position in the hierarchy had to be guessed."""
        return sum(1 for d in self.documents.values()
                   for c in d.clauses if c.uncertain_depth)

    def __str__(self) -> str:
        lines = [f"{self.corpus_id}: {len(self)} sources, {self.clauses} clauses"]
        for source_id, doc in sorted(self.documents.items()):
            flagged = sum(1 for c in doc.clauses if c.uncertain_depth)
            suffix = f", {flagged} uncertain" if flagged else ""
            lines.append(f"  {source_id:16} {len(doc.clauses):4} clauses{suffix}"
                         f"   {doc.title}")
        return "\n".join(lines)


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_manifest(manifest_path: str | Path) -> list[str]:
    """Digest mismatches, as human-readable lines. Empty means the corpus is intact."""
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    problems: list[str] = []
    for entry in manifest.get("sources", []):
        path = manifest_path.parent / entry["file"]
        if not path.exists():
            problems.append(f"{entry['source_id']}: {entry['file']} is missing")
            continue
        expected = entry.get("sha256")
        if not expected:
            problems.append(f"{entry['source_id']}: the manifest records no sha256")
            continue
        actual = sha256_of(path)
        if actual != expected:
            problems.append(
                f"{entry['source_id']}: {entry['file']} hashes to {actual[:16]}… "
                f"but the manifest records {expected[:16]}…")
    return problems


def load_corpus(manifest_path: str | Path, *, verify: bool = True) -> Corpus:
    """Parse every source in a manifest, after checking it is the source recorded.

    `verify=False` exists for working with a snapshot that is deliberately being replaced —
    re-fetching a source and re-recording its digest. It is not an escape hatch for a
    corpus that fails its own check, and a corpus loaded that way is marked in `notes` so
    nothing downstream can mistake it for a verified one.
    """
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    notes: list[str] = []
    if verify:
        problems = verify_manifest(manifest_path)
        if problems:
            raise CorpusError(
                "the source corpus does not match its manifest:\n  "
                + "\n  ".join(problems)
                + "\nRe-fetch the sources, or re-record the digests if the change is "
                  "intended. Do not load an unverified corpus to get past this.")
    else:
        notes.append("loaded without digest verification — provenance is not guaranteed")

    documents: dict[str, SourceDocument] = {}
    for entry in manifest.get("sources", []):
        document = parse_file(
            manifest_path.parent / entry["file"],
            source_id=entry["source_id"],
            citation=entry.get("citation"),
            title=entry.get("title"),
            point_in_time=entry.get("point_in_time"),
            retrieved_at=entry.get("retrieved_at"),
            sha256=entry.get("sha256"),
        )
        documents[entry["source_id"]] = document
        notes.extend(f"{entry['source_id']}: {n}" for n in document.notes)

    return Corpus(
        corpus_id=manifest.get("corpus_id", manifest_path.parent.name),
        documents=documents,
        rights=manifest.get("rights", {}),
        notes=notes,
    )
