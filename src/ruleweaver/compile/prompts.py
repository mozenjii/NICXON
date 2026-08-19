"""Versioned prompt assets.

Prompts are project artifacts, not string literals scattered through the passes that use
them. Two reasons, both practical rather than tidy:

A compilation has to be reproducible. Run metadata records `prompt_id` and
`prompt_version`, and those are only meaningful if the text they name is a file somebody
can read, diff, and check out at the revision a run used.

A prompt that constrains what a model may do is a safety control. The instruction that the
model may not mark its own work approved belongs somewhere it can be reviewed alongside
the code that enforces it — not buried in a function body where a later edit passes
unnoticed.

Assets live beside this module as `<id>.<version>.md` with a small front matter block.
Loading is strict: an unknown id or version is an error, never a silent fallback to some
other prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from ..hashing import digest

PROMPTS = Path(__file__).parent / "prompts"

_FRONT_MATTER = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.S)


class PromptError(Exception):
    """A prompt asset is missing or malformed."""


@dataclass(frozen=True)
class Prompt:
    """One versioned instruction set, and the digest that pins it."""

    id: str
    version: str
    task: str
    text: str
    path: Path

    @property
    def content_hash(self) -> str:
        return digest(self.text)

    def system(self) -> str:
        """What is sent as the system instruction — the body, without front matter."""
        return self.text


@lru_cache(maxsize=None)
def load(prompt_id: str, version: str) -> Prompt:
    """Load one prompt asset. Cached: the file cannot change mid-compilation."""
    path = PROMPTS / f"{prompt_id}.{version}.md"
    if not path.exists():
        available = ", ".join(sorted(p.name for p in PROMPTS.glob("*.md"))) or "none"
        raise PromptError(
            f"no prompt asset {prompt_id!r} at version {version!r} "
            f"({path.name} does not exist). Available: {available}")

    raw = path.read_text(encoding="utf-8")
    match = _FRONT_MATTER.match(raw)
    if match is None:
        raise PromptError(f"{path.name} has no front matter block")

    meta: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, _, value = line.partition(":")
            meta[key.strip()] = value.strip()

    for required in ("id", "version", "task"):
        if required not in meta:
            raise PromptError(f"{path.name} front matter has no {required!r}")
    if meta["id"] != prompt_id or meta["version"] != version:
        raise PromptError(
            f"{path.name} declares {meta['id']}/{meta['version']} but was loaded as "
            f"{prompt_id}/{version}; the file name and its front matter must agree")

    return Prompt(
        id=meta["id"],
        version=meta["version"],
        task=meta["task"],
        text=raw[match.end():].strip(),
        path=path,
    )


def available() -> list[tuple[str, str]]:
    """Every (id, version) on disk, for a `--help` listing or a reproducibility report."""
    found = []
    for path in sorted(PROMPTS.glob("*.md")):
        stem = path.stem
        prompt_id, _, version = stem.rpartition(".")
        if prompt_id and version:
            found.append((prompt_id, version))
    return found
