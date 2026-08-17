"""Rules, exceptions, parameters and the rule package.

Nothing here imports a model provider or a target runtime, per docs/13_REPO_STRUCTURE.md.
The IR is the public contract; adapters lower from it and never redefine it.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .expressions import Expr


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SourceSpan(Base):
    """Provenance. Every material semantic object carries at least one."""

    source_id: str
    citation: str | None = None
    quote: str | None = None
    term: str | None = None
    node_id: str | None = None
    start_char: int | None = None
    end_char: int | None = None


class Entity(Base):
    id: str
    label: str
    kind: Literal["group", "member"] = "group"
    member_of: str | None = None


class Variable(Base):
    id: str
    entity: str
    value_type: Literal["boolean", "integer", "decimal", "money", "date", "enumeration", "string"]
    periodicity: Literal["day", "month", "year"] | None = None
    input: bool = False
    note: str | None = None
    sources: list[SourceSpan] = Field(default_factory=list)


class ParameterValue(Base):
    effective_from: str
    effective_to: str | None = None
    value: Decimal | str | bool
    # Dimension coordinates this value applies at, e.g. {"household_size": "3"}.
    at: dict[str, str] = Field(default_factory=dict)


class Parameter(Base):
    id: str
    value_type: Literal["boolean", "integer", "decimal", "money", "date", "string"]
    periodicity: Literal["day", "month", "year"] | None = None
    dimensions: list[str] = Field(default_factory=list)
    values: list[ParameterValue] = Field(default_factory=list)
    sources: list[SourceSpan] = Field(default_factory=list)
    note: str | None = None


class Assign(Base):
    target: str
    value: Expr


class Then(Base):
    assign: Assign


class Exception_(Base):
    """A rule-local exception.

    `disable_base_rule` suppresses the base rule. `substitute` replaces its effect —
    the dominant legal form, as in "except that for a household with an elderly member
    the limit is X". Encoding substitution as disable-plus-shadow-rule would duplicate
    the condition and sever source correspondence.
    """

    id: str
    when: Expr
    effect: Literal["disable_base_rule", "substitute"]
    substitute: Then | None = None
    priority: int
    sources: list[SourceSpan] = Field(default_factory=list)

    @model_validator(mode="after")
    def _substitute_required(self) -> "Exception_":
        if self.effect == "substitute" and self.substitute is None:
            raise ValueError(f"exception {self.id}: effect 'substitute' requires a 'substitute' block")
        if self.effect == "disable_base_rule" and self.substitute is not None:
            raise ValueError(f"exception {self.id}: 'substitute' block is meaningless with effect 'disable_base_rule'")
        return self


class Interpretation(Base):
    status: Literal["proposed", "needs_review", "approved", "rejected", "ambiguous", "human_judgment_required"] = "needs_review"
    note: str | None = None
    # Recorded for audit only. Never authorises approval — see ADR-004.
    model_confidence: float | None = None


class Rule(Base):
    id: str
    kind: Literal["eligibility", "calculation", "classification", "parameter_selection", "requirement"]
    effective_from: str
    effective_to: str | None = None
    when: Expr
    then: Then
    exceptions: list[Exception_] = Field(default_factory=list)
    # Cross-rule precedence for "notwithstanding" clauses. Rule-local exception
    # priority cannot express precedence between two rules assigning one target.
    overrides: list[str] = Field(default_factory=list)
    sources: list[SourceSpan] = Field(default_factory=list)
    interpretation: Interpretation = Field(default_factory=Interpretation)

    @model_validator(mode="after")
    def _unique_exception_priority(self) -> "Rule":
        seen: dict[int, str] = {}
        for exc in self.exceptions:
            if exc.priority in seen:
                raise ValueError(
                    f"rule {self.id}: exceptions {seen[exc.priority]} and {exc.id} share "
                    f"priority {exc.priority}; precedence must be deterministic"
                )
            seen[exc.priority] = exc.id
        return self


class Interpretations(Base):
    id: str
    description: str


class Ambiguity(Base):
    id: str
    type: str
    blocking: bool
    affects: list[str] = Field(default_factory=list)
    question: str
    interpretations: list[Interpretations] = Field(default_factory=list)
    resolution: dict | None = None
    sources: list[SourceSpan] = Field(default_factory=list)


class RulePackage(Base):
    schema_version: str
    package_id: str
    jurisdiction: str
    description: str | None = None
    entities: list[Entity] = Field(default_factory=list)
    variables: list[Variable] = Field(default_factory=list)
    parameters: list[Parameter] = Field(default_factory=list)
    rules: list[Rule] = Field(default_factory=list)
    ambiguities: list[Ambiguity] = Field(default_factory=list)

    def variable(self, vid: str) -> Variable | None:
        return next((v for v in self.variables if v.id == vid), None)

    def parameter(self, pid: str) -> Parameter | None:
        return next((p for p in self.parameters if p.id == pid), None)

    def rule(self, rid: str) -> Rule | None:
        return next((r for r in self.rules if r.id == rid), None)
