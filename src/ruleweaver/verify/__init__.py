"""Deterministic verification. No model is consulted here and none may be."""

from .diagnostics import Diagnostic, Report, Severity
from .validators import validate

__all__ = ["Diagnostic", "Report", "Severity", "validate"]
