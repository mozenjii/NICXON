"""Deterministic evaluator for an approved rule package.

No model is involved here and none may be. This is the layer whose behaviour must be
reproducible and explainable, which is what keeps the runtime decider a human-authored
rule engine rather than an inference system.

Evaluation runs to a fixed point: rules are applied repeatedly until no assignment
changes. That resolves dependency order without a topological sort, and a stall guard
turns a genuine cycle into an error rather than a hang.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_CEILING, ROUND_DOWN, ROUND_FLOOR, ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal

from ..ir.expressions import (
    Aggregate,
    Arith,
    BoolOp,
    Clamp,
    Compare,
    ConvertPeriod,
    Lit,
    Not,
    Param,
    Piecewise,
    Ref,
    Round,
)
from ..ir.rules import Rule, RulePackage
from .values import UNKNOWN, Value, is_unknown, kleene_all, kleene_any, kleene_not

_ROUNDING = {
    "up": ROUND_CEILING,
    "down": ROUND_FLOOR,
    "half_up": ROUND_HALF_UP,
    "half_even": ROUND_HALF_EVEN,
    "toward_zero": ROUND_DOWN,
}

_MONTHS_PER = {"year": Decimal(12), "month": Decimal(1)}


class EvaluationError(Exception):
    """A defect in the rule package or the inputs. Never a silent unknown."""


@dataclass
class TraceStep:
    rule_id: str
    target: str
    value: Value
    scope: str
    via: str  # "base", "exception:<id>", or "override:<id>"

    def __str__(self) -> str:
        return f"{self.target} = {self.value!r}  [{self.rule_id} {self.via} {self.scope}]"


@dataclass
class Context:
    """Inputs and derived values for one household."""

    household: dict[str, Value] = field(default_factory=dict)
    members: list[dict[str, Value]] = field(default_factory=list)
    on_date: str = "2026-01-01"
    trace: list[TraceStep] = field(default_factory=list)


class ParameterTable:
    """Resolves dated, dimensioned parameter values.

    Values declared in the package are used first; `overrides` supplies the externally
    published tables (poverty guidelines, standard deduction, shelter caps) that the
    regulation references but does not contain.
    """

    def __init__(self, package: RulePackage, overrides: dict | None = None) -> None:
        self._package = package
        self._overrides = overrides or {}

    def get(self, pid: str, coords: dict[str, str], on_date: str) -> Value:
        if pid in self._overrides:
            table = self._overrides[pid]
            if isinstance(table, dict):
                key = tuple(str(coords[d]) for d in sorted(coords)) if coords else ()
                if key in table:
                    return table[key]
                if () in table:
                    return table[()]
                return UNKNOWN
            return table

        param = self._package.parameter(pid)
        if param is None:
            raise EvaluationError(f"unknown parameter: {pid}")
        for pv in param.values:
            # Two independent tests, deliberately not collapsed: the first selects the
            # value in force on the date, the second selects the cell along the
            # parameter's dimensions. Joining them reads as one condition and hides that
            # a parameter can be in force yet have no value at these coordinates.
            if pv.effective_from <= on_date and (pv.effective_to is None or on_date < pv.effective_to):  # noqa: SIM102
                if all(str(coords.get(k)) == v for k, v in pv.at.items()):
                    return Decimal(str(pv.value)) if not isinstance(pv.value, bool) else pv.value
        return UNKNOWN


class Evaluator:
    def __init__(self, package: RulePackage, parameters: ParameterTable | None = None) -> None:
        self.package = package
        self.parameters = parameters or ParameterTable(package)

    # ---------- expression evaluation ----------

    def eval(self, expr, ctx: Context, member: dict | None = None) -> Value:
        e = expr

        if isinstance(e, Lit):
            v = e.value
            return Decimal(str(v)) if isinstance(v, (int,)) and not isinstance(v, bool) else v

        if isinstance(e, Ref):
            if e.id.startswith("var.member."):
                if member is None:
                    raise EvaluationError(f"{e.id} referenced outside a member scope")
                return member.get(e.id, UNKNOWN)
            if e.id == "var.household":
                return "household"
            return ctx.household.get(e.id, UNKNOWN)

        if isinstance(e, Param):
            coords = {k: self.eval(v, ctx, member) for k, v in e.args.items()}
            if any(is_unknown(v) for v in coords.values()):
                return UNKNOWN
            return self.parameters.get(e.id, {k: str(v) for k, v in coords.items()}, ctx.on_date)

        if isinstance(e, Compare):
            left = self.eval(e.left, ctx, member)
            right = self.eval(e.right, ctx, member)
            if is_unknown(left) or is_unknown(right):
                return UNKNOWN
            return {
                "lt": left < right, "lte": left <= right,
                "gt": left > right, "gte": left >= right,
                "eq": left == right, "neq": left != right,
            }[e.op]

        if isinstance(e, BoolOp):
            vals = [self.eval(a, ctx, member) for a in e.args]
            return kleene_all(vals) if e.op == "all" else kleene_any(vals)

        if isinstance(e, Not):
            return kleene_not(self.eval(e.arg, ctx, member))

        if isinstance(e, Arith):
            vals = [self.eval(a, ctx, member) for a in e.args]
            if any(is_unknown(v) for v in vals):
                return UNKNOWN
            return self._arith(e.op, [Decimal(str(v)) for v in vals])

        if isinstance(e, Round):
            v = self.eval(e.arg, ctx, member)
            if is_unknown(v):
                return UNKNOWN
            return Decimal(str(v)).quantize(Decimal(e.to), rounding=_ROUNDING[e.mode])

        if isinstance(e, ConvertPeriod):
            v = self.eval(e.arg, ctx, member)
            if is_unknown(v):
                return UNKNOWN
            if e.method != "divide":
                raise EvaluationError(f"period method not implemented: {e.method}")
            return Decimal(str(v)) * _MONTHS_PER[e.to] / _MONTHS_PER[e.from_]

        if isinstance(e, Clamp):
            v = self.eval(e.arg, ctx, member)
            if is_unknown(v):
                return UNKNOWN
            v = Decimal(str(v))
            if e.min is not None:
                lo = self.eval(e.min, ctx, member)
                if is_unknown(lo):
                    return UNKNOWN
                v = max(v, Decimal(str(lo)))
            if e.max is not None:
                hi = self.eval(e.max, ctx, member)
                if is_unknown(hi):
                    return UNKNOWN
                v = min(v, Decimal(str(hi)))
            return v

        if isinstance(e, Piecewise):
            for case in e.cases:
                hit = self.eval(case.when, ctx, member)
                if is_unknown(hit):
                    return UNKNOWN
                if hit is True:
                    return self.eval(case.then, ctx, member)
            return self.eval(e.otherwise, ctx, member)

        if isinstance(e, Aggregate):
            return self._aggregate(e, ctx)

        raise EvaluationError(f"unsupported expression node: {type(e).__name__}")

    def _arith(self, op: str, vals: list[Decimal]) -> Decimal:
        if not vals:
            raise EvaluationError(f"{op}: needs at least one operand")
        if op == "add":
            return sum(vals, Decimal(0))
        if op == "multiply":
            out = Decimal(1)
            for v in vals:
                out *= v
            return out
        if op == "min":
            return min(vals)
        if op == "max":
            return max(vals)
        out = vals[0]
        for v in vals[1:]:
            if op == "subtract":
                out -= v
            elif op == "divide":
                if v == 0:
                    raise EvaluationError("divide: division by zero")
                out /= v
        return out

    def _aggregate(self, e: Aggregate, ctx: Context) -> Value:
        selected = []
        for m in ctx.members:
            if e.where is not None:
                keep = self.eval(e.where, ctx, m)
                if is_unknown(keep):
                    return UNKNOWN
                if keep is not True:
                    continue
            selected.append(self.eval(e.value, ctx, m))

        # An empty group yields the operator's identity, never unknown.
        if e.op == "count_over":
            return Decimal(len(selected))
        if e.op == "any_over":
            return kleene_any(selected)
        if e.op == "all_over":
            return kleene_all(selected)
        if any(is_unknown(v) for v in selected):
            return UNKNOWN
        nums = [Decimal(str(v)) for v in selected]
        if e.op == "sum_over":
            return sum(nums, Decimal(0))
        if not nums:
            return UNKNOWN
        return min(nums) if e.op == "min_over" else max(nums)

    # ---------- rule application ----------

    def _applicable(self, rule: Rule, on_date: str) -> bool:
        if rule.effective_from > on_date:
            return False
        return rule.effective_to is None or on_date < rule.effective_to

    def _fire(self, rule: Rule, ctx: Context, member: dict | None) -> tuple[str, Value, str] | None:
        """Return (target, value, via), or None if the rule does not apply."""
        guard = self.eval(rule.when, ctx, member)
        if guard is not True:
            return None

        # Lowest matching priority wins; ties are rejected at parse time.
        for exc in sorted(rule.exceptions, key=lambda x: x.priority):
            hit = self.eval(exc.when, ctx, member)
            if is_unknown(hit):
                return (rule.then.assign.target, UNKNOWN, f"exception:{exc.id}(unknown)")
            if hit is True:
                if exc.effect == "disable_base_rule":
                    return None
                assert exc.substitute is not None
                return (
                    exc.substitute.assign.target,
                    self.eval(exc.substitute.assign.value, ctx, member),
                    f"exception:{exc.id}",
                )

        return (rule.then.assign.target, self.eval(rule.then.assign.value, ctx, member), "base")

    def run(self, ctx: Context, max_passes: int = 50) -> Context:
        """Evaluate to a fixed point.

        A rule listed in another rule's `overrides` is skipped while the overriding rule
        can still fire, so a "notwithstanding" clause wins regardless of evaluation order.
        """
        overridden = {rid for r in self.package.rules for rid in r.overrides}
        rules = [r for r in self.package.rules if self._applicable(r, ctx.on_date)]

        for _ in range(max_passes):
            changed = False
            for rule in rules:
                if rule.id in overridden:
                    continue
                scopes: list[tuple[str, dict | None]] = (
                    [(f"member[{i}]", m) for i, m in enumerate(ctx.members)]
                    if rule.then.assign.target.startswith("var.member.")
                    else [("household", None)]
                )
                for scope_name, member in scopes:
                    fired = self._fire(rule, ctx, member)
                    if fired is None:
                        continue
                    target, value, via = fired
                    store = member if target.startswith("var.member.") else ctx.household
                    assert store is not None
                    if target not in store or store[target] != value:
                        store[target] = value
                        ctx.trace.append(TraceStep(rule.id, target, value, scope_name, via))
                        changed = True
            if not changed:
                return ctx

        raise EvaluationError(
            f"no fixed point after {max_passes} passes — the rule package likely has a cycle"
        )
