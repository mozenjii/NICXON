"""Mutation testing for rule packages.

docs/07_DATA_BENCHMARK_EVAL.md is right that generated tests "should be evaluated by
fault detection, not beauty". A suite that passes tells you nothing on its own; a suite
that fails when the rules are deliberately broken tells you it is load-bearing.

This plants semantic faults of the kind a mis-extraction would actually produce — a
comparison flipped at a threshold, a conjunction turned into a disjunction, an exception
silently dropped, a "notwithstanding" override lost — and reports what fraction the
suite catches. That number is the evidence ADR-021 asks for.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Callable, Iterator

from ..ir.rules import RulePackage

_COMPARISON_FLIP = {"lte": "lt", "lt": "lte", "gte": "gt", "gt": "gte", "eq": "neq", "neq": "eq"}
_BOOLEAN_SWAP = {"all": "any", "any": "all"}
_ROUNDING_FLIP = {"up": "down", "down": "up", "half_up": "half_even", "half_even": "half_up"}


@dataclass
class Mutant:
    id: str
    operator: str
    location: str
    description: str
    package: RulePackage


@dataclass
class MutationReport:
    total: int
    caught: int
    survivors: list[Mutant]

    @property
    def catch_rate(self) -> float:
        return self.caught / self.total if self.total else 0.0

    def __str__(self) -> str:
        pct = self.catch_rate * 100
        lines = [f"mutation score: {self.caught}/{self.total} caught ({pct:.0f}%)"]
        for m in self.survivors:
            lines.append(f"  SURVIVED  {m.operator:18} {m.location}  — {m.description}")
        return "\n".join(lines)


def _walk_exprs(node: dict, path: str) -> Iterator[tuple[dict, str]]:
    """Yield every expression dict in a tree with a readable path."""
    if not isinstance(node, dict):
        return
    if "op" in node:
        yield node, path
    for key, child in node.items():
        if isinstance(child, dict):
            yield from _walk_exprs(child, f"{path}.{key}")
        elif isinstance(child, list):
            for i, item in enumerate(child):
                if isinstance(item, dict):
                    yield from _walk_exprs(item, f"{path}.{key}[{i}]")


def _rule_expr_roots(rule: dict, rid: str) -> Iterator[tuple[dict, str]]:
    yield rule["when"], f"{rid}.when"
    yield rule["then"]["assign"]["value"], f"{rid}.then"
    for i, exc in enumerate(rule.get("exceptions", [])):
        yield exc["when"], f"{rid}.exceptions[{i}].when"
        if exc.get("substitute"):
            yield exc["substitute"]["assign"]["value"], f"{rid}.exceptions[{i}].substitute"


def generate_mutants(package: RulePackage) -> list[Mutant]:
    base = package.model_dump(mode="json", by_alias=True)
    mutants: list[Mutant] = []

    # A rule that is unconditionally overridden never fires, so mutating it produces
    # equivalent mutants — unkillable by construction, and they depress the score
    # without indicating a real gap. Skipping them matches the evaluator's own logic.
    # That such rules exist at all is a modelling smell a validator should report.
    overridden = {rid for r in base["rules"] for rid in r.get("overrides", [])}

    def emit(operator: str, location: str, description: str, mutated: dict) -> None:
        try:
            pkg = RulePackage.model_validate(mutated)
        except Exception:
            return  # a mutant the schema already rejects is not an interesting fault
        mutants.append(Mutant(
            id=f"mut.{operator}.{len(mutants)}", operator=operator,
            location=location, description=description, package=pkg))

    for r_idx, rule in enumerate(base["rules"]):
        rid = rule["id"]
        if rid in overridden:
            continue

        # Structural faults: a dropped exception or a lost override.
        for e_idx, exc in enumerate(rule.get("exceptions", [])):
            m = copy.deepcopy(base)
            del m["rules"][r_idx]["exceptions"][e_idx]
            emit("drop_exception", f"{rid}.exceptions[{e_idx}]",
                 f"exception {exc['id']} removed", m)

        if rule.get("overrides"):
            m = copy.deepcopy(base)
            m["rules"][r_idx]["overrides"] = []
            emit("drop_override", f"{rid}.overrides",
                 f"override of {rule['overrides']} removed", m)

        # Expression faults: the shape a mis-extraction actually takes.
        for root, root_path in _rule_expr_roots(rule, rid):
            for node, path in _walk_exprs(root, root_path):
                op = node.get("op")

                if op in _COMPARISON_FLIP:
                    m = _mutate_at(base, r_idx, rid, path, "op", _COMPARISON_FLIP[op])
                    if m:
                        emit("comparison_flip", path, f"{op} -> {_COMPARISON_FLIP[op]}", m)

                elif op in _BOOLEAN_SWAP:
                    m = _mutate_at(base, r_idx, rid, path, "op", _BOOLEAN_SWAP[op])
                    if m:
                        emit("boolean_swap", path, f"{op} -> {_BOOLEAN_SWAP[op]}", m)

                elif op == "round":
                    new = _ROUNDING_FLIP.get(node.get("mode"))
                    if new:
                        m = _mutate_at(base, r_idx, rid, path, "mode", new)
                        if m:
                            emit("rounding_flip", path, f"round {node['mode']} -> {new}", m)

                elif op == "not":
                    m = _mutate_at(base, r_idx, rid, path, "__unwrap_not__", None)
                    if m:
                        emit("drop_negation", path, "not(...) removed", m)

                elif op == "literal" and isinstance(node.get("value"), (int, float, str)):
                    try:
                        from decimal import Decimal
                        val = Decimal(str(node["value"]))
                    except Exception:
                        continue
                    m = _mutate_at(base, r_idx, rid, path, "value", str(val + 1))
                    if m:
                        emit("literal_perturb", path, f"{node['value']} -> {val + 1}", m)

    return mutants


def _mutate_at(base: dict, r_idx: int, rid: str, target_path: str,
               field: str, value) -> dict | None:
    """Deep-copy the package and apply one change at `target_path`."""
    m = copy.deepcopy(base)
    for root, root_path in _rule_expr_roots(m["rules"][r_idx], rid):
        for node, path in _walk_exprs(root, root_path):
            if path != target_path:
                continue
            if field == "__unwrap_not__":
                inner = node.get("arg")
                if not isinstance(inner, dict):
                    return None
                node.clear()
                node.update(inner)
            else:
                node[field] = value
            return m
    return None


def run(mutants: list[Mutant], check: Callable[[RulePackage], bool]) -> MutationReport:
    """`check` returns True when the suite passes. A mutant is caught when it returns False."""
    survivors = []
    for mutant in mutants:
        try:
            passed = check(mutant.package)
        except Exception:
            passed = False  # a crash is a detection
        if passed:
            survivors.append(mutant)
    return MutationReport(total=len(mutants), caught=len(mutants) - len(survivors), survivors=survivors)
