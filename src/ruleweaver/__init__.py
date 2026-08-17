"""RuleWeaver — a compiler for turning rules and regulations into executable form."""

from __future__ import annotations

import json
from pathlib import Path

from .ir import RulePackage
from .verify import Report, validate

__version__ = "0.1.0"

__all__ = ["InvalidPackage", "RulePackage", "__version__", "load", "loads", "validate"]


class InvalidPackage(Exception):
    """A package that failed deterministic validation.

    Raised rather than returned so an invalid package cannot be evaluated by a caller
    who forgot to check. docs/06_VERIFICATION_SAFETY.md forbids bypassing validation for
    convenience, and the convenient thing is exactly what a returned report invites.
    """

    def __init__(self, report: Report) -> None:
        self.report = report
        errors = report.errors
        detail = "\n".join(f"  {d}" for d in errors)
        super().__init__(f"{len(errors)} validation error(s):\n{detail}")


def loads(document: dict, *, verify: bool = True) -> RulePackage:
    """Parse and validate a rule package.

    `verify=False` exists for tests that deliberately construct a broken package. It is
    not an escape hatch for production loading, and nothing in this repository uses it
    outside the validator's own test suite.
    """
    package = RulePackage.model_validate(document)
    if verify:
        report = validate(package)
        if not report.ok:
            raise InvalidPackage(report)
    return package


def load(path: str | Path, *, verify: bool = True) -> RulePackage:
    return loads(json.loads(Path(path).read_text(encoding="utf-8")), verify=verify)
