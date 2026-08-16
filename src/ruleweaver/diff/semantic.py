"""Semantic comparison of two rule packages.

Textual diff tells you a file changed. What a caseworker needs to know is whether the
*meaning* changed, and which determinations move as a result — a reworded citation is
noise, a threshold moving from 32,000 to 36,500 is not.

Every change is classified as semantic or cosmetic, and only semantic changes propagate
into impact analysis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..ir.rules import RulePackage

# Fields that carry meaning. Anything else on a rule is documentation.
_SEMANTIC_RULE_FIELDS = {"when", "then", "exceptions", "overrides", "effective_from",
                         "effective_to", "kind"}
_COSMETIC_RULE_FIELDS = {"sources", "interpretation"}


@dataclass
class Change:
    kind: str
    object_id: str
    semantic: bool
    description: str
    field_name: str | None = None
    before: Any = None
    after: Any = None

    def __str__(self) -> str:
        mark = "SEMANTIC" if self.semantic else "cosmetic"
        return f"[{mark}] {self.kind} {self.object_id}: {self.description}"


@dataclass
class DiffReport:
    changes: list[Change] = field(default_factory=list)

    @property
    def semantic(self) -> list[Change]:
        return [c for c in self.changes if c.semantic]

    @property
    def cosmetic(self) -> list[Change]:
        return [c for c in self.changes if not c.semantic]

    @property
    def changed_rules(self) -> set[str]:
        return {c.object_id for c in self.semantic if c.kind.startswith("rule")}

    @property
    def changed_parameters(self) -> set[str]:
        return {c.object_id for c in self.semantic if c.kind.startswith("parameter")}

    def __str__(self) -> str:
        if not self.changes:
            return "no changes"
        lines = [f"{len(self.semantic)} semantic, {len(self.cosmetic)} cosmetic"]
        lines += [f"  {c}" for c in self.semantic]
        lines += [f"  {c}" for c in self.cosmetic]
        return "\n".join(lines)


def _dump(package: RulePackage) -> dict:
    return package.model_dump(mode="json", by_alias=True)


def compare(before: RulePackage, after: RulePackage) -> DiffReport:
    report = DiffReport()
    old, new = _dump(before), _dump(after)

    _compare_rules(old, new, report)
    _compare_parameters(old, new, report)
    _compare_variables(old, new, report)
    return report


def _index(items: list[dict]) -> dict[str, dict]:
    return {i["id"]: i for i in items}


def _compare_rules(old: dict, new: dict, report: DiffReport) -> None:
    a, b = _index(old["rules"]), _index(new["rules"])

    for rid in b.keys() - a.keys():
        report.changes.append(Change(
            "rule_added", rid, True, "new rule introduced", after=b[rid]))
    for rid in a.keys() - b.keys():
        report.changes.append(Change(
            "rule_removed", rid, True,
            "rule removed — any determination that relied on it changes", before=a[rid]))

    for rid in a.keys() & b.keys():
        old_rule, new_rule = a[rid], b[rid]
        for key in _SEMANTIC_RULE_FIELDS:
            if old_rule.get(key) != new_rule.get(key):
                report.changes.append(Change(
                    "rule_modified", rid, True,
                    f"{key} changed", field_name=key,
                    before=old_rule.get(key), after=new_rule.get(key)))
        for key in _COSMETIC_RULE_FIELDS:
            if old_rule.get(key) != new_rule.get(key):
                report.changes.append(Change(
                    "rule_annotated", rid, False,
                    f"{key} changed with no effect on meaning", field_name=key))


def _compare_parameters(old: dict, new: dict, report: DiffReport) -> None:
    a, b = _index(old["parameters"]), _index(new["parameters"])

    for pid in b.keys() - a.keys():
        report.changes.append(Change("parameter_added", pid, True, "new parameter"))
    for pid in a.keys() - b.keys():
        report.changes.append(Change("parameter_removed", pid, True, "parameter removed"))

    for pid in a.keys() & b.keys():
        old_values = {(v["effective_from"], str(v.get("at"))): v["value"] for v in a[pid]["values"]}
        new_values = {(v["effective_from"], str(v.get("at"))): v["value"] for v in b[pid]["values"]}

        for key in new_values.keys() - old_values.keys():
            report.changes.append(Change(
                "parameter_value_added", pid, True,
                f"new value {new_values[key]} effective {key[0]}",
                after=new_values[key]))
        for key in old_values.keys() & new_values.keys():
            if old_values[key] != new_values[key]:
                report.changes.append(Change(
                    "parameter_value_changed", pid, True,
                    f"{old_values[key]} -> {new_values[key]} effective {key[0]}",
                    before=old_values[key], after=new_values[key]))
        if a[pid].get("dimensions") != b[pid].get("dimensions"):
            report.changes.append(Change(
                "parameter_modified", pid, True, "dimensions changed",
                field_name="dimensions",
                before=a[pid].get("dimensions"), after=b[pid].get("dimensions")))


def _compare_variables(old: dict, new: dict, report: DiffReport) -> None:
    a, b = _index(old["variables"]), _index(new["variables"])

    for vid in b.keys() - a.keys():
        report.changes.append(Change("variable_added", vid, True, "new variable"))
    for vid in a.keys() - b.keys():
        report.changes.append(Change("variable_removed", vid, True, "variable removed"))
    for vid in a.keys() & b.keys():
        for key in ("value_type", "periodicity", "entity", "input"):
            if a[vid].get(key) != b[vid].get(key):
                report.changes.append(Change(
                    "variable_modified", vid, True, f"{key} changed",
                    field_name=key, before=a[vid].get(key), after=b[vid].get(key)))
