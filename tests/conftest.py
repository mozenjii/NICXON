"""Shared fixtures for the SNAP golden corpus."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

from ruleweaver.ir import RulePackage
from ruleweaver.runtime import Context, Evaluator, ParameterTable

FIXTURE = Path(__file__).resolve().parents[1] / "examples" / "snap" / "rules.json"

# Externally published tables the regulation references but does not contain.
# Keys are dimension values in alphabetical order of dimension name.
# FY2026 figures for a household of three in the 48 states and DC.
PARAMETER_OVERRIDES = {
    "param.snap.fpl_annual": {
        ("1", "48_dc"): Decimal("15650"),
        ("3", "48_dc"): Decimal("26650"),
        ("8", "48_dc"): Decimal("54150"),
    },
    # The three-person computed value sits BELOW the statutory minimum on purpose.
    # With both at 204 the "notwithstanding" override is unobservable — max(204,204)
    # is 204 whether or not the override fires — and mutation testing showed the suite
    # could not tell the override had been deleted.
    "param.snap.standard_deduction": {
        ("1", "48_dc"): Decimal("204"),
        ("3", "48_dc"): Decimal("180"),
        ("6", "48_dc"): Decimal("234"),
    },
    "param.snap.standard_deduction_minimum": {("48_dc",): Decimal("204")},
    "param.snap.shelter_cap": {("48_dc",): Decimal("672")},
}


@pytest.fixture(scope="session")
def package() -> RulePackage:
    return RulePackage.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


@pytest.fixture()
def evaluator(package: RulePackage) -> Evaluator:
    return Evaluator(package, ParameterTable(package, overrides=PARAMETER_OVERRIDES))


def member(age: int, earned: str = "0", unearned: str = "0", disabled: bool = False) -> dict:
    return {
        "var.member.age": Decimal(age),
        "var.member.receives_disability_benefit": disabled,
        "var.member.earned_income": Decimal(earned),
        "var.member.unearned_income": Decimal(unearned),
    }


def household(members: list[dict], size: int | None = None, shelter: str = "0",
              jurisdiction: str = "48_dc") -> Context:
    return Context(
        household={
            "var.household.size": Decimal(size if size is not None else len(members)),
            "var.household.jurisdiction": jurisdiction,
            "var.household.shelter_expenses": Decimal(shelter),
        },
        members=members,
    )
