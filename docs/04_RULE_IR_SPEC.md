# 04 — RuleWeaver Intermediate Representation (IR) Specification

**Status:** Draft architectural specification. Implementation has not yet begun.  
**Goal:** Define the minimum canonical representation needed for v0.1 without encoding one jurisdiction's vocabulary into the core.

## Design requirements

The IR must support:

- stable IDs;
- jurisdiction and source version metadata;
- typed values;
- entities;
- variables/inputs;
- parameters changing over time;
- boolean and arithmetic expressions;
- eligibility/calculation rules;
- explicit effective periods;
- exceptions/overrides;
- definitions;
- source provenance;
- review state;
- ambiguity;
- deterministic evaluation;
- adapter feature detection.

## Package-level object

```json
{
  "schema_version": "0.1",
  "package_id": "example-benefit-2026",
  "jurisdiction": "example",
  "sources": [],
  "entities": [],
  "definitions": [],
  "variables": [],
  "parameters": [],
  "rules": [],
  "ambiguities": [],
  "tests": [],
  "approvals": [],
  "metadata": {}
}
```

## IDs

IDs should be stable, human-readable where practical, and unique within a package.

Recommended style:

```text
entity.person
entity.household
var.person.age
var.household.gross_income
param.benefit.income_limit
rule.benefit.basic_eligibility
source.policy_2026.section_4_2
```

Do not encode mutable values such as dates or amounts into IDs.

## Source span

Every interpreted semantic object should reference source spans.

```json
{
  "source_id": "policy-2026",
  "node_id": "sec-4.2-p3",
  "quote_hash": "sha256:...",
  "start_char": 120,
  "end_char": 287,
  "page": 14,
  "selector": null
}
```

Not all formats provide pages/characters. The model must allow multiple selector methods.

## Entity

Represents a person/group/thing about which rules compute.

```json
{
  "id": "entity.person",
  "label": "Person"
}
```

v0.1 should support simple entity relationships but avoid inventing a complete ontology framework.

## Value types

Initial types:

- boolean;
- integer;
- decimal;
- string;
- date;
- duration;
- money (amount + currency);
- enumeration;
- list/set where needed;
- unknown.

Money must never be represented as a binary floating-point semantic value.

## Variable

Represents input or computed facts associated with an entity/context.

```json
{
  "id": "var.household.gross_income",
  "entity": "entity.household",
  "value_type": "money",
  "periodicity": "year",
  "input": true,
  "sources": []
}
```

## Parameter

A parameter is a rule value that may vary over time or dimensions.

```json
{
  "id": "param.benefit.income_limit",
  "value_type": "money",
  "dimensions": ["household_size"],
  "values": [
    {
      "effective_from": "2026-01-01",
      "effective_to": null,
      "when": {"household_size": 1},
      "value": {"amount": "32000.00", "currency": "USD"},
      "sources": []
    }
  ]
}
```

Numbers stated in legislation should normally become parameters rather than being embedded directly in rule expressions.

## Expression system

Expressions must be an AST, never arbitrary source code.

### Literal

```json
{"op": "literal", "value": 18}
```

### Reference

```json
{"op": "ref", "id": "var.person.age"}
```

### Parameter lookup

```json
{
  "op": "parameter",
  "id": "param.benefit.income_limit",
  "args": {"household_size": {"op": "ref", "id": "var.household.size"}}
}
```

### Comparison

```json
{
  "op": "lte",
  "left": {"op": "ref", "id": "var.household.gross_income"},
  "right": {"op": "parameter", "id": "param.benefit.income_limit", "args": {}}
}
```

### Boolean

```json
{"op": "all", "args": [/* expressions */]}
{"op": "any", "args": [/* expressions */]}
{"op": "not", "arg": {/* expression */}}
```

### Arithmetic

Start with:

- add;
- subtract;
- multiply;
- divide;
- min;
- max;
- round with an explicit rule.

Do not inherit host-language numeric semantics by accident.

## Rule

```json
{
  "id": "rule.benefit.basic_eligibility",
  "kind": "eligibility",
  "effective": {
    "from": "2026-01-01",
    "to": null
  },
  "when": {
    "op": "all",
    "args": [
      {
        "op": "gte",
        "left": {"op": "ref", "id": "var.person.age"},
        "right": {"op": "literal", "value": 18}
      }
    ]
  },
  "then": {
    "assign": {
      "target": "var.person.basic_eligible",
      "value": {"op": "literal", "value": true}
    }
  },
  "exceptions": [],
  "sources": [],
  "interpretation": {
    "status": "needs_review"
  }
}
```

## Rule kinds for v0.1

- eligibility;
- assignment/calculation;
- classification;
- parameter selection;
- requirement/check.

Do not create dozens of legal-deontic rule types until a real use case needs them.

## Exceptions and overrides

Legal rules frequently contain explicit exceptions. v0.1 should support a constrained model:

```json
{
  "id": "exception.student_exclusion",
  "when": {/* expression */},
  "effect": "disable_base_rule",
  "priority": 100,
  "sources": []
}
```

Priority semantics must be deterministic and validated.

Long term, richer defeasibility may map to LegalRuleML or another formalism. Do not prematurely implement full defeasible logic in v0.1.

## Effective periods

All rules/parameters may have:

- `effective_from` inclusive;
- `effective_to` exclusive by project convention unless a specific imported format defines otherwise.

This convention must be documented and enforced uniformly.

**Field spelling is normative:** rules and parameters both use flat `effective_from` /
`effective_to`. The nested `effective: {from, to}` shown in the Rule example above is
legacy and must not be used.

---

## v0.1 construct additions

**Added by ADR-020.** Every construct here was forced by hand-encoding real SNAP text; see
`15_VOCABULARY.md` for the clause that requires each. These are not speculative
generalisations — each has a citation behind it.

### Aggregation over group members

Required by `household_income` (sum over members) and
`household_has_elderly_or_disabled_member` (existential over members).
Closes open question 4.

```json
{
  "op": "sum_over",
  "entity": "household_member",
  "scope": {"op": "ref", "id": "var.household"},
  "value": {"op": "ref", "id": "var.member.earned_income"},
  "where": {"op": "not", "arg": {"op": "ref", "id": "var.member.is_excluded"}}
}
```

Operators: `sum_over`, `count_over`, `min_over`, `max_over`, `any_over`, `all_over`.
`where` is optional; when omitted, all members in scope are included.

**Unknown propagation is explicit, not incidental.** `sum_over` yields `unknown` if any
included member's `value` is `unknown`. `any_over` yields `true` if any member matches even
when others are `unknown` (Kleene), and `unknown` only when no member matches and at least
one is `unknown`. `all_over` is the dual. An empty scope yields the operator's identity —
`0` for `sum_over`, `0` for `count_over`, `false` for `any_over`, `true` for `all_over` —
and never `unknown`.

### Explicit rounding

Required by "rounding the results upwards as necessary" (273.9(a)(3)) and "rounded up to
the nearest whole dollar" (273.9(d)(1)). Closes open question 5.

```json
{"op": "round", "arg": {"op": "ref", "id": "var.x"}, "mode": "up", "to": "1"}
```

`mode`: `up` | `down` | `half_up` | `half_even` | `toward_zero`.
`to` is a decimal string giving the quantum — `"1"` for whole dollars, `"0.01"` for cents.
There is no default. A `round` node without both fields is a schema error, and no other
operator rounds implicitly.

### Period conversion

Required by "annual income poverty guidelines shall be divided by 12" (273.9(a)(3)).
Closes open question 1 for the conversion case.

```json
{"op": "convert_period", "arg": {"op": "parameter", "id": "param.snap.fpl", "args": {}},
 "from": "year", "to": "month", "method": "divide"}
```

`method`: `divide` (uniform split) | `prorate_days` (calendar-sensitive).
Period conversion is **never implicit**. An expression comparing a `year`-periodicity
value to a `month`-periodicity value without an intervening `convert_period` is a type
error, not a silent coercion.

### Clamp and piecewise

Required by "for household sizes greater than six, the standard deduction shall be equal
to the standard deduction for a six-person household" (273.9(d)(1)(i)).

The clean encoding clamps the **lookup index**, not the resulting value:

```json
{
  "op": "parameter",
  "id": "param.snap.standard_deduction",
  "args": {
    "household_size": {
      "op": "clamp",
      "arg": {"op": "ref", "id": "var.household.size"},
      "max": {"op": "literal", "value": 6}
    }
  }
}
```

`clamp` takes optional `min` and `max`; at least one is required.

For schedules that continue past a threshold by increment — the poverty guideline above
eight persons — use `piecewise`, evaluated top-down with the first matching case winning:

```json
{
  "op": "piecewise",
  "cases": [{"when": {"op": "lte", "left": {"op": "ref", "id": "var.household.size"},
                      "right": {"op": "literal", "value": 8}},
             "then": {"op": "parameter", "id": "param.snap.fpl", "args": {}}}],
  "otherwise": {"op": "add", "args": []}
}
```

`otherwise` is mandatory. A `piecewise` with no matching case and no `otherwise` would
yield `unknown` silently, which `06_VERIFICATION_SAFETY.md` forbids.

### Substitutive exceptions

Required by 273.9(d)(6)(ii): the shelter deduction is uncapped, **except** where the
household contains no elderly or disabled member, where an area cap applies. Encoding this
as disable-plus-shadow-rule would duplicate the condition and sever the source
correspondence required by `README.md:36`.

```json
{
  "id": "exception.snap.shelter_cap_applies",
  "when": {"op": "not", "arg": {"op": "ref", "id": "var.household.has_elderly_or_disabled_member"}},
  "effect": "substitute",
  "substitute": {
    "assign": {
      "target": "var.household.excess_shelter_deduction",
      "value": {"op": "min", "args": [
        {"op": "ref", "id": "var.household.raw_shelter_excess"},
        {"op": "parameter", "id": "param.snap.shelter_cap", "args": {}}
      ]}
    }
  },
  "priority": 100,
  "sources": []
}
```

`effect`: `disable_base_rule` | `substitute`. When `substitute`, the `substitute` object
replaces the base rule's `then` and is required.

**Priority semantics (closes open question 3).** Within one rule, exceptions are evaluated
in ascending `priority`; the **lowest-numbered matching exception wins** and evaluation
stops. Two matching exceptions at equal priority is a **blocking** diagnostic (`RW3xxx`),
never an arbitrary tie-break. Priority is rule-local and carries no meaning across rules —
cross-rule precedence uses `overrides` below.

### Norm override — "notwithstanding"

Required by 273.9(d)(1)(iii): "**Notwithstanding** paragraphs (d)(1)(i) and (d)(1)(ii)…
the standard deduction… shall not be less than $144…". A statutory floor that overrides
the computed value — cross-rule precedence, which `priority` cannot express.

```json
{
  "id": "rule.snap.standard_deduction_minimum",
  "kind": "assignment",
  "overrides": ["rule.snap.standard_deduction_computed"],
  "when": {"op": "literal", "value": true},
  "then": {"assign": {"target": "var.household.standard_deduction",
                      "value": {"op": "max", "args": []}}}
}
```

`overrides` lists rule IDs this rule takes precedence over when both assign the same
target. The validator must reject a cycle in the override graph and must reject an
`overrides` entry naming a rule that does not assign the same target — both are `RW3xxx`
blocking diagnostics.

### Resolved open questions

Questions 1 (period algebra, conversion case), 3 (exception priority), 4 (aggregation) and
5 (rounding) are closed by this section. Question 2 (entity relationships) is answered
narrowly: v0.1 supports one group-to-member relation, which is all `household` requires.
Questions 6, 7 and 8 remain open and are not needed for the SNAP fixture.

## Definitions

Definitions are semantic objects because laws often redefine ordinary terms.

```json
{
  "id": "definition.household_income",
  "term": "household income",
  "text": "...",
  "sources": [],
  "linked_objects": ["var.household.gross_income"]
}
```

A definition may be non-executable but still affects interpretation.

## Ambiguity

```json
{
  "id": "ambiguity.income_scope_001",
  "type": "scope",
  "blocking": true,
  "sources": [],
  "question": "Does income mean gross or taxable household income?",
  "interpretations": [
    {
      "id": "a",
      "description": "gross household income",
      "candidate_changes": []
    },
    {
      "id": "b",
      "description": "taxable household income",
      "candidate_changes": []
    }
  ],
  "resolution": null
}
```

A blocking ambiguity prevents affected rules from becoming executable/approved until resolved or explicitly marked as requiring runtime human judgment.

## Interpretation/review state

Suggested states:

```text
proposed
needs_review
approved
rejected
superseded
human_judgment_required
```

Model confidence may be recorded as metadata but must not determine approval.

## Unknown values

The evaluator must distinguish:

- `false`;
- `true`;
- `unknown/missing`;
- evaluation error.

Do not silently coerce missing inputs to false or zero.

## Provenance

At minimum, semantic objects record:

- direct source spans;
- compiler pass/model run that proposed them;
- reviewer actions;
- derivation relationships where one rule is produced from another artifact.

See `06_VERIFICATION_SAFETY.md` for required traceability.

## Schema versioning

Every serialized package must include `schema_version`.

Rules:

- patch: serialization-compatible clarifications;
- minor: additive backwards-compatible fields/features;
- major: semantic or structural breaking changes.

Adapters must declare which IR versions/features they support.

## Open questions to settle during M0/M1

1. exact period algebra and periodicity model;
2. entity relationship model;
3. exception priority semantics;
4. aggregation semantics across entity groups;
5. explicit rounding semantics;
6. currency conversion (likely out of core v0.1);
7. whether definitions can be executable aliases or remain separate;
8. representation of human-required predicates.

Do not resolve these through convenience alone. Each needs examples and tests.
