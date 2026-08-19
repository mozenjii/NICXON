"""The OpenFisca adapter.

OpenFisca itself is not a dependency and is not installed, so these tests check what the
adapter produces, not what OpenFisca does with it. That boundary is stated rather than
hidden: the export is structurally checked here, and running the generated package against
OpenFisca is an unverified claim until someone does it.

The tests that matter most are the refusals — an unapproved rule, a rule OpenFisca cannot
represent, a parameter with no values. Silently producing a plausible-looking country
package from any of those is the failure mode with real consequences.
"""

from __future__ import annotations

import ast
import json

import pytest

from conftest import FIXTURE
from ruleweaver.adapters.openfisca import Lowerer, Unlowerable, export
from ruleweaver.approval import current_hashes
from ruleweaver.ir import RulePackage
from ruleweaver.ir.expressions import Aggregate, Arith, Compare, Lit, Ref, Round
from ruleweaver.review import Decision, ReviewEvent, ReviewLog


@pytest.fixture()
def approved_log(package: RulePackage) -> ReviewLog:
    log = ReviewLog()
    for rule_id, (rule_hash, source_hash) in current_hashes(package).items():
        log.append(ReviewEvent(rule_id=rule_id, reviewer="alice",
                               decision=Decision.APPROVE,
                               rule_hash=rule_hash, source_hash=source_hash))
    return log


class TestLowering:
    def lower(self, expr) -> str:
        return Lowerer().lower(expr).source

    def test_a_household_variable_asks_the_household(self):
        assert self.lower(Ref(op="ref", id="var.household.size")) == \
            "household('size', period)"

    def test_a_member_variable_asks_the_person(self):
        assert self.lower(Ref(op="ref", id="var.member.age")) == "person('age', period)"

    def test_a_sum_over_members_becomes_an_entity_aggregation(self):
        expr = Aggregate(op="sum_over", entity="household_member",
                         scope=Ref(op="ref", id="var.household"),
                         value=Ref(op="ref", id="var.member.earned_income"))
        assert self.lower(expr) == "household.sum(person('earned_income', period))"

    def test_a_filtered_aggregation_is_refused(self):
        """A mask has to be a variable OpenFisca can compute per member; inlining the
        filter would produce a formula that silently sums the wrong people."""
        expr = Aggregate(op="sum_over", entity="household_member",
                         scope=Ref(op="ref", id="var.household"),
                         value=Ref(op="ref", id="var.member.earned_income"),
                         where=Ref(op="ref", id="var.member.is_elderly_or_disabled"))
        with pytest.raises(Unlowerable, match="per-member mask"):
            self.lower(expr)

    def test_min_and_max_fold_pairwise(self):
        expr = Arith(op="max", args=[Lit(op="literal", value=0),
                                     Ref(op="ref", id="var.household.size")])
        assert self.lower(expr) == "np.maximum(0, household('size', period))"

    def test_rounding_up_to_the_dollar_uses_ceil(self):
        expr = Round(op="round", arg=Ref(op="ref", id="var.household.size"),
                     mode="up", to="1")
        assert self.lower(expr) == "np.ceil(household('size', period))"

    def test_a_quantum_other_than_one_scales_around_the_rounding(self):
        expr = Round(op="round", arg=Ref(op="ref", id="var.household.size"),
                     mode="down", to="0.01")
        source = self.lower(expr)
        assert "/ 0.01" in source and "* 0.01" in source

    def test_a_comparison_keeps_its_operator(self):
        expr = Compare(op="gte", left=Ref(op="ref", id="var.household.size"),
                       right=Lit(op="literal", value=3))
        assert self.lower(expr) == "(household('size', period) >= 3)"

    def test_lowering_records_what_the_formula_needs(self):
        expr = Compare(op="gte", left=Ref(op="ref", id="var.household.size"),
                       right=Lit(op="literal", value=3))
        lowered = Lowerer().lower(expr)
        assert lowered.household_vars == {"size"}
        assert not lowered.uses_numpy


class TestExport:
    def test_nothing_is_exported_without_approval(self, package):
        """Export is a deployment step. An adapter that ignored the gate would be the one
        path around it that nobody is watching."""
        result = export(package, log=ReviewLog())
        assert result.exported == []
        assert len(result.skipped) == len(package.rules)
        assert any(d.code == "RW8002" for d in result.diagnostics)
        assert not result.ok

    def test_every_approved_rule_is_exported(self, package, approved_log):
        result = export(package, log=approved_log)
        assert len(result.exported) == len(package.rules)
        assert result.skipped == {}

    def test_a_rule_rejected_after_approval_stops_being_exported(self, package,
                                                                 approved_log):
        target = package.rules[0]
        approved_log.append(ReviewEvent(
            rule_id=target.id, reviewer="bob", decision=Decision.REJECT,
            rule_hash="stale", source_hash="stale",
            note="the threshold does not match the regulation"))
        result = export(package, log=approved_log)
        assert target.id not in result.exported

    def test_the_unknown_gap_is_reported_on_every_export(self, package, approved_log):
        """The one semantic difference that changes outcomes, and it cannot be fixed
        inside the adapter — so it is said out loud instead."""
        result = export(package, log=approved_log)
        [warning] = [d for d in result.diagnostics if d.code == "RW8001"]
        assert "no unknown state" in warning.message
        assert "denial" in warning.details["detail"]

    def test_the_generated_module_repeats_the_warning(self, package, approved_log):
        module = export(package, log=approved_log).files["variables.py"]
        assert "OpenFisca has no unknown state" in module

    def test_the_generated_module_is_valid_python(self, package, approved_log):
        """Not evidence that it is correct — only that it parses. Running it against
        OpenFisca is a separate claim this suite does not make."""
        module = export(package, log=approved_log).files["variables.py"]
        ast.parse(module)

    def test_every_variable_carries_its_citation(self, package, approved_log):
        """A generated formula with no route back to the regulation is the artifact this
        project exists to avoid producing."""
        module = export(package, log=approved_log).files["variables.py"]
        tree = ast.parse(module)
        classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
        assert classes
        for node in classes:
            doc = ast.get_docstring(node) or ""
            assert "7 CFR" in doc, f"{node.name} has no citation"

    def test_exceptions_become_prioritised_selection(self, package, approved_log):
        """A substitutive exception has a faithful vectorised form; the priority order
        decides which case wins."""
        module = export(package, log=approved_log).files["variables.py"]
        assert "np.select(" in module

    def test_a_parameter_with_no_values_is_an_error(self, package, approved_log):
        """The fixture cites published FNS tables it does not contain. The export is
        structurally complete and will not run until they are supplied — which is a
        finding, not something to paper over with an empty file."""
        result = export(package, log=approved_log)
        empty = [d for d in result.diagnostics if d.code == "RW8005"]
        assert empty
        assert not result.ok
        assert all("parameters/snap/fpl_annual" not in name for name in result.files)

    def test_a_populated_parameter_becomes_yaml(self, package, approved_log):
        result = export(package, log=approved_log)
        yaml = result.files["parameters/snap/earned_income_deduction_rate.yaml"]
        assert "values:" in yaml
        assert "0.20" in yaml

    def test_the_entity_model_is_generated(self, package, approved_log):
        entities = export(package, log=approved_log).files["entities.py"]
        ast.parse(entities)
        assert "build_entity" in entities

    def test_writing_lays_the_files_out_on_disk(self, package, approved_log, tmp_path):
        root = export(package, log=approved_log).write(tmp_path)
        assert (root / "variables.py").exists()
        assert (root / "parameters" / "snap" / "shelter_income_share.yaml").exists()


class TestDryRun:
    def test_skipping_approval_is_possible_but_marked(self, package):
        """Available for inspecting what an export *would* contain. The docstring says it
        must not be deployed, and the gate says so again on the normal path."""
        result = export(package, require_approval=False)
        assert len(result.exported) == len(package.rules)
        assert not any(d.code == "RW8002" for d in result.diagnostics)

    def test_an_empty_package_is_not_a_successful_export(self):
        empty = RulePackage(schema_version="0.1.0", package_id="empty",
                            jurisdiction="nowhere")
        result = export(empty, require_approval=False)
        assert result.exported == []


class TestFixtureShape:
    def test_the_fixture_uses_only_substitutive_exceptions(self):
        """`disable_base_rule` is refused by the adapter. If the fixture ever grows one,
        this test fails and the refusal path needs a real case behind it."""
        document = json.loads(FIXTURE.read_text(encoding="utf-8"))
        effects = {e["effect"] for r in document["rules"] for e in r.get("exceptions", [])}
        assert effects <= {"substitute"}
