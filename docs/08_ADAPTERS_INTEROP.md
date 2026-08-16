# 08 — Adapters and Interoperability

## Adapter principle

RuleWeaver does not replace existing legal/rules-as-code ecosystems.

The canonical IR should be able to export supported semantic subsets to specialized systems.

## OpenFisca — first executable target

### Why first

OpenFisca already models tax/benefit systems using:

- entities;
- variables;
- formulas;
- legislation parameters;
- periods;
- tests;
- simulation APIs.

That overlaps strongly with RuleWeaver's v0.1 domain.

### Mapping candidates

| RuleWeaver | OpenFisca concept |
|---|---|
| Entity | Entity |
| Variable | Variable |
| Parameter | legislation parameter |
| Effective period | dated formula/parameter behavior |
| Calculation rule | Variable formula |
| Policy-intent test | YAML test |
| Source reference | variable/parameter metadata/reference |

### Important difference

RuleWeaver preserves proposed/ambiguous/review semantics and richer provenance that should not be forced into OpenFisca concepts.

The adapter exports approved, representable semantics only.

### Adapter validation

For every exported rule package:

1. generate OpenFisca artifacts;
2. run generated + human tests in RuleWeaver reference evaluator;
3. run equivalent tests in OpenFisca;
4. compare outputs;
5. fail the adapter build on unexplained differences.

## Catala — later high-assurance target

Catala is a domain-specific language designed to keep legal specification and executable code closely linked through literate programming.

RuleWeaver should treat Catala as:

- a target for rules compatible with its semantic model;
- a source of design lessons on exceptions, scopes, and legal-text/code correspondence;
- a possible higher-assurance backend for selected domains.

Do not make Catala a v0.1 dependency.

## Akoma Ntoso — document interoperability

Akoma Ntoso is primarily a standard for legal documents and their structure/metadata, not the RuleWeaver executable IR.

Use cases:

- ingest structured legislative documents;
- preserve existing section/article IDs;
- preserve metadata and references;
- export source-linked annotations without flattening document structure.

Do not duplicate a full legal-document model inside RuleWeaver when stable imported identifiers can be retained.

## LegalRuleML — legal-rule interchange

LegalRuleML can represent legal normative concepts including:

- obligations/permissions/prohibitions;
- defeasibility;
- temporality;
- jurisdiction;
- rule-text correspondence;
- authorial information.

RuleWeaver v0.1 should not attempt to implement all LegalRuleML semantics.

Instead:

1. build a small IR suited to computable tax/benefit rules;
2. preserve enough metadata for future mapping;
3. create an export adapter for the supported subset;
4. explicitly report unsupported semantics.

## W3C PROV — provenance interchange

The internal provenance model can map concepts to W3C PROV:

| RuleWeaver | PROV idea |
|---|---|
| source/rule/package artifact | Entity |
| compiler/review/adapter run | Activity |
| model/reviewer/system | Agent |
| derivation | wasDerivedFrom |
| generation | wasGeneratedBy |
| input usage | used |
| responsibility | wasAttributedTo / wasAssociatedWith |

A PROV export can be a later interoperability feature.

## JSON Schema

Use JSON Schema to publish machine-readable constraints for serialized IR/package artifacts.

Python Pydantic models may be the implementation types, but generated/published JSON Schema should be treated as a public interchange contract.

## Adapter capability negotiation

Every adapter should publish a feature matrix.

Example:

```json
{
  "adapter": "openfisca",
  "version": "0.1.0",
  "ir_versions": ["0.1"],
  "features": {
    "boolean_conditions": true,
    "dated_parameters": true,
    "simple_exceptions": "partial",
    "human_judgment_predicates": false
  }
}
```

Compilation of unsupported features must fail or require an explicit opt-in transformation marked as lossy.

## Adapter interface

Conceptually:

```text
analyze(package) -> CapabilityReport
compile(package) -> TargetArtifactSet + Diagnostics
validate(target_artifacts) -> Diagnostics
```

Adapters must not mutate canonical approved IR.
