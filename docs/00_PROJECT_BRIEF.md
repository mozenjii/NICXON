# 00 — Project Brief

## Problem

Legislation, regulations, program manuals, circulars, and administrative policies are normally published for human readers. Software systems that implement those rules require a second representation: variables, parameters, types, formulas, conditions, exceptions, dates, dependencies, and tests.

That translation is usually manual. Different agencies, vendors, NGOs, and product teams repeatedly interpret the same rule. This causes duplication, update lag, inconsistent interpretations, weak provenance, and difficult audits.

## RuleWeaver's job

RuleWeaver will help experts **compile** natural-language rules into structured, executable artifacts without pretending that an LLM is the legal authority.

The system should make every semantic transformation inspectable:

```text
source clause
  → extracted concept
  → proposed rule
  → diagnostics
  → generated tests
  → human decision
  → approved executable artifact
```

## Why LLMs are useful

LLMs are useful in the semantic gap between prose and structure:

- identifying definitions and references;
- decomposing conditions and exceptions;
- mapping natural-language thresholds to typed comparisons;
- identifying candidate parameters;
- detecting potentially relevant cross-references;
- proposing tests from examples and boundaries;
- summarizing ambiguities for reviewers.

LLMs are not used for deterministic evaluation of an approved ruleset.

## Initial users

### Primary

- rules-as-code engineers;
- government digital-service teams;
- public-benefits implementation teams;
- policy analysts working with computable programs;
- civic-tech organizations;
- legal/technical teams maintaining benefits calculators.

### Secondary

- researchers in computational law;
- compliance technology teams;
- tax/benefit simulation developers;
- auditors and implementation reviewers.

## Initial domain

v0.1 is intentionally focused on rules with objectively computable semantics:

- tax rules;
- public-benefit eligibility rules;
- public-benefit amount calculations;
- thresholds;
- temporal parameters;
- household/person/entity relationships;
- explicit exceptions.

## Why not all law

Many legal concepts are intentionally open-textured or require fact-finding, discretion, precedent, or institutional judgment. RuleWeaver should not make them look more deterministic than they are.

Subjective concepts can eventually be represented as unresolved predicates or human-evaluation requirements, but they are not a v0.1 implementation target.

## Core value proposition

### Today

```text
policy text → manual interpretation → manual code → manual tests
```

### RuleWeaver

```text
policy text
  → machine-assisted structured proposal
  → source-linked review
  → deterministic verification
  → generated + human policy-intent tests
  → executable adapter
  → version/change impact analysis
```

## Distinguishing features

1. Compiler architecture rather than chatbot architecture.
2. Canonical, provider-neutral intermediate representation.
3. Provenance on every material semantic object.
4. First-class ambiguity and abstention.
5. Generated boundary/date/exception tests.
6. Human approval gate.
7. Deterministic execution.
8. Impact analysis when legislation changes.
9. Multiple target runtimes rather than one vendor lock-in.
10. Public benchmark as a first-class project asset.

## Six-month ambition

By six months, the project should have:

- a stable v0.x Rule IR;
- one polished tax/benefit corpus;
- an evaluator and verifier;
- source-linked LLM compilation;
- human review workflow;
- OpenFisca export for a supported subset;
- amendment impact analysis;
- reproducible benchmark results;
- external users/contributors testing the system on real policy.

## Long-term ambition

RuleWeaver could become shared infrastructure analogous to a compiler toolchain:

- canonical IR;
- parser/compiler passes;
- diagnostics;
- test generation;
- provenance;
- target adapters;
- benchmark suite;
- language/server tooling for legal-rule implementations.

The project succeeds if other systems use its artifacts and interfaces even when they do not use its UI.
