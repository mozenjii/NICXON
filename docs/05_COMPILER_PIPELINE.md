# 05 — Compiler Pipeline

## Principle

The LLM should never be asked to perform the entire transformation in one opaque prompt.

Use staged compiler passes with narrow responsibilities, typed outputs, and deterministic validation between stages.

## Pipeline

```text
P0 ingest
P1 structure
P2 clause classification
P3 concept extraction
P4 rule proposal
P5 reference linking
P6 ambiguity analysis
P7 deterministic verification
P8 test generation
P9 human review
P10 approved package build
P11 adapter compilation
```

## P0 — Ingest

Input:

- file/URL/snapshot supplied by user or test fixture.

Output:

- source bytes/text;
- metadata;
- content hash;
- ingestion diagnostics.

MVP should prioritize clean HTML/text and native-text PDFs. OCR is not a prerequisite for compiler semantics.

## P1 — Source structure

Goal:

Represent the document independently of rule interpretation.

Extract/preserve:

- title;
- hierarchy;
- sections/subsections;
- numbered paragraphs;
- tables;
- footnotes/endnotes;
- links/cross-references;
- stable source node IDs.

If the source is Akoma Ntoso, preserve its identifiers rather than generating incompatible IDs unnecessarily.

## P2 — Clause classification

Classify source units into candidate categories:

- definition;
- parameter/value;
- rule/condition;
- exception;
- scope/jurisdiction;
- effective date;
- evidence/document requirement;
- example;
- non-normative explanation;
- cross-reference;
- non-computable/human judgment.

This can be LLM-assisted but should support multiple labels per clause.

## P3 — Concept extraction

Extract candidates:

- entities;
- variables;
- definitions;
- parameters;
- named program concepts;
- units;
- periods;
- referenced rules.

Before creating a new concept, attempt to link to an existing concept in the package.

## P4 — Rule proposal

Input:

- clause;
- surrounding source context;
- linked definitions;
- relevant concepts;
- allowed IR schema/features.

Output:

- one or more Rule IR proposals;
- source spans;
- assumptions;
- unsupported concepts;
- confidence metadata;
- diagnostics.

Prompts must explicitly allow the result `cannot_compile`.

## P5 — Reference linking

Resolve:

- “section 4.2”;
- “for purposes of paragraph (b)”;
- named definitions;
- variables/parameters;
- tables/schedules;
- external source references.

Use deterministic identifiers wherever the document structure allows it. LLM matching should propose links, then the resolver checks existence/type.

## P6 — Ambiguity analysis

Look specifically for:

- scope ambiguity;
- unclear attachment of exceptions;
- ambiguous conjunction/disjunction;
- undefined terms;
- competing definitions;
- cross-reference uncertainty;
- temporal uncertainty;
- implicit units;
- contradictions between sources;
- missing external knowledge.

The output should not be “confidence = 0.62.” It should state what is uncertain and what decision is required.

## P7 — Deterministic verification

Run:

- JSON/schema validation;
- type checking;
- reference resolution;
- duplicate ID detection;
- dependency-cycle checks;
- parameter availability checks;
- temporal overlap/gap diagnostics;
- unsupported operator checks;
- source provenance checks;
- ambiguity blocking checks.

No model is required for these passes.

## P8 — Test generation

Generate candidate tests using structural features of the rule.

### Threshold

For `x <= 32000` generate values around the boundary.

Example:

```text
31999.99
32000.00
32000.01
```

Use type-appropriate epsilon/step semantics rather than assuming integers.

### Effective date

Generate:

```text
day before
exact start date
day after
end boundary
```

### Exception

Generate:

- base condition true / exception false;
- base true / exception true;
- base false / exception true;
- missing exception inputs.

### Dependencies

Generate cases that exercise upstream values and downstream changes.

### Mutation testing later

Mutate operators/boundaries to determine whether the test suite would catch a plausible implementation error.

## P9 — Human review

A reviewer sees:

```text
SOURCE | STRUCTURED RULE | TESTS | DIAGNOSTICS | DEPENDENCIES
```

The reviewer can:

- edit the rule;
- approve;
- reject;
- mark ambiguous;
- attach a legal/policy note;
- add policy-intent tests;
- approve/reject generated tests;
- link additional source evidence.

## P10 — Package build

Only rules satisfying the configured approval policy enter an executable release package.

Build should fail on:

- blocking ambiguity;
- unresolved references;
- invalid temporal ranges;
- schema errors;
- missing required provenance;
- failed mandatory policy-intent tests.

## P11 — Adapter compilation

Adapters consume approved IR and produce target artifacts.

Adapter compilation must produce a capability report such as:

```text
supported: 23 rules
unsupported: 2 rules
lossy: 0 rules
```

A release should not silently omit unsupported rules.

## Prompt engineering rules

Prompts are versioned compiler assets.

Each prompt should define:

- task;
- permitted source context;
- target schema;
- allowed abstention outputs;
- forbidden assumptions;
- examples;
- diagnostic behavior.

Avoid one global “legal expert” system prompt as the core architecture.

## Retrieval policy

For long policies, retrieve structurally and semantically.

Prioritize:

1. current clause;
2. parent/neighbor clauses;
3. referenced definitions;
4. explicitly referenced sections;
5. source-global concept search;
6. external authoritative sources only when the compilation task declares them.

Never silently use general web knowledge to fill a missing policy fact in a reproducible compilation.

## Reproducibility

Each compiler run should record:

- compiler version/commit;
- source hashes;
- model identifier;
- model settings;
- prompt versions;
- retrieval context IDs/hashes;
- IR schema version;
- timestamp;
- output hashes.
