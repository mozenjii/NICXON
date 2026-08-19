"""Deterministic validation of a rule package.

Every check here is mechanical. None of them consults a model, and none of them can be
skipped for convenience — a package that does not validate must not be evaluated, because
an unresolved reference or a lost override changes who receives a benefit.
"""

from __future__ import annotations

from ..ir.expressions import Aggregate, Param, Piecewise, Ref
from ..ir.rules import Rule, RulePackage
from .diagnostics import Diagnostic, Report


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
                elif hasattr(item, "when"):
                    yield from _walk(item.when)
                    yield from _walk(item.then)
    args = getattr(expr, "args", None)
    if isinstance(args, dict):
        for child in args.values():
            yield from _walk(child)


def _rule_exprs(rule: Rule):
    yield rule.when
    yield rule.then.assign.value
    for exc in rule.exceptions:
        yield exc.when
        if exc.substitute is not None:
            yield exc.substitute.assign.value


def _refs(rule: Rule) -> set[str]:
    out: set[str] = set()
    for root in _rule_exprs(rule):
        for node in _walk(root):
            if isinstance(node, Ref) and node.id != "var.household":
                out.add(node.id)
    return out


def validate(package: RulePackage, *, corpus=None) -> Report:
    """Check a package. With a `corpus`, also check that its provenance resolves.

    The corpus is optional because validation must work without the source snapshots
    on disk — a deployment that executes an approved package should not need the
    originals. When they are available, `RW1xxx` reports spans that no longer point at
    what they claim to, which is the check that catches an amended clause.
    """
    report = Report()
    var_ids = {v.id for v in package.variables}
    param_ids = {p.id for p in package.parameters}
    rule_ids = {r.id for r in package.rules}
    entity_ids = {e.id for e in package.entities}

    _duplicates(package, report)
    _references(package, report, var_ids, param_ids, entity_ids)
    _targets(package, report, var_ids)
    _overrides(package, report, rule_ids)
    _cycles(package, report)
    _temporal(package, report)
    _provenance(package, report)
    if corpus is not None:
        _spans_resolve(package, report, corpus)
    _ambiguities(package, report, rule_ids)
    _piecewise(package, report)
    return report


def _duplicates(pkg: RulePackage, report: Report) -> None:
    for label, ids in (
        ("variable", [v.id for v in pkg.variables]),
        ("parameter", [p.id for p in pkg.parameters]),
        ("rule", [r.id for r in pkg.rules]),
        ("entity", [e.id for e in pkg.entities]),
    ):
        seen: set[str] = set()
        for i in ids:
            if i in seen:
                report.add(Diagnostic(
                    "RW2001", "blocking", f"duplicate {label} id: {i}", object_id=i,
                    suggestion="ids must be unique; the later definition would silently win"))
            seen.add(i)


def _references(pkg: RulePackage, report: Report, var_ids, param_ids, entity_ids) -> None:
    for rule in pkg.rules:
        for ref in _refs(rule):
            if ref not in var_ids:
                report.add(Diagnostic(
                    "RW3001", "blocking", f"reference to undeclared variable: {ref}",
                    rule_id=rule.id, object_id=ref,
                    suggestion="declare it in variables, or correct the id"))
        for root in _rule_exprs(rule):
            for node in _walk(root):
                if isinstance(node, Param) and node.id not in param_ids:
                    report.add(Diagnostic(
                        "RW3002", "blocking", f"reference to undeclared parameter: {node.id}",
                        rule_id=rule.id, object_id=node.id))
                if isinstance(node, Aggregate) and node.entity not in entity_ids:
                    report.add(Diagnostic(
                        "RW3007", "blocking",
                        f"aggregation over undeclared entity: {node.entity}",
                        rule_id=rule.id, object_id=node.entity))


def _targets(pkg: RulePackage, report: Report, var_ids) -> None:
    for rule in pkg.rules:
        targets = [rule.then.assign.target] + [
            e.substitute.assign.target for e in rule.exceptions if e.substitute
        ]
        for t in targets:
            if t not in var_ids:
                report.add(Diagnostic(
                    "RW3003", "blocking", f"assignment to undeclared variable: {t}",
                    rule_id=rule.id, object_id=t))
        base = rule.then.assign.target
        for exc in rule.exceptions:
            if exc.substitute and exc.substitute.assign.target != base:
                report.add(Diagnostic(
                    "RW3004", "error",
                    f"exception {exc.id} assigns {exc.substitute.assign.target} but the "
                    f"base rule assigns {base}",
                    rule_id=rule.id, object_id=exc.id,
                    suggestion="a substitutive exception must replace the base effect, "
                               "not write elsewhere"))


def _overrides(pkg: RulePackage, report: Report, rule_ids) -> None:
    by_id = {r.id: r for r in pkg.rules}
    for rule in pkg.rules:
        for target_id in rule.overrides:
            if target_id not in rule_ids:
                report.add(Diagnostic(
                    "RW3005", "blocking", f"overrides unknown rule: {target_id}",
                    rule_id=rule.id, object_id=target_id))
                continue
            other = by_id[target_id]
            if other.then.assign.target != rule.then.assign.target:
                report.add(Diagnostic(
                    "RW3006", "error",
                    f"overrides {target_id}, which assigns "
                    f"{other.then.assign.target} rather than {rule.then.assign.target}",
                    rule_id=rule.id, object_id=target_id,
                    suggestion="precedence is only meaningful between rules assigning "
                               "the same target"))

    # Override cycles would make evaluation order undefined.
    graph = {r.id: set(r.overrides) for r in pkg.rules}
    for cycle in _find_cycles(graph):
        report.add(Diagnostic(
            "RW3008", "blocking", f"override cycle: {' -> '.join(cycle)}",
            rule_id=cycle[0], details={"cycle": cycle}))

    # A rule that is unconditionally overridden can never fire. The mutation harness
    # treats these as equivalent-mutant sources; here they are reported as dead code.
    overridden = {rid for r in pkg.rules for rid in r.overrides}
    for rid in overridden:
        overriders = [r for r in pkg.rules if rid in r.overrides]
        if any(getattr(r.when, "op", None) == "literal" and r.when.value is True for r in overriders):
            report.add(Diagnostic(
                "RW3009", "warning", "rule is unconditionally overridden and can never fire",
                rule_id=rid,
                details={"overridden_by": [r.id for r in overriders]},
                suggestion="either guard the overriding rule so this one can fire, or "
                           "fold this rule's logic into it and delete this rule"))


def _find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    WHITE, GREY, BLACK = 0, 1, 2
    colour = dict.fromkeys(graph, WHITE)

    def visit(node: str, path: list[str]) -> None:
        colour[node] = GREY
        for nxt in graph.get(node, ()):
            if nxt not in colour:
                continue
            if colour[nxt] == GREY:
                cycles.append([*path[path.index(nxt):], nxt])
            elif colour[nxt] == WHITE:
                visit(nxt, [*path, nxt])
        colour[node] = BLACK

    for node in list(graph):
        if colour[node] == WHITE:
            visit(node, [node])
    return cycles


def _cycles(pkg: RulePackage, report: Report) -> None:
    """A variable dependency cycle would prevent the evaluator reaching a fixed point."""
    produced: dict[str, str] = {}
    for rule in pkg.rules:
        produced.setdefault(rule.then.assign.target, rule.id)

    graph: dict[str, set[str]] = {}
    for rule in pkg.rules:
        target = rule.then.assign.target
        graph.setdefault(target, set())
        for ref in _refs(rule):
            if ref in produced and ref != target:
                graph[target].add(ref)

    for cycle in _find_cycles(graph):
        report.add(Diagnostic(
            "RW3010", "blocking", f"variable dependency cycle: {' -> '.join(cycle)}",
            rule_id=produced.get(cycle[0]), details={"cycle": cycle},
            suggestion="the evaluator cannot reach a fixed point through a cycle"))


def _temporal(pkg: RulePackage, report: Report) -> None:
    for rule in pkg.rules:
        if rule.effective_to is not None and rule.effective_to <= rule.effective_from:
            report.add(Diagnostic(
                "RW4001", "blocking",
                f"effective_to {rule.effective_to} is not after effective_from "
                f"{rule.effective_from}; the rule can never apply",
                rule_id=rule.id))
    for param in pkg.parameters:
        for pv in param.values:
            if pv.effective_to is not None and pv.effective_to <= pv.effective_from:
                report.add(Diagnostic(
                    "RW4002", "blocking",
                    f"parameter value interval is empty: {pv.effective_from} to {pv.effective_to}",
                    object_id=param.id))
        # Overlapping intervals at the same coordinates make lookup order-dependent.
        for i, a in enumerate(param.values):
            for b in param.values[i + 1:]:
                if a.at != b.at:
                    continue
                a_end = a.effective_to or "9999-12-31"
                b_end = b.effective_to or "9999-12-31"
                if a.effective_from < b_end and b.effective_from < a_end:
                    report.add(Diagnostic(
                        "RW4003", "error",
                        f"overlapping value intervals for {param.id} at {a.at or 'no dimensions'}",
                        object_id=param.id,
                        suggestion="lookup would depend on declaration order"))


def _provenance(pkg: RulePackage, report: Report) -> None:
    """README principle 2: every material semantic object links to a source span."""
    for rule in pkg.rules:
        if not rule.sources:
            report.add(Diagnostic(
                "RW7001", "error", "rule has no source span",
                rule_id=rule.id,
                suggestion="cite the clause, or mark the rule as derived"))
        for exc in rule.exceptions:
            if not exc.sources:
                report.add(Diagnostic(
                    "RW7002", "warning", f"exception {exc.id} has no source span",
                    rule_id=rule.id, object_id=exc.id))
    for param in pkg.parameters:
        if not param.sources:
            report.add(Diagnostic(
                "RW7003", "warning", f"parameter {param.id} has no source span",
                object_id=param.id))


def _spans_resolve(pkg: RulePackage, report: Report, corpus) -> None:
    """Every source span must still point at the text it claims to quote.

    This is the check that turns provenance from a stored string into a verified fact. It
    found that 14 of the 15 rules in the golden fixture quoted text which did not appear in
    the clause they cited, so it is not hypothetical.
    """
    from ..ingest.document import resolve_span

    documents = getattr(corpus, "documents", corpus)

    def check(spans, rule_id, object_id=None) -> None:
        for span in spans:
            result = resolve_span(span, documents)
            if result:
                continue
            report.add(Diagnostic(
                "RW1001", "error",
                f"source span does not resolve: {result.reason}",
                rule_id=rule_id, object_id=object_id,
                suggestion="quote contiguous text from the cited clause, or correct the "
                           "citation",
                details={"source_id": span.source_id, "citation": span.citation}))

    for rule in pkg.rules:
        check(rule.sources, rule.id)
        for exc in rule.exceptions:
            check(exc.sources, rule.id, exc.id)
    for param in pkg.parameters:
        check(param.sources, None, param.id)
    for variable in pkg.variables:
        check(variable.sources, None, variable.id)
    for ambiguity in pkg.ambiguities:
        check(ambiguity.sources, None, ambiguity.id)


def _ambiguities(pkg: RulePackage, report: Report, rule_ids) -> None:
    for amb in pkg.ambiguities:
        for rid in amb.affects:
            if rid not in rule_ids:
                report.add(Diagnostic(
                    "RW5001", "error", f"ambiguity {amb.id} affects unknown rule {rid}",
                    object_id=amb.id))
        if amb.blocking and not amb.resolution:
            report.add(Diagnostic(
                "RW5002", "blocking",
                f"blocking ambiguity {amb.id} is unresolved",
                object_id=amb.id,
                details={"affects": amb.affects},
                suggestion="a blocking ambiguity prevents affected rules becoming executable"))
        if not amb.affects:
            report.add(Diagnostic(
                "RW5003", "warning",
                f"ambiguity {amb.id} names no affected rules, so nothing can act on it",
                object_id=amb.id))


def _piecewise(pkg: RulePackage, report: Report) -> None:
    for rule in pkg.rules:
        for root in _rule_exprs(rule):
            for node in _walk(root):
                if isinstance(node, Piecewise) and not node.cases:
                    report.add(Diagnostic(
                        "RW2002", "warning",
                        "piecewise has no cases and always yields its otherwise branch",
                        rule_id=rule.id))
