"""Amendment impact analysis.

Given what changed between two versions of a rule package, work out what it reaches:
which rules depend on it transitively, and — the part that actually matters — which
determinations move for real households.

The dependency closure answers "what could change". Running both packages over the same
scenarios answers "what does change", and that is the number a policy team can act on.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from ..ir.expressions import Param, Ref
from ..ir.rules import RulePackage
from ..runtime.evaluator import Context, Evaluator, ParameterTable
from ..runtime.values import Value
from .semantic import DiffReport


@dataclass
class OutcomeChange:
    scenario: str
    variable: str
    before: Value
    after: Value

    def __str__(self) -> str:
        return f"{self.scenario}: {self.variable.split('.')[-1]}  {self.before} -> {self.after}"


@dataclass
class ImpactReport:
    directly_affected: set[str] = field(default_factory=set)
    transitively_affected: set[str] = field(default_factory=set)
    outcome_changes: list[OutcomeChange] = field(default_factory=list)
    scenarios_run: int = 0

    @property
    def scenarios_changed(self) -> int:
        return len({c.scenario for c in self.outcome_changes})

    def __str__(self) -> str:
        lines = [
            "LEGISLATIVE CHANGE IMPACT",
            f"  directly affected rules     {len(self.directly_affected)}",
            f"  transitively affected rules {len(self.transitively_affected)}",
            f"  scenarios run               {self.scenarios_run}",
            f"  scenarios with a changed outcome {self.scenarios_changed}",
        ]
        if self.outcome_changes:
            lines.append("  outcome changes:")
            lines += [f"    {c}" for c in self.outcome_changes]
        return "\n".join(lines)


def _walk(expr):
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
                elif hasattr(item, "when"):
                    yield from _walk(item.when)
                    yield from _walk(item.then)
    args = getattr(expr, "args", None)
    if isinstance(args, dict):
        for child in args.values():
            yield from _walk(child)


def _rule_inputs(rule) -> tuple[set[str], set[str]]:
    """The variables and parameters a rule reads."""
    variables: set[str] = set()
    parameters: set[str] = set()
    roots = [rule.when, rule.then.assign.value]
    for exc in rule.exceptions:
        roots.append(exc.when)
        if exc.substitute:
            roots.append(exc.substitute.assign.value)
    for root in roots:
        for node in _walk(root):
            if isinstance(node, Ref) and node.id != "var.household":
                variables.add(node.id)
            elif isinstance(node, Param):
                parameters.add(node.id)
    return variables, parameters


def dependency_closure(package: RulePackage, changed_rules: set[str],
                       changed_parameters: set[str]) -> tuple[set[str], set[str]]:
    """Rules that read something a changed rule writes, transitively."""
    reads: dict[str, tuple[set[str], set[str]]] = {}
    writes: dict[str, str] = {}
    for rule in package.rules:
        reads[rule.id] = _rule_inputs(rule)
        writes[rule.id] = rule.then.assign.target

    direct = set(changed_rules)
    for rid, (_, params) in reads.items():
        if params & changed_parameters:
            direct.add(rid)

    transitive: set[str] = set()
    frontier = set(direct)
    while frontier:
        tainted = {writes[r] for r in frontier if r in writes}
        nxt = {
            rid for rid, (vars_read, _) in reads.items()
            if vars_read & tainted and rid not in direct and rid not in transitive
        }
        if not nxt:
            break
        transitive |= nxt
        frontier = nxt

    return direct, transitive


def analyse(
    before: RulePackage,
    after: RulePackage,
    diff: DiffReport,
    scenarios: dict[str, tuple[Context, dict]],
    observe: list[str],
) -> ImpactReport:
    """Full impact: the dependency closure, plus what actually moves.

    `scenarios` maps a name to a (context, parameter-overrides) pair. Each is run against
    both packages on a deep copy, so a scenario cannot leak state between versions.
    """
    direct, transitive = dependency_closure(after, diff.changed_rules, diff.changed_parameters)
    report = ImpactReport(directly_affected=direct, transitively_affected=transitive)

    for name, (ctx, overrides) in scenarios.items():
        report.scenarios_run += 1
        results = {}
        for label, package in (("before", before), ("after", after)):
            run_ctx = copy.deepcopy(ctx)
            evaluator = Evaluator(package, ParameterTable(package, overrides=overrides))
            try:
                evaluator.run(run_ctx)
                results[label] = {k: run_ctx.household.get(k) for k in observe}
            except Exception as exc:
                results[label] = {k: f"error: {type(exc).__name__}" for k in observe}

        for variable in observe:
            old_value, new_value = results["before"][variable], results["after"][variable]
            if old_value != new_value:
                report.outcome_changes.append(
                    OutcomeChange(name, variable, old_value, new_value))

    return report
