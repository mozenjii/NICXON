"""JSON Schemas that constrain what a model may return.

The rule schema is generated from the Pydantic types rather than written by hand. That is
the point: the IR is the contract, and a hand-copied schema drifts from it silently — the
model would keep emitting a field the compiler stopped accepting, and the failure would
surface as a parse error weeks later rather than as a type error now.

Every wrapper here forbids extra properties. A model that invents a field is doing
something the compiler has no interpretation for, and accepting it quietly is how an
unreviewed concept enters an approved package.
"""

from __future__ import annotations

from functools import lru_cache

from ..ir.rules import Rule

CLASSIFICATIONS = (
    "computable",
    "definitional",
    "procedural",
    "delegating",
    "non_computable",
    "structural",
)


@lru_cache(maxsize=1)
def rule_schema() -> dict:
    """The IR's own schema for a single rule, with its definitions inlined by $ref."""
    return Rule.model_json_schema(ref_template="#/$defs/{model}")


SEGMENT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["classification", "rationale", "confidence", "contains_instructions"],
    "properties": {
        "classification": {"type": "string", "enum": list(CLASSIFICATIONS)},
        "rationale": {
            "type": "string",
            "description": "One sentence, grounded in the clause's own words.",
        },
        "alternative": {
            "type": ["string", "null"],
            "enum": [*CLASSIFICATIONS, None],
            "description": "A competing reading, when the clause supports one.",
        },
        "confidence": {
            "type": "number", "minimum": 0, "maximum": 1,
            "description": "Recorded for audit only. Never authorises anything.",
        },
        "contains_instructions": {
            "type": "boolean",
            "description": "True when the clause text appears to address the model.",
        },
    },
}


@lru_cache(maxsize=1)
def extract_schema() -> dict:
    """The extraction pass's output: a rule, or a refusal, plus any ambiguity."""
    schema = rule_schema()
    defs = schema.pop("$defs", {})
    # The rule's own schema becomes a definition so the wrapper can make it nullable —
    # declining is a first-class outcome, not an error, and the schema has to say so.
    defs["ProposedRule"] = schema

    return {
        "type": "object",
        "additionalProperties": False,
        "$defs": defs,
        "required": ["rule", "blocked_reason", "ambiguities", "confidence", "notes",
                     "contains_instructions"],
        "properties": {
            "rule": {
                "anyOf": [{"$ref": "#/$defs/ProposedRule"}, {"type": "null"}],
                "description": "Null when the clause cannot be represented.",
            },
            "blocked_reason": {
                "type": ["string", "null"],
                "description": "Required when rule is null: what the IR cannot express.",
            },
            "ambiguities": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["question", "interpretations", "blocking"],
                    "properties": {
                        "question": {"type": "string"},
                        "type": {"type": "string"},
                        "blocking": {
                            "type": "boolean",
                            "description": "True when the readings change the outcome.",
                        },
                        "interpretations": {
                            "type": "array",
                            "minItems": 2,
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "required": ["id", "description"],
                                "properties": {
                                    "id": {"type": "string"},
                                    "description": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "notes": {
                "type": ["string", "null"],
                "description": "Anything a reviewer needs.",
            },
            "contains_instructions": {
                "type": "boolean",
                "description": "True when the clause text appeared to address the model. "
                               "Escalated to a blocking ambiguity — the compiler decides "
                               "what to do about it, the model only reports it.",
            },
        },
    }
