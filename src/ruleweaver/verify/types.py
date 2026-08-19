"""Type checking the expression AST.

The last P0 in the backlog, and the gap it leaves is specific: validation resolved every
reference and detected every cycle, but nothing checked that the *types* on either side of
an operator could meet. A rule comparing a money amount to a date, or summing a boolean,
passed validation and failed at evaluation — or worse, did not fail, because Python will
happily compare a `Decimal` to an `int` and add `True` to a number.

Inference is bottom-up and total. Every node gets a type or `UNTYPED`, and `UNTYPED` never
produces a cascade of complaints: an unresolvable reference is already reported by the
reference resolver, and repeating it here as six type errors buries the one diagnostic that
matters.

The numeric family is ordered `integer < decimal < money`, and arithmetic widens. Money is
the widest deliberately: an amount that has been through a rate stays an amount, and a rule
that assigns a plain decimal to a money variable is more likely to be right than one
assigning money to a count.
"""

from __future__ import annotations

from decimal import Decimal

from ..ir.expressions import (
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
from ..ir.rules import Rule, RulePackage
from .diagnostics import Diagnostic, Report

UNTYPED = "untyped"

NUMERIC = ("integer", "decimal", "money")
ORDERABLE = (*NUMERIC, "date", "string")


def _widest(left: str, right: str) -> str:
    return left if NUMERIC.index(left) >= NUMERIC.index(right) else right


def _is_numeric(kind: str) -> bool:
    return kind in NUMERIC


def _comparable(left: str, right: str) -> bool:
    """Whether two types may meet in an ordering comparison.

    Numerics compare with numerics; everything else only with itself. `enumeration` is
    excluded from ordering on purpose — the order of an enumeration's members is an
    artifact of how it was written down, not a fact about the world.
    """
    if UNTYPED in (left, right):
        return True
    if _is_numeric(left) and _is_numeric(right):
        return True
    return left == right and left in ORDERABLE


class TypeChecker:
    """Infers expression types against a package's declarations."""

    def __init__(self, package: RulePackage, report: Report) -> None:
        self.package = package
        self.report = report
        self.rule_id: str | None = None

    def _fail(self, code: str, message: str, **details) -> str:
        self.report.add(Diagnostic(code, "error", message, rule_id=self.rule_id,
                                   details=details))
        return UNTYPED

    def check_rule(self, rule: Rule) -> None:
        self.rule_id = rule.id

        condition = self.infer(rule.when)
        if condition not in ("boolean", UNTYPED):
            self._fail("RW2003",
                       f"a rule condition must be boolean, not {condition}",
                       op=getattr(rule.when, "op", None))

        self._check_assignment(rule.then.assign.target, self.infer(rule.then.assign.value),
                               where="then")

        for exception in rule.exceptions:
            guard = self.infer(exception.when)
            if guard not in ("boolean", UNTYPED):
                self._fail("RW2003",
                           f"exception {exception.id} has a {guard} condition, not boolean")
            if exception.substitute is not None:
                self._check_assignment(
                    exception.substitute.assign.target,
                    self.infer(exception.substitute.assign.value),
                    where=f"exception {exception.id}")
        self.rule_id = None

    def _check_assignment(self, target: str, produced: str, *, where: str) -> None:
        declared = self.package.variable(target)
        if declared is None or produced is UNTYPED:
            # An unknown target is RW3xxx's finding, not this pass's.
            return
        expected = declared.value_type
        if expected == produced:
            return
        if _is_numeric(expected) and _is_numeric(produced):
            # Widening within the numeric family is allowed; narrowing money to an
            # integer count is not, because it silently discards the amount's meaning.
            if NUMERIC.index(produced) <= NUMERIC.index(expected):
                return
            self._fail("RW2004",
                       f"{where} assigns {produced} to {target}, declared {expected}",
                       target=target, produced=produced, declared=expected)
            return
        self._fail("RW2004",
                   f"{where} assigns {produced} to {target}, declared {expected}",
                   target=target, produced=produced, declared=expected)

    # ---------- inference ----------

    def infer(self, e: Expr) -> str:
        if isinstance(e, Lit):
            return self._literal(e)
        if isinstance(e, Ref):
            declared = self.package.variable(e.id)
            return declared.value_type if declared is not None else UNTYPED
        if isinstance(e, Param):
            parameter = self.package.parameter(e.id)
            # Dimension coordinates are expressions too, and a coordinate computed from a
            # boolean is a mistake worth reporting even though it does not change the
            # parameter's own type.
            for arg in e.args.values():
                self.infer(arg)
            return parameter.value_type if parameter is not None else UNTYPED
        if isinstance(e, Compare):
            return self._compare(e)
        if isinstance(e, BoolOp):
            for arg in e.args:
                kind = self.infer(arg)
                if kind not in ("boolean", UNTYPED):
                    self._fail("RW2005", f"'{e.op}' takes boolean operands, got {kind}")
            return "boolean"
        if isinstance(e, Not):
            kind = self.infer(e.arg)
            if kind not in ("boolean", UNTYPED):
                self._fail("RW2005", f"'not' takes a boolean operand, got {kind}")
            return "boolean"
        if isinstance(e, Arith):
            return self._arith(e)
        if isinstance(e, Round):
            return self._numeric_unary(e.arg, "round")
        if isinstance(e, ConvertPeriod):
            return self._numeric_unary(e.arg, "convert_period")
        if isinstance(e, Clamp):
            return self._clamp(e)
        if isinstance(e, Piecewise):
            return self._piecewise(e)
        if isinstance(e, Aggregate):
            return self._aggregate(e)
        return UNTYPED

    def _literal(self, e: Lit) -> str:
        # Order matters: bool is a subclass of int in Python, so it must be tested first.
        if isinstance(e.value, bool):
            return "boolean"
        if isinstance(e.value, int):
            return "integer"
        if isinstance(e.value, Decimal):
            return "decimal"
        if isinstance(e.value, str):
            return "string"
        return UNTYPED

    def _compare(self, e: Compare) -> str:
        left = self.infer(e.left)
        right = self.infer(e.right)
        if e.op in ("eq", "neq"):
            # Equality is defined between any two values of the same family. Comparing a
            # string to a number is always false, which is far more likely to be a mistake
            # in the encoding than an intended test.
            if not _comparable(left, right) and left != right:
                self._fail("RW2006",
                           f"'{e.op}' compares {left} with {right}, which can never be equal")
        elif not _comparable(left, right):
            self._fail("RW2006", f"'{e.op}' cannot order {left} against {right}")
        elif left not in (*ORDERABLE, UNTYPED) or right not in (*ORDERABLE, UNTYPED):
            self._fail("RW2006", f"'{e.op}' has no ordering for {left}")
        return "boolean"

    def _arith(self, e: Arith) -> str:
        kinds = [self.infer(a) for a in e.args]
        result = "integer"
        for kind in kinds:
            if kind is UNTYPED:
                return UNTYPED
            if not _is_numeric(kind):
                return self._fail("RW2007",
                                  f"'{e.op}' takes numeric operands, got {kind}")
            result = _widest(result, kind)
        # Division of whole numbers is not whole. Reporting the result as an integer would
        # let a rule assign a fraction to a count and pass.
        return "decimal" if e.op == "divide" and result == "integer" else result

    def _numeric_unary(self, arg: Expr, label: str) -> str:
        kind = self.infer(arg)
        if kind is UNTYPED:
            return UNTYPED
        if not _is_numeric(kind):
            return self._fail("RW2007", f"'{label}' takes a numeric operand, got {kind}")
        return kind

    def _clamp(self, e: Clamp) -> str:
        result = self._numeric_unary(e.arg, "clamp")
        for bound, name in ((e.min, "min"), (e.max, "max")):
            if bound is None:
                continue
            kind = self.infer(bound)
            if kind is not UNTYPED and not _is_numeric(kind):
                self._fail("RW2007", f"clamp {name} must be numeric, got {kind}")
        return result

    def _piecewise(self, e: Piecewise) -> str:
        for case in e.cases:
            guard = self.infer(case.when)
            if guard not in ("boolean", UNTYPED):
                self._fail("RW2005",
                           f"a piecewise case condition must be boolean, got {guard}")

        branches = [self.infer(case.then) for case in e.cases]
        branches.append(self.infer(e.otherwise))
        known = [b for b in branches if b is not UNTYPED]
        if not known:
            return UNTYPED

        if all(_is_numeric(b) for b in known):
            widest = known[0]
            for kind in known[1:]:
                widest = _widest(widest, kind)
            return widest
        if len(set(known)) > 1:
            return self._fail(
                "RW2008",
                "piecewise branches disagree: " + ", ".join(sorted(set(known))),
                branches=sorted(set(known)))
        return known[0]

    def _aggregate(self, e: Aggregate) -> str:
        self.infer(e.scope)
        if e.where is not None:
            guard = self.infer(e.where)
            if guard not in ("boolean", UNTYPED):
                self._fail("RW2005", f"an aggregation filter must be boolean, got {guard}")

        value = self.infer(e.value)
        if e.op == "count_over":
            return "integer"
        if e.op in ("any_over", "all_over"):
            if value not in ("boolean", UNTYPED):
                self._fail("RW2005", f"'{e.op}' aggregates booleans, got {value}")
            return "boolean"
        if value is UNTYPED:
            return UNTYPED
        if not _is_numeric(value):
            return self._fail("RW2007", f"'{e.op}' aggregates numbers, got {value}")
        return value


def check_types(package: RulePackage, report: Report) -> None:
    """Run the type checker over every rule in `package`."""
    checker = TypeChecker(package, report)
    for rule in package.rules:
        checker.check_rule(rule)
