"""The approval gate.

README principle 4 — "No extracted rule is executable in an approved package until it
passes review" — was a stated principle with nothing enforcing it: the evaluator ran any
package handed to it. This module is the enforcement, and it lives outside `review/` on
purpose. Approval is a property of the *runtime*, checked by whatever executes rules; the
reviewer application is only one way to produce the evidence.

Three things are deliberate:

**The gate reads the log, never a flag on the rule.** Status is derived
(`review/decisions.py`), so a rule whose clause was re-fetched and changed falls out of
the approved set without anyone remembering to revoke it.

**Excluding a rule leaves its target unknown, not false.** A filtered package is still a
valid package: the rules that survive reference variables the excluded rules would have
assigned, and those evaluate to `unknown` and propagate. That is the same four-state
behaviour a missing input gets, and it is the honest answer — "this determination rests on
a rule nobody has approved" is not the same claim as "this household does not qualify".

**Hashing is shared with the reviewer.** `rule_digest` and `source_digest` are the
functions the review application records against. Two implementations would drift, and the
failure mode of drift is an approval that silently no longer matches.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .hashing import digest
from .ir import RulePackage
from .review.decisions import ReviewLog, Status


def rule_digest(rule) -> str:
    """Digest of a rule's full structured form — what the reviewer approved."""
    return digest(rule.model_dump(mode="json", by_alias=True))


def source_digest(rule) -> str:
    """Digest of the source spans a rule cites.

    Separate from `rule_digest` so the two staleness causes stay distinguishable: an
    edited rule and a moved clause are different events and want different handling.
    """
    return digest([s.model_dump(mode="json") for s in rule.sources])


def current_hashes(package: RulePackage) -> dict[str, tuple[str, str]]:
    """Every rule's (rule_hash, source_hash) as they are *now*."""
    return {r.id: (rule_digest(r), source_digest(r)) for r in package.rules}


class NotApproved(Exception):
    """Execution was requested for rules that have not passed review."""

    def __init__(self, statuses: dict[str, Status]) -> None:
        self.statuses = statuses
        lines = "\n".join(f"  {rid}: {st.value}" for rid, st in sorted(statuses.items()))
        super().__init__(
            f"{len(statuses)} rule(s) are not approved for execution:\n{lines}\n"
            "Review them first, or pass the package through approved_subset() and accept "
            "that determinations resting on unapproved rules will be unknown."
        )


@dataclass
class GateReport:
    """What the gate found. Reported rather than raised so a caller can show it."""

    approved: list[str] = field(default_factory=list)
    blocked: dict[str, Status] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.blocked

    def __str__(self) -> str:
        if not self.approved and not self.blocked:
            return "no rules"
        parts = [f"{len(self.approved)} approved, {len(self.blocked)} blocked"]
        counts: dict[str, int] = {}
        for status in self.blocked.values():
            counts[status.value] = counts.get(status.value, 0) + 1
        for name in sorted(counts):
            parts.append(f"  {name:28} {counts[name]}")
        return "\n".join(parts)


def check(package: RulePackage, log: ReviewLog) -> GateReport:
    """Classify every rule in the package as approved or blocked."""
    report = GateReport()
    for rule_id, (rh, sh) in current_hashes(package).items():
        status = log.status(rule_id, rule_hash=rh, source_hash=sh)
        if status is Status.APPROVED:
            report.approved.append(rule_id)
        else:
            report.blocked[rule_id] = status
    report.approved.sort()
    return report


def approved_subset(package: RulePackage, log: ReviewLog) -> tuple[RulePackage, GateReport]:
    """The package with unapproved rules removed, plus what was removed and why.

    Entities, variables and parameters are kept whole. Dropping a variable because the only
    rule assigning it was excluded would turn a reference to it into a validation error,
    which reports the wrong problem: the reference is fine, the approval is missing.
    """
    report = check(package, log)
    keep = set(report.approved)
    subset = package.model_copy(update={"rules": [r for r in package.rules if r.id in keep]})
    return subset, report


def enforce(package: RulePackage, log: ReviewLog) -> RulePackage:
    """Return the package only if every rule in it is approved.

    Raises rather than returning a report so a caller who forgets to check cannot
    accidentally execute unapproved rules — the same reasoning as `InvalidPackage`.
    """
    report = check(package, log)
    if not report.ok:
        raise NotApproved(report.blocked)
    return package
