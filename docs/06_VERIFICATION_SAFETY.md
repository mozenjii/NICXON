# 06 — Verification, Safety, and Trust Model

## Threat model

RuleWeaver can fail in ways that look convincing. That is more dangerous than a visible crash.

Primary failure classes:

1. wrong interpretation;
2. missed exception;
3. wrong scope;
4. wrong definition;
5. wrong date/effective version;
6. wrong threshold/operator;
7. missing external reference;
8. fabricated source link;
9. adapter semantic drift;
10. stale rules after amendment;
11. prompt injection from source text;
12. user treating a draft as authoritative.

## Safety principle

RuleWeaver produces **reviewable interpretations**, not law.

The authoritative source remains the authoritative source.

## Human-in-the-loop policy

### Required

Human review is required before a proposed semantic rule becomes part of an approved executable package.

### Model confidence

Model confidence may help prioritize review. It may not bypass review.

### Reviewer roles

Long-term deployments may support:

- compiler engineer;
- policy reviewer;
- legal reviewer;
- approver/release manager.

v0.1 can implement a simpler single-reviewer state while preserving room for role policies.

## Abstention states

Compiler passes must be allowed to produce:

- `UNKNOWN` — required information is not available;
- `AMBIGUOUS` — multiple plausible interpretations;
- `UNSUPPORTED` — the IR/runtime cannot faithfully represent the source concept;
- `NEEDS_EXTERNAL_SOURCE` — referenced information is absent;
- `HUMAN_JUDGMENT_REQUIRED` — rule depends on discretion or contextual assessment;
- `INVALID` — structured proposal fails deterministic checks.

These are successful outputs when appropriate, not failures to be suppressed.

## Provenance requirements

For each approved rule, the system must answer:

1. Which source document/version supports it?
2. Which exact source span(s) support it?
3. Which compiler/model run created the proposal?
4. What deterministic validations ran?
5. Which reviewer changed/approved it?
6. Which tests were approved with it?
7. Which adapter/compiler generated a target artifact?

W3C PROV provides useful interoperability concepts:

- Entity;
- Activity;
- Agent;
- `wasDerivedFrom`;
- `wasGeneratedBy`;
- `used`;
- `wasAttributedTo`.

RuleWeaver does not need an RDF store in v0.1. It should preserve equivalent relations in its own typed data and export PROV later if useful.

## Source integrity

Each source snapshot should record:

- source ID;
- origin;
- retrieval/import timestamp;
- cryptographic hash;
- declared jurisdiction;
- effective/publication metadata if known;
- license/reuse notes where applicable.

Do not allow a silently changed remote URL to rewrite history.

## Deterministic validator checklist

An approved package build must verify:

- valid schema;
- all IDs unique;
- references resolve;
- types match operators;
- parameters have compatible units/types;
- rule effective periods are valid;
- required parameter values exist for test periods;
- exception priorities are resolvable;
- no prohibited cycles exist;
- blocking ambiguities are resolved;
- required provenance exists;
- mandatory tests pass.

## Testing safety

Generated tests must be labeled with origin.

Why: a model can generate a rule and then generate tests that merely restate the same mistake. Passing those tests proves little.

Maintain separate metadata:

```text
origin = human_policy_intent
origin = source_example
origin = generated_boundary
origin = generated_mutation
origin = adapter_differential
```

High-confidence releases should rely on human/source examples plus generated adversarial tests.

## Differential verification

When an adapter exists:

```text
RuleWeaver reference evaluator
        vs
Target runtime output
```

Run identical test cases. Any disagreement is an adapter/compiler defect or unsupported semantic difference until explained.

## Amendment safety

When a source changes:

- do not automatically overwrite approved rules;
- create a new source version;
- compute source diff;
- mark potentially affected rules stale;
- identify dependency impact;
- rerun/generate affected tests;
- require review before publishing a new approved rule package.

## Prompt-injection safety

Policy documents are untrusted input.

Compiler prompts must frame document text as quoted/data content. Instructions appearing inside source documents must not be treated as instructions to the model unless they are part of the policy semantics being analyzed.

Never expose credentials/tools capable of destructive actions to a document-processing model without strict tool policies.

## Code generation safety

Do not directly execute model-generated Python/Catala/OpenFisca code.

Preferred flow:

```text
LLM → RuleWeaver IR → deterministic adapter → target code
```

This dramatically reduces arbitrary-code risk and makes semantics auditable.

## User-facing disclaimers

The product should clearly state:

- source authority lies with the referenced official materials;
- RuleWeaver outputs are implementations/interpretations requiring review;
- use in benefits/tax decisions requires appropriate governance and validation;
- unresolved ambiguity is visible and intentional.

Do not add alarming boilerplate everywhere. Put warnings at consequential transitions such as approval/export/use.
