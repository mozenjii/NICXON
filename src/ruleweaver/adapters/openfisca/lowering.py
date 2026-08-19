"""Lowering the RuleWeaver expression AST to OpenFisca formula source.

ADR-019 settled what this is: OpenFisca rules are Python `Variable` subclasses whose
`formula` methods compute over vectorised NumPy arrays. Only parameters are data. So the
adapter is a **code generator**, and lowering is the part that turns a closed expression
tree into Python source text.

The IR and OpenFisca do not agree about one thing, and it is the important one.

**OpenFisca has no unknown.** Every variable has a type default — 0 for a number, False for
a boolean — and a fact nobody supplied is indistinguishable from a fact that is genuinely
zero. The IR spends its whole design refusing that conflation: a missing input evaluates to
`UNKNOWN` and propagates, so "we have no income figure for this household" never becomes
"this household has no income". Lowering to OpenFisca loses that distinction.

It is not repairable inside the adapter, so it is reported instead. Every export emits
`RW8001`, and the generated module says the same thing at the top of the file. An adapter
that quietly dropped four-state semantics would be producing a model that denies benefits
for missing paperwork while claiming to implement the same rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from ...ir.expressions import (
    Aggregate,
    Arith,
    BoolOp,
    Clamp,
    Compare,
    ConvertPeriod,
    Expr,
    Lit,
    Not,
    Param,
    Piecewise,
    Ref,
    Round,
)

_COMPARE = {"lt": "<", "lte": "<=", "gt": ">", "gte": ">=", "eq": "==", "neq": "!="}
_ARITH = {"add": " + ", "subtract": " - ", "multiply": " * ", "divide": " / "}
_ROUNDING = {"up": "np.ceil", "down": "np.floor", "toward_zero": "np.trunc"}
_MONTHS = {"day": Decimal(1) / Decimal(30), "month": Decimal(1), "year": Decimal(12)}


class Unlowerable(Exception):
    """A construct with no faithful OpenFisca equivalent."""


@dataclass
class Lowered:
    """Generated source, plus what the entity model has to provide for it to run."""

    source: str
    uses_numpy: bool = False
    person_vars: set[str] = field(default_factory=set)
    household_vars: set[str] = field(default_factory=set)
    parameters: set[str] = field(default_factory=set)


class Lowerer:
    """Turns one expression into a Python expression string.

    Names are short on purpose. The generated formulas read as OpenFisca code, which is
    what someone maintaining the export will compare against the regulation.
    """

    def __init__(self, *, person_entity: str = "household_member") -> None:
        self.person_entity = person_entity
        self.result = Lowered(source="")

    def lower(self, expr: Expr) -> Lowered:
        """Lower one expression, discarding any previous state."""
        self.result = Lowered(source="")
        self.result.source = self.expression(expr)
        return self.result

    def expression(self, expr: Expr) -> str:
        """Lower a sub-expression into the *running* result.

        Separate from `lower` so a caller assembling several expressions into one formula —
        a rule and its exceptions, say — accumulates one set of variable and parameter
        requirements rather than losing all but the last.
        """
        return self._expr(expr)

    # ---------- names ----------

    def _leaf(self, identifier: str) -> str:
        """`var.household.size` becomes `size`; the entity decides who is asked."""
        return identifier.rsplit(".", 1)[-1]

    def _variable(self, identifier: str) -> str:
        leaf = self._leaf(identifier)
        if identifier.startswith("var.member.") or identifier.startswith("var.person."):
            self.result.person_vars.add(leaf)
            return f"person('{leaf}', period)"
        self.result.household_vars.add(leaf)
        return f"household('{leaf}', period)"

    def _parameter(self, node: Param) -> str:
        path = node.id.removeprefix("param.")
        self.result.parameters.add(node.id)
        base = f"parameters(period).{path}"
        if not node.args:
            return base
        # A dimensioned parameter becomes a node lookup per coordinate. OpenFisca indexes
        # by string key, so each coordinate is formatted by `_key`, emitted alongside the
        # generated variables. Plain `str()` is wrong here: an index that has been through
        # `np.clip` is a float, and `str(6.0)` is "6.0", which matches no parameter node.
        for name in sorted(node.args):
            base = f"{base}[_key({self._expr(node.args[name])})]"
        return base

    # ---------- expressions ----------

    def _expr(self, e: Expr) -> str:
        if isinstance(e, Lit):
            if e.value is None:
                raise Unlowerable("a null literal has no OpenFisca equivalent")
            if isinstance(e.value, bool):
                return "True" if e.value else "False"
            if isinstance(e.value, str):
                return repr(e.value)
            return str(e.value)

        if isinstance(e, Ref):
            return self._variable(e.id)

        if isinstance(e, Param):
            return self._parameter(e)

        if isinstance(e, Compare):
            return f"({self._expr(e.left)} {_COMPARE[e.op]} {self._expr(e.right)})"

        if isinstance(e, BoolOp):
            self.result.uses_numpy = True
            parts = ", ".join(self._expr(a) for a in e.args)
            # `*` and `+` on boolean arrays would work but read as arithmetic. The reduce
            # form says what it means and keeps n-ary clauses n-ary.
            reducer = "logical_and" if e.op == "all" else "logical_or"
            return f"np.{reducer}.reduce([{parts}])"

        if isinstance(e, Not):
            self.result.uses_numpy = True
            return f"np.logical_not({self._expr(e.arg)})"

        if isinstance(e, Arith):
            return self._arith(e)

        if isinstance(e, Round):
            return self._round(e)

        if isinstance(e, ConvertPeriod):
            factor = _MONTHS[e.to] / _MONTHS[e.from_]
            if e.method != "divide":
                raise Unlowerable(f"period method {e.method!r} is not supported")
            return f"({self._expr(e.arg)} * {factor})"

        if isinstance(e, Clamp):
            self.result.uses_numpy = True
            low = self._expr(e.min) if e.min is not None else "-np.inf"
            high = self._expr(e.max) if e.max is not None else "np.inf"
            return f"np.clip({self._expr(e.arg)}, {low}, {high})"

        if isinstance(e, Piecewise):
            self.result.uses_numpy = True
            conditions = ", ".join(self._expr(c.when) for c in e.cases)
            values = ", ".join(self._expr(c.then) for c in e.cases)
            return (f"np.select([{conditions}], [{values}], "
                    f"default={self._expr(e.otherwise)})")

        if isinstance(e, Aggregate):
            return self._aggregate(e)

        raise Unlowerable(f"no lowering for {type(e).__name__}")

    def _arith(self, e: Arith) -> str:
        if e.op in _ARITH:
            return "(" + _ARITH[e.op].join(self._expr(a) for a in e.args) + ")"
        self.result.uses_numpy = True
        fn = "np.minimum" if e.op == "min" else "np.maximum"
        folded = self._expr(e.args[0])
        for arg in e.args[1:]:
            folded = f"{fn}({folded}, {self._expr(arg)})"
        return folded

    def _round(self, e: Round) -> str:
        self.result.uses_numpy = True
        inner = self._expr(e.arg)
        quantum = Decimal(e.to)
        scaled = inner if quantum == 1 else f"({inner}) / {quantum}"
        if e.mode in _ROUNDING:
            rounded = f"{_ROUNDING[e.mode]}({scaled})"
        elif e.mode == "half_even":
            # np.round is half-to-even, which is the only mode NumPy gives directly.
            rounded = f"np.round({scaled})"
        elif e.mode == "half_up":
            # NumPy has no half-up. Adding half before flooring is the standard
            # equivalent for non-negative values, and benefit amounts are non-negative.
            rounded = f"np.floor(({scaled}) + 0.5)"
        else:
            raise Unlowerable(f"rounding mode {e.mode!r} has no NumPy equivalent")
        return rounded if quantum == 1 else f"({rounded} * {quantum})"

    def _aggregate(self, e: Aggregate) -> str:
        if e.where is not None:
            raise Unlowerable(
                "a filtered aggregation needs a per-member mask variable; declare the "
                "filter as its own boolean variable and aggregate that")
        value = self._expr(e.value)
        if e.op == "sum_over":
            return f"household.sum({value})"
        if e.op == "any_over":
            return f"household.any({value})"
        if e.op == "all_over":
            return f"household.all({value})"
        if e.op == "count_over":
            return f"household.sum({value} * 1)"
        if e.op in ("min_over", "max_over"):
            self.result.uses_numpy = True
            reducer = "min" if e.op == "min_over" else "max"
            return f"household.{reducer}({value})"
        raise Unlowerable(f"aggregation {e.op!r} has no OpenFisca equivalent")
