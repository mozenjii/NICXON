"""Boundary case generation.

A threshold comparison in legislation is where implementations go wrong: off-by-one at a
limit denies or grants a benefit to real people. For every comparison between a variable
and a threshold, this emits the three cases either side of the edge.

These are DIAGNOSTIC tests. They record what the package currently does, not what the
policy intends. ADR-012 forbids them standing in for policy-intent tests, so every case
produced here carries origin="generated" and an `observed` outcome rather than an
`expected` one. A generated case that disagrees with a hand-written policy-intent test
means the package is wrong, not the test.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from decimal import Decimal

from ..ir.expressions import Compare, Ref
from ..ir.rules import Rule, RulePackage
from ..runtime.evaluator import Context, Evaluator
from ..runtime.values import Value, is_unknown


@dataclass
class GeneratedCase:
    """One probe of a threshold.

    `observed` is what the package does today. It is deliberately not called `expected`:
    nothing here knows what the law intends.
    """

    id: str
    origin: str
    rule_id: str
    probe: str
    value: Decimal
    position: str  # "below" | "at" | "above"
    observed: dict[str, Value] = field(default_factory=dict)
    rationale: str = ""


def _walk(expr):
    """Yield every node in an expression tree."""
    yield expr
    for attr in ("arg", "left", "right", "value", "scope", "where", "otherwise", "min", "max"):
        child = getattr(expr, attr, None)
        if child is not None and hasattr(child, "op"):
            yield from _walk(child)
    for attr in ("args", "cases"):
        seq = getattr(expr, attr, None)
        if isinstance(seq, list):
            for item in seq:
                if hasattr(item, "op"):
                    yield from _walk(item)
                elif hasattr(item, "when"):  # piecewise Case
                    yield from _walk(item.when)
                    yield from _walk(item.then)
    if isinstance(getattr(expr, "args", None), dict):
        for child in expr.args.values():
            yield from _walk(child)


def _comparisons(rule: Rule):
    """Comparisons in the rule's guard, effect and exceptions."""
    roots = [rule.when, rule.then.assign.value]
    for exc in rule.exceptions:
        roots.append(exc.when)
        if exc.substitute is not None:
            roots.append(exc.substitute.assign.value)
    for root in roots:
        for node in _walk(root):
            if isinstance(node, Compare):
                yield node


def generate(
    package: RulePackage,
    baseline: Context,
    evaluator: Evaluator,
    observe: list[str] | None = None,
) -> list[GeneratedCase]:
    """Probe every household-level threshold in the package.

    `baseline` supplies a household the thresholds can be evaluated against; each case
    is run on a deep copy so probes never contaminate one another.
    """
    observe = observe or []
    cases: list[GeneratedCase] = []

    for rule in package.rules:
        for cmp_node in _comparisons(rule):
            # One side must be a plain household variable, the other a computable threshold.
            if isinstance(cmp_node.left, Ref) and not isinstance(cmp_node.right, Ref):
                probe, threshold_expr = cmp_node.left.id, cmp_node.right
            elif isinstance(cmp_node.right, Ref) and not isinstance(cmp_node.left, Ref):
                probe, threshold_expr = cmp_node.right.id, cmp_node.left
            else:
                continue
            if not probe.startswith("var.household."):
                continue

            probe_ctx = copy.deepcopy(baseline)
            evaluator.run(probe_ctx)
            threshold = evaluator.eval(threshold_expr, probe_ctx)
            if is_unknown(threshold) or not isinstance(threshold, Decimal):
                continue

            for offset, position in ((-1, "below"), (0, "at"), (1, "above")):
                value = threshold + Decimal(offset)
                ctx = copy.deepcopy(baseline)
                ctx.household[probe] = value
                # Freeze the probe so the rule that derives it cannot overwrite it.
                frozen = [r for r in package.rules if r.then.assign.target != probe]
                sub = Evaluator(package.model_copy(update={"rules": frozen}), evaluator.parameters)
                sub.run(ctx)
                cases.append(
                    GeneratedCase(
                        id=f"gen.boundary.{rule.id}.{probe.split('.')[-1]}.{position}",
                        origin="generated",
                        rule_id=rule.id,
                        probe=probe,
                        value=value,
                        position=position,
                        observed={k: ctx.household.get(k) for k in observe},
                        rationale=f"{probe} at threshold{offset:+d} for {cmp_node.op} in {rule.id}",
                    )
                )
    return cases
