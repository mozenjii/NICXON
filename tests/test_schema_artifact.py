"""The published schema must match the code that generates it.

A schema file that has drifted from the types is worse than no schema: consumers validate
against it, pass, and then fail at load. This test makes drift a build failure.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ruleweaver.ir import RulePackage

SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "ruleweaver-0.1.schema.json"


@pytest.fixture(scope="module")
def published() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def test_schema_file_exists():
    assert SCHEMA.exists(), "run the export in docs/13_REPO_STRUCTURE.md to regenerate"


def test_schema_matches_the_types(published):
    current = RulePackage.model_json_schema()
    stripped = {k: v for k, v in published.items() if not k.startswith("$schema") and k != "$id"}
    assert stripped == current, (
        "schemas/ruleweaver-0.1.schema.json has drifted from ruleweaver.ir — regenerate it"
    )


def test_schema_declares_its_dialect(published):
    assert published["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_schema_is_addressable(published):
    assert published["$id"].endswith("ruleweaver-0.1.schema.json")


def test_expression_union_is_closed(published):
    """The AST must remain a closed union: an open schema would let arbitrary
    structures through, which is the property that keeps generated text out."""
    defs = published["$defs"]
    assert "Lit" in defs and "Aggregate" in defs
    for name in ("Lit", "Ref", "Compare", "Aggregate", "Piecewise"):
        assert defs[name].get("additionalProperties") is False, f"{name} accepts extra keys"
