"""Expression AST for the RuleWeaver IR.

Expressions are data, never source code. A model proposes one of these shapes or it
proposes nothing; there is no path by which generated text reaches an interpreter.

Every node here is required by a clause in the SNAP fixture. See docs/15_VOCABULARY.md
for the clause behind each construct.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class ExprBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Lit(ExprBase):
    """A constant. Numbers arrive as Decimal, never binary float."""

    op: Literal["literal"]
    value: bool | Decimal | int | str | None


class Ref(ExprBase):
    """A reference to a variable by stable id."""

    op: Literal["ref"]
    id: str


class Param(ExprBase):
    """A dated parameter lookup, optionally dimensioned.

    `args` maps a dimension name to the expression selecting along it, which is what
    lets the standard deduction clamp its household_size index rather than its value.
    """

    op: Literal["parameter"]
    id: str
    args: dict[str, Expr] = Field(default_factory=dict)


class Compare(ExprBase):
    op: Literal["lt", "lte", "gt", "gte", "eq", "neq"]
    left: Expr
    right: Expr


class BoolOp(ExprBase):
    """Kleene conjunction/disjunction. Arity is n, not 2, so encoded law keeps the
    shape of the clause it came from."""

    op: Literal["all", "any"]
    args: list[Expr]


class Not(ExprBase):
    op: Literal["not"]
    arg: Expr


class Arith(ExprBase):
    """`subtract` and `divide` are left-folds over args, so `a - b - c` stays one node."""

    op: Literal["add", "subtract", "multiply", "divide", "min", "max"]
    args: list[Expr]


class Round(ExprBase):
    """Explicit rounding. There is no default mode and no default quantum, because
    7 CFR 273.9(a)(3) rounds up and (d)(1) rounds up to the dollar — an implicit
    rule would silently be wrong for one of them.
    """

    op: Literal["round"]
    arg: Expr
    mode: Literal["up", "down", "half_up", "half_even", "toward_zero"]
    to: str  # decimal quantum, e.g. "1" or "0.01"


class ConvertPeriod(ExprBase):
    """Period conversion is never implicit. Required by "divided by 12" at 273.9(a)(3)."""

    op: Literal["convert_period"]
    arg: Expr
    from_: Literal["day", "month", "year"] = Field(alias="from")
    to: Literal["day", "month", "year"]
    method: Literal["divide", "prorate_days"] = "divide"

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class Clamp(ExprBase):
    """Bound a value. At least one of min/max is required.

    Used on a parameter's lookup index for "for household sizes greater than six, the
    standard deduction shall be equal to the standard deduction for a six-person
    household" (273.9(d)(1)(i)).
    """

    op: Literal["clamp"]
    arg: Expr
    min: Expr | None = None
    max: Expr | None = None


class Case(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    when: Expr
    then: Expr


class Piecewise(ExprBase):
    """First matching case wins. `otherwise` is mandatory so a schedule can never fall
    through to a silent unknown."""

    op: Literal["piecewise"]
    cases: list[Case]
    otherwise: Expr


class Aggregate(ExprBase):
    """Aggregation over the members of a group entity.

    Required by household income (a sum over members) and by
    household_has_elderly_or_disabled_member (an existential over members).
    """

    op: Literal["sum_over", "count_over", "min_over", "max_over", "any_over", "all_over"]
    entity: str
    scope: Expr
    value: Expr
    where: Expr | None = None


Expr = Annotated[
    Lit | Ref | Param | Compare | BoolOp | Not | Arith | Round | ConvertPeriod | Clamp | Piecewise | Aggregate,
    Field(discriminator="op"),
]

for _m in (Lit, Ref, Param, Compare, BoolOp, Not, Arith,
           Round, ConvertPeriod, Clamp, Piecewise, Aggregate, Case):
    _m.model_rebuild()
