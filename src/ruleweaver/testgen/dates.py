"""Date transition case generation.

Legislation changes on a date, and the day either side of that date is where
implementations silently diverge: a rule applied one day early, or a repealed rule still
firing, produces a wrong determination that nobody notices because no test covers the
edge.

For every effective boundary in a package — rule intervals and dated parameter values —
this emits the three cases around it. Like boundary cases these are DIAGNOSTIC: they
record what the package does on each date, not what the policy intends.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import date, timedelta

from ..ir.rules import RulePackage
from ..runtime.evaluator import Context, Evaluator
from ..runtime.values import Value


@dataclass
class DateCase:
    id: str
    origin: str
    on_date: str
    boundary: str
    object_id: str
    position: str  # "before" | "on" | "after"
    observed: dict[str, Value] = field(default_factory=dict)
    rationale: str = ""


def _parse(value: str) -> date | None:
    try:
        return date.fromisoformat(value)
    except (ValueError, TypeError):
        return None


def boundaries(package: RulePackage) -> list[tuple[str, str]]:
    """Every effective boundary in the package, as (date, object_id) pairs.

    A rule's `effective_to` is exclusive by project convention, so it is a boundary in
    its own right: the rule applies the day before and not on the day itself.
    """
    found: set[tuple[str, str]] = set()
    for rule in package.rules:
        found.add((rule.effective_from, rule.id))
        if rule.effective_to:
            found.add((rule.effective_to, rule.id))
    for param in package.parameters:
        for pv in param.values:
            found.add((pv.effective_from, param.id))
            if pv.effective_to:
                found.add((pv.effective_to, param.id))
    return sorted(found)


def generate(
    package: RulePackage,
    baseline: Context,
    evaluator: Evaluator,
    observe: list[str] | None = None,
) -> list[DateCase]:
    observe = observe or []
    cases: list[DateCase] = []

    for boundary, object_id in boundaries(package):
        anchor = _parse(boundary)
        if anchor is None:
            continue
        for delta, position in ((-1, "before"), (0, "on"), (1, "after")):
            when = anchor + timedelta(days=delta)
            ctx = copy.deepcopy(baseline)
            ctx.on_date = when.isoformat()
            try:
                evaluator.run(ctx)
                observed = {k: ctx.household.get(k) for k in observe}
            except Exception as exc:  # a package that cannot evaluate on a date is a finding
                observed = {"__error__": type(exc).__name__}
            cases.append(DateCase(
                id=f"gen.date.{object_id}.{when.isoformat()}",
                origin="generated",
                on_date=when.isoformat(),
                boundary=boundary,
                object_id=object_id,
                position=position,
                observed=observed,
                rationale=f"{position} the {boundary} boundary on {object_id}",
            ))
    return cases


def transitions(cases: list[DateCase], variable: str) -> list[tuple[str, Value, Value]]:
    """Boundaries where the observed value actually changes.

    A boundary that changes nothing is either correctly inert or untested by this
    scenario; a boundary that changes something is where a date bug would live.
    """
    out: list[tuple[str, Value, Value]] = []
    by_boundary: dict[str, dict[str, Value]] = {}
    for case in cases:
        by_boundary.setdefault(case.boundary, {})[case.position] = case.observed.get(variable)
    for boundary, seen in sorted(by_boundary.items()):
        before, after = seen.get("before"), seen.get("after")
        if before != after:
            out.append((boundary, before, after))
    return out
