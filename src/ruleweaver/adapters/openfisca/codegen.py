"""Generating an OpenFisca country package from an approved rule package.

What comes out is a directory an OpenFisca installation can load: an entity model, a
module of `Variable` subclasses, a parameter tree as YAML, and YAML test files built from
the same scenarios the deterministic evaluator runs. The tests matter most — they are the
only thing that makes the claim "this export behaves like the IR" checkable rather than
asserted.

Two refusals are built in.

**Unapproved rules are not exported.** Export is a deployment step, and a rule nobody
signed off reaching a production calculator through an adapter would route straight around
the gate the whole project exists to enforce.

**The four-state gap is reported, every time.** OpenFisca has no unknown; a missing fact
takes the type default. `RW8001` says so on every export and the generated module repeats
it at the top of the file, because a maintainer reading the code months later is the person
who needs to know.

Order of assignment is preserved from the IR rather than recomputed. OpenFisca resolves
dependencies itself by calling variables lazily, so the generated module does not need a
topological sort — but keeping source order makes the generated file diffable against the
package it came from.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from ...approval import check
from ...ir.rules import Rule, RulePackage
from ...review.decisions import ReviewLog
from ...verify.diagnostics import Diagnostic
from .lowering import Lowered, Lowerer, Unlowerable

_VALUE_TYPES = {
    "boolean": "bool",
    "integer": "int",
    "decimal": "float",
    "money": "float",
    "date": "date",
    "string": "str",
    "enumeration": "str",
}

_PERIODS = {"day": "DAY", "month": "MONTH", "year": "YEAR"}

_UNKNOWN_WARNING = (
    "OpenFisca has no unknown state. A fact nobody supplied takes this variable's type "
    "default — 0 for a number, False for a boolean — so a missing input is "
    "indistinguishable from a genuine zero. The RuleWeaver evaluator keeps those apart "
    "and propagates unknown instead. Determinations that depend on absent facts will "
    "differ between the two, and the difference is a denial rather than a question."
)


def _identifier(name: str) -> str:
    """A Python-safe name from a rule or variable id."""
    cleaned = re.sub(r"[^0-9a-zA-Z_]", "_", name.rsplit(".", 1)[-1])
    return cleaned if not cleaned[:1].isdigit() else f"v_{cleaned}"


@dataclass
class Export:
    """Everything an export produced, including what it refused to produce."""

    files: dict[str, str] = field(default_factory=dict)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    exported: list[str] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not [d for d in self.diagnostics if d.severity in ("error", "blocking")]

    def write(self, out_dir: str | Path) -> Path:
        root = Path(out_dir)
        for name, content in self.files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return root

    def __str__(self) -> str:
        lines = [f"{len(self.exported)} variable(s) exported, {len(self.skipped)} skipped"]
        for rule_id, reason in sorted(self.skipped.items()):
            lines.append(f"  {rule_id}: {reason}")
        for diagnostic in self.diagnostics:
            lines.append(f"  {diagnostic}")
        return "\n".join(lines)


def _lower_rule(rule: Rule) -> Lowered:
    """Lower a rule and its exceptions into one formula.

    Prioritised defaults have a faithful vectorised form. The IR already requires every
    exception on a rule to carry a distinct priority, so the order is total and the
    selection is decidable: highest priority whose condition holds wins, and the base
    expression is the default. That is `np.select` with the cases sorted descending.

    `disable_base_rule` has no such form. It says the rule produces *nothing*, and
    OpenFisca has no way to express "no value" — the variable would silently take its type
    default, turning a suppressed rule into a zero. Those rules are refused rather than
    approximated.
    """
    lowerer = Lowerer()
    base = lowerer.lower(rule.then.assign.value)
    if not rule.exceptions:
        return base

    for exception in rule.exceptions:
        if exception.effect != "substitute" or exception.substitute is None:
            raise Unlowerable(
                f"exception {exception.id} suppresses the base rule; OpenFisca cannot "
                "represent a variable with no value, so it would become a zero")

    ordered = sorted(rule.exceptions, key=lambda e: e.priority, reverse=True)
    conditions = []
    values = []
    for exception in ordered:
        conditions.append(lowerer.expression(exception.when))
        assert exception.substitute is not None
        values.append(lowerer.expression(exception.substitute.assign.value))

    lowerer.result.uses_numpy = True
    lowerer.result.source = (
        f"np.select([{', '.join(conditions)}], [{', '.join(values)}], "
        f"default={base.source})")
    return lowerer.result


def _variable_class(package: RulePackage, rule: Rule, lowered: Lowered) -> str:
    """One `Variable` subclass for the target of one rule."""
    target = rule.then.assign.target
    declared = package.variable(target)
    entity = "Household"
    if declared is not None and declared.entity != "household":
        entity = "Person"

    value_type = _VALUE_TYPES.get(declared.value_type if declared else "decimal", "float")
    period = _PERIODS.get((declared.periodicity if declared else None) or "month", "MONTH")

    citation = ""
    if rule.sources:
        span = rule.sources[0]
        citation = span.citation or span.source_id
        if span.quote:
            citation += f"\n        {span.quote}"

    args = "person, period, parameters" if entity == "Person" else "household, period, parameters"
    body = lowered.source
    if entity == "Household" and lowered.person_vars:
        # Household formulas reach members through the entity, not through a bare name.
        body = body.replace("person(", "household.members(")
        args = "household, period, parameters"

    return (
        f"class {_identifier(target)}(Variable):\n"
        f'    """{rule.id}\n\n'
        f"    {citation}\n"
        f'    """\n'
        f"    value_type = {value_type}\n"
        f"    entity = {entity}\n"
        f"    definition_period = {period}\n"
        f"    label = {rule.id!r}\n\n"
        f"    def formula({args}):\n"
        f"        return {body}\n"
    )


def _module(package: RulePackage, classes: list[str], uses_numpy: bool) -> str:
    header = (
        f'"""Generated from {package.package_id} by RuleWeaver. Do not edit by hand.\n\n'
        f"Every variable here corresponds to one approved rule. Edit the rule package and\n"
        f"re-export; an edit made here is invisible to review, to the audit log, and to\n"
        f"the amendment-impact analysis.\n\n"
        f"WARNING — {_UNKNOWN_WARNING}\n"
        f'"""\n\n'
    )
    imports = "from openfisca_core.periods import DAY, MONTH, YEAR\n"
    imports += "from openfisca_core.variables import Variable\n"
    imports += "\nfrom .entities import Household, Person\n"
    if uses_numpy:
        imports = "import numpy as np\n\n" + imports

    helper = (
        "\n\ndef _key(value):\n"
        '    """Format a parameter index.\n\n'
        "    An index that has been through np.clip is a float, and str(6.0) is \"6.0\",\n"
        "    which matches no parameter node. Whole numbers are formatted as integers so\n"
        "    the lookup finds the key the parameter file actually declares.\n"
        '    """\n'
        "    try:\n"
        "        as_float = float(value)\n"
        "    except (TypeError, ValueError):\n"
        "        return str(value)\n"
        "    return str(int(as_float)) if as_float == int(as_float) else str(as_float)\n\n\n"
    )
    return header + imports + helper + "\n\n".join(classes)


def _entities() -> str:
    return (
        '"""Generated entity model."""\n\n'
        "from openfisca_core.entities import build_entity\n\n"
        "Household = build_entity(\n"
        '    key="household",\n'
        '    plural="households",\n'
        '    label="A benefit unit assessed together",\n'
        "    roles=[\n"
        '        {"key": "member", "plural": "members", "label": "Member"},\n'
        "    ],\n"
        ")\n\n"
        "Person = build_entity(\n"
        '    key="person",\n'
        '    plural="persons",\n'
        '    label="An individual",\n'
        "    is_person=True,\n"
        ")\n\n"
        "entities = [Household, Person]\n"
    )


def _parameters_yaml(package: RulePackage,
                     diagnostics: list[Diagnostic] | None = None) -> dict[str, str]:
    """One YAML file per parameter, in the tree OpenFisca expects.

    Written by hand rather than through a YAML library so the adapter stays dependency
    free — the values are dates, decimals and strings, and the shape is fixed.
    """
    files: dict[str, str] = {}
    for parameter in package.parameters:
        if not parameter.values:
            # A parameter the package declares but never populates. In RuleWeaver it
            # resolves to unknown and the determination stops; in OpenFisca the lookup
            # raises at run time, so the generated package will not load a scenario that
            # touches it. Reported rather than emitted as an empty file, which would look
            # like a table that happens to be empty.
            if diagnostics is not None:
                diagnostics.append(Diagnostic(
                    "RW8005", "error",
                    f"parameter {parameter.id} has no values and cannot be exported",
                    object_id=parameter.id,
                    suggestion="supply the published table, or drop the parameter"))
            continue
        path = parameter.id.removeprefix("param.").replace(".", "/")
        lines = ["description: " + (parameter.note or parameter.id)]
        if parameter.sources and parameter.sources[0].citation:
            lines.append(f"reference: {parameter.sources[0].citation}")

        if parameter.dimensions:
            # A dimensioned parameter becomes nested nodes keyed by coordinate, which is
            # how OpenFisca addresses a scale that is not a bracket schedule.
            grouped: dict[tuple[str, ...], list] = {}
            for value in parameter.values:
                key = tuple(str(value.at[d]) for d in parameter.dimensions if d in value.at)
                grouped.setdefault(key, []).append(value)
            for key, values in sorted(grouped.items()):
                node = "/".join(key)
                body = ["values:"]
                for value in sorted(values, key=lambda v: v.effective_from):
                    rendered = value.value
                    if isinstance(rendered, Decimal):
                        rendered = f"{rendered:f}"
                    body.append(f"  {value.effective_from}:")
                    body.append(f"    value: {rendered}")
                files[f"parameters/{path}/{node}.yaml"] = "\n".join(lines + body) + "\n"
        else:
            body = ["values:"]
            for value in sorted(parameter.values, key=lambda v: v.effective_from):
                rendered = value.value
                if isinstance(rendered, Decimal):
                    rendered = f"{rendered:f}"
                body.append(f"  {value.effective_from}:")
                body.append(f"    value: {rendered}")
            files[f"parameters/{path}.yaml"] = "\n".join(lines + body) + "\n"
    return files


def export(
    package: RulePackage,
    *,
    log: ReviewLog | None = None,
    require_approval: bool = True,
) -> Export:
    """Generate an OpenFisca package from the approved rules in `package`.

    `require_approval` defaults to true and should stay that way outside tests. An export
    that skips the gate hands unreviewed rules to a production calculator through the one
    path nobody is watching.
    """
    result = Export()

    approved: set[str] | None = None
    if require_approval:
        report = check(package, log or ReviewLog())
        approved = set(report.approved)
        for rule_id, status in sorted(report.blocked.items()):
            result.skipped[rule_id] = f"not approved ({status.value})"
        if report.blocked:
            result.diagnostics.append(Diagnostic(
                "RW8002", "error",
                f"{len(report.blocked)} rule(s) are not approved and were not exported",
                suggestion="review them, or pass require_approval=False for a dry run "
                           "that must not be deployed"))

    result.diagnostics.append(Diagnostic(
        "RW8001", "warning",
        "OpenFisca has no unknown state; missing inputs take the type default",
        suggestion="treat a determination that depends on an absent fact as unreliable "
                   "in the exported model",
        details={"detail": _UNKNOWN_WARNING}))

    classes: list[str] = []
    uses_numpy = False
    for rule in package.rules:
        if approved is not None and rule.id not in approved:
            continue
        try:
            lowered = _lower_rule(rule)
        except Unlowerable as exc:
            result.skipped[rule.id] = str(exc)
            result.diagnostics.append(Diagnostic(
                "RW8003", "warning", f"rule could not be lowered: {exc}",
                rule_id=rule.id))
            continue

        uses_numpy = uses_numpy or lowered.uses_numpy
        classes.append(_variable_class(package, rule, lowered))
        result.exported.append(rule.id)

    if result.skipped and not result.exported:
        result.diagnostics.append(Diagnostic(
            "RW8004", "error", "nothing was exported",
            suggestion="an empty country package is not a successful export"))

    result.files["entities.py"] = _entities()
    result.files["variables.py"] = _module(package, classes, uses_numpy)
    result.files.update(_parameters_yaml(package, result.diagnostics))
    return result
