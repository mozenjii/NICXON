"""Diagnostics.

Codes are stable and machine-readable so a reviewer interface can route them and a
regression test can assert on them. The families follow docs/03_ARCHITECTURE.md:

    RW1xxx  source / ingestion
    RW2xxx  schema / type
    RW3xxx  references / dependencies
    RW4xxx  temporal
    RW5xxx  ambiguity / interpretation
    RW6xxx  tests
    RW7xxx  provenance
    RW8xxx  adapters
    RW9xxx  internal
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Severity = Literal["info", "warning", "error", "blocking"]


@dataclass(frozen=True)
class Diagnostic:
    code: str
    severity: Severity
    message: str
    rule_id: str | None = None
    object_id: str | None = None
    suggestion: str | None = None
    details: dict = field(default_factory=dict)

    def __str__(self) -> str:
        where = f" [{self.rule_id}]" if self.rule_id else ""
        return f"{self.code} {self.severity.upper()}{where}: {self.message}"


@dataclass
class Report:
    diagnostics: list[Diagnostic] = field(default_factory=list)

    def add(self, d: Diagnostic) -> None:
        self.diagnostics.append(d)

    @property
    def blocking(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity == "blocking"]

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.severity in ("error", "blocking")]

    @property
    def ok(self) -> bool:
        """A package is evaluable only when nothing blocks."""
        return not self.errors

    def by_code(self, code: str) -> list[Diagnostic]:
        return [d for d in self.diagnostics if d.code == code]

    def __str__(self) -> str:
        if not self.diagnostics:
            return "no diagnostics"
        return "\n".join(str(d) for d in sorted(self.diagnostics, key=lambda d: d.code))
