# 02 — Product Specification

## Product statement

RuleWeaver is a developer/expert tool that turns authoritative natural-language rules into structured candidate rules, validates them, generates tests, supports source-linked human review, and emits approved executable artifacts.

## Primary v0.1 workflow

### Input

An official policy source containing computable eligibility or calculation logic.

Examples:

- public benefit manual section;
- tax rule;
- benefits circular;
- agency eligibility policy;
- authoritative program guidance.

### Processing

1. ingest and normalize the source;
2. preserve document hierarchy and stable citations;
3. identify potentially normative/computable clauses;
4. identify definitions and parameters;
5. propose structured rules;
6. resolve explicit cross-references;
7. emit ambiguity diagnostics;
8. validate IR structure and semantics;
9. generate candidate tests;
10. present rule + source + tests for review;
11. approve/reject/edit;
12. execute approved rules deterministically;
13. export the supported subset to a target runtime.

### Output

A **Rule Package** containing:

- source manifest and hashes;
- source hierarchy;
- approved rule IR;
- parameters and temporal values;
- definitions;
- unresolved ambiguity list;
- provenance graph;
- approved policy-intent tests;
- generated tests and their generation provenance;
- diagnostics;
- adapter artifacts;
- compiler/run metadata.

## Primary personas

### Rules engineer

Needs to implement legislation faithfully and quickly. Wants typed rules, source links, tests, and executable adapters.

### Legal/policy reviewer

Needs to verify interpretations without reading code. Wants source text and structured rule side by side, explicit ambiguity, and change impact.

### Program administrator

Needs confidence that a ruleset corresponds to the currently effective program rules. Wants versions, approval records, tests, and audit history.

### Civic-tech / product engineer

Needs stable APIs and executable rules without independently interpreting the full policy corpus.

## Functional requirements

### FR-1 Source fidelity

The system shall preserve source identity, version, hierarchy, and source spans.

### FR-2 Typed semantic output

Every rule proposal shall conform to a typed RuleWeaver IR.

### FR-3 Provenance

Every material rule element shall be traceable to one or more source spans or explicitly marked as inferred/derived without direct textual support.

### FR-4 Ambiguity

The system shall represent multiple plausible interpretations and blocking uncertainty rather than silently selecting one.

### FR-5 Review state

Rules shall have explicit states such as `proposed`, `needs_review`, `approved`, `rejected`, and `superseded`.

### FR-6 Deterministic validation

Rule packages shall be checked for schema, type, reference, temporal, and dependency errors without using an LLM.

### FR-7 Deterministic execution

Approved supported rules shall be executable without an LLM.

### FR-8 Test generation

The system shall generate candidate tests for boundaries, dates, exceptions, and representative combinations where supported.

### FR-9 Human policy-intent tests

The project shall support human-authored tests independent of generated implementation logic.

### FR-10 Change impact

When a source version changes, RuleWeaver shall identify affected source clauses, rules, parameters, dependencies, and tests.

### FR-11 Adapter separation

Target runtimes shall be adapters over the canonical IR, not alternative sources of truth.

### FR-12 Reproducibility

Compiler output shall record model/provider, prompt version, source hashes, compiler version, schema version, and configuration.

## Non-functional requirements

### Auditability

A reviewer must be able to explain why a rule exists, which source it came from, who approved it, and which tests support it.

### Local-first compatibility

Core compilation and evaluation workflows should eventually support local/self-hosted models for privacy-sensitive deployments.

### Provider neutrality

No core semantic type may depend on one model provider's API.

### Determinism after approval

Given the same approved rule package, inputs, and date context, the evaluator must return the same result and trace.

### Stable diagnostics

Compiler/validator errors require stable diagnostic codes for CI and tooling.

### Interoperability

The architecture should preserve enough semantics to map useful subsets to OpenFisca, Catala, LegalRuleML, and other rules engines.

## v0.1 feature set

### Must have

- source model;
- Rule IR;
- deterministic evaluator;
- parameters with effective dates;
- conditions/comparisons/boolean logic;
- exceptions/overrides for a limited supported form;
- diagnostics;
- provenance;
- boundary/date test generation;
- LLM-assisted extraction from one policy corpus;
- review workflow;
- OpenFisca export for supported rules;
- semantic version/change report;
- benchmark runner.

### Should have

- HTML and text input;
- native-text PDF ingestion;
- Akoma Ntoso input where available;
- command-line interface;
- minimal local web review UI;
- JSON rule-package export.

### Could have

- DOCX ingestion;
- OCR;
- LegalRuleML export;
- Catala export;
- VS Code/LSP support;
- GitHub Action for policy changes.

### Won't have in v0.1

- court precedent reasoning;
- legal advice;
- subjective standards adjudication;
- automated publication of authoritative rules;
- autonomous benefit denial/approval;
- generalized legal research chat.

## Product success metrics

### Semantic quality

- rule extraction precision/recall against expert gold;
- source-span alignment accuracy;
- definition/reference linking accuracy;
- parameter/date extraction accuracy;
- ambiguity detection recall on annotated cases.

### Executability

- percentage of approved supported rules that compile;
- target adapter differential-test agreement;
- deterministic evaluator pass rate on gold tests.

### Review efficiency

- time from source clause to approved rule;
- percentage of model proposals accepted unchanged;
- average edits per rule;
- reviewer time saved versus baseline manual implementation.

### Maintenance

- percentage of amended clauses correctly linked to affected rules;
- affected-test recall;
- time to update an approved ruleset after source revision.

### Community

- external corpora/adapters contributed;
- organizations testing RuleWeaver;
- benchmark citations/reuse;
- independent integrations.
