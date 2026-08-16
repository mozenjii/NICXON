# 03 — Architecture

## Architectural style

RuleWeaver is a **multi-pass compiler with human review gates**.

It should feel more like a compiler toolchain than a conversational assistant.

## High-level architecture

```text
┌──────────────────────────────────────────────────────────────┐
│                   AUTHORITATIVE SOURCES                      │
│ HTML · text · PDF · DOCX · XML · Akoma Ntoso               │
└────────────────────────────┬─────────────────────────────────┘
                             │
                             ▼
                    Source normalization
                             │
                             ▼
                  Canonical Source Document
                             │
          ┌──────────────────┴───────────────────┐
          ▼                                      ▼
 deterministic structure                semantic LLM passes
 refs / hierarchy / hashes              classify / extract / link
          │                                      │
          └──────────────────┬───────────────────┘
                             ▼
                       RuleWeaver IR
                             │
         ┌───────────────────┼────────────────────┐
         ▼                   ▼                    ▼
     type checker       reference resolver    provenance
         │                   │                    │
         └───────────────────┼────────────────────┘
                             ▼
                    semantic verification
                             │
                             ▼
                       test generation
                             │
                             ▼
                     human review gate
                             │
                             ▼
                     approved rule package
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
        native evaluator   OpenFisca      other adapters
                             │
                             ▼
                 deterministic simulation
```

## Key subsystem boundaries

### 1. Source layer

Responsibilities:

- preserve authoritative text;
- identify source document/version;
- represent hierarchy;
- give stable identifiers to source nodes/spans;
- record hashes and retrieval metadata;
- represent cross-document/source references when known.

Must not contain interpreted rule logic.

### 2. Semantic compiler

Responsibilities:

- identify normative/computable clauses;
- extract candidate definitions/parameters/rules;
- propose typed expressions;
- propose cross-reference resolution;
- detect candidate ambiguities;
- attach provenance evidence.

The compiler produces **proposals plus diagnostics**, not approved law.

### 3. Canonical RuleWeaver IR

The IR is the central public contract.

Properties:

- typed;
- serializable;
- versioned;
- target-neutral;
- provenance-aware;
- temporal;
- explicit about unknown/ambiguous states;
- deterministic when approved and executable.

### 4. Verification layer

Deterministic passes:

- schema validation;
- type checking;
- unresolved identifier detection;
- source-reference validation;
- temporal consistency;
- dependency/cycle analysis;
- exception/priority validation;
- unsupported-feature diagnostics;
- contradiction warnings where mechanically detectable.

### 5. Test layer

Two test categories must remain distinguishable.

**Policy-intent tests**

Human-authored/approved examples representing intended outcomes.

**Generated diagnostic tests**

Compiler-generated boundary, date, exception, and mutation cases.

Generated tests are useful evidence but cannot define policy intent by themselves.

### 6. Review layer

Review UI/workflow must show:

- exact source text;
- source hierarchy/location;
- proposed structured rule;
- compiler diagnostics;
- ambiguity alternatives;
- generated tests;
- dependency impact;
- change history.

Reviewer actions:

- approve;
- edit;
- reject;
- mark ambiguous;
- request source clarification;
- mark non-computable/human judgment required.

### 7. Runtime

A small deterministic RuleWeaver evaluator should exist even if adapters are available.

Reasons:

- makes IR independently testable;
- gives a reference semantic implementation;
- enables differential tests against adapters;
- avoids making OpenFisca the de facto IR.

### 8. Adapter layer

Adapters translate only approved/supported IR features.

If a target cannot represent a RuleWeaver feature faithfully, the adapter must fail or emit an explicit lossy/unsupported diagnostic. It must never silently approximate semantics.

## Compiler pass model

Recommended pattern:

```text
SourceDocument
  → ClauseCandidates
  → Concepts
  → RuleProposals
  → LinkedRules
  → VerifiedRules
  → ReviewedRules
  → ApprovedRulePackage
```

Every pass should return:

```text
output
+ diagnostics[]
+ provenance events[]
+ pass metadata
```

## Diagnostic model

Every diagnostic should include:

- stable code (`RWxxxx`);
- severity (`info`, `warning`, `error`, `blocking`);
- message;
- source location if applicable;
- IR object IDs if applicable;
- machine-readable details;
- suggested reviewer action where appropriate.

Example diagnostic families:

```text
RW1xxx source/ingestion
RW2xxx schema/type
RW3xxx references/dependencies
RW4xxx temporal
RW5xxx ambiguity/interpretation
RW6xxx tests
RW7xxx provenance
RW8xxx adapters
RW9xxx internal/compiler
```

## Storage

### MVP

- filesystem artifacts for source snapshots and rule packages;
- SQLite for review state/metadata if a DB is needed;
- content-addressed hashes for reproducibility.

### Later

- PostgreSQL for multi-user deployments;
- object storage for source artifacts;
- immutable audit/event log;
- optional graph index for large rule dependencies.

Do not start with a graph database unless actual scale demonstrates the need.

## Model-provider interface

The semantic compiler must use an interface conceptually like:

```text
structured_generate(task, context, schema, settings) -> typed proposal + run metadata
```

Required run metadata:

- provider;
- model identifier;
- model/version if known;
- prompt/template version;
- decoding settings;
- request timestamp;
- input source hashes;
- output hash;
- tool/retrieval calls used.

## Security boundary

Treat source documents and policies as untrusted input.

LLM prompts must not allow source documents to override system/compiler instructions. Document text is data, not instruction.

Never automatically execute code emitted by a model.

## Architecture rule

**No target adapter, UI convenience, or model capability is allowed to redefine the meaning of the canonical IR.**
