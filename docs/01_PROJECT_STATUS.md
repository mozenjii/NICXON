# 01 — Project Status

**Status date:** 2026-08-17  
**Phase:** v0.1 deterministic core built — M0 closed, M1 validators complete

> **2026-08-17 review.** The spec pack was reviewed against verified external research.
> Architecture held; scope and three assumptions did not. See ADR-017 to ADR-022 in
> `11_DECISIONS.md`. Material changes:
>
> - **v0.1 rescoped** to a deterministic core (vocabulary + hand-encoded fixture + typed
>   IR + evaluator + validators + mutation harness). The former ten-point definition is
>   now v1.0.
> - **M0 was not closable as written** — its exit criteria depended on backlog items
>   scheduled after it. Resolved by ADR-017.
> - **Exception priority and temporal semantics are not open questions.** Worked answers
>   exist (prioritised defaults; multi-axis validity). Adopt, do not re-derive — ADR-020.
> - **Adapter plan reduced.** OpenFisca export is code generation, not serialization.
>   Catala and LegalRuleML are design references only — ADR-019.
> - **The human approval gate needs evidence it works.** Independent expert encoders agree
>   ~0% without a shared vocabulary, and automation bias degrades even expert review —
>   ADR-018, ADR-021.
> - **Deterministic runtime is now a legal position**, not only an engineering one —
>   ADR-022.

This file must stay brutally accurate. Do not mark an item complete because a placeholder, interface, or demo exists.

## Completed decisions

### Product

- [x] RuleWeaver chosen as the project.
- [x] Primary goal defined: compile natural-language rules into source-linked, testable, executable rule representations.
- [x] Primary public-interest wedge: tax and public-benefit rules.
- [x] Generic legal chatbot explicitly rejected.
- [x] Autonomous legal decision-making explicitly rejected.

### Architecture

- [x] Standards-first architecture approved.
- [x] Canonical RuleWeaver IR approved as the center of the system.
- [x] LLM used for semantic proposals, not final runtime evaluation.
- [x] Human approval required before executable use.
- [x] Ambiguity/abstention must be first-class.
- [x] Provenance must be first-class.
- [x] Tests are part of policy intent, not only code QA.
- [x] OpenFisca selected as first executable target.
- [x] Catala selected as a later high-assurance target.
- [x] LegalRuleML selected as an interchange target.
- [x] Akoma Ntoso selected as a legal-document interoperability target.
- [x] W3C PROV chosen as provenance-model inspiration/interop.

### Research completed enough to begin

- [x] OpenFisca architecture, variables, parameters, formulas, and YAML testing reviewed.
- [x] OpenFisca guidance to start with simple authoritative rules and reliable interpretations reviewed.
- [x] Catala's literate-programming and high-assurance approach reviewed.
- [x] Akoma Ntoso and LegalRuleML standards reviewed at architectural level.
- [x] W3C PROV reviewed at architectural level.
- [x] Georgetown/Beeck Center LLM-to-rules experiments reviewed.
- [x] Better Rules methodology and policy-intent test concept reviewed.
- [x] 2026 PROLEG legislation-to-executable-rules work reviewed.

## Implementation state

Checked items are built and covered by tests. Everything unchecked is genuinely absent.

### Foundation

- [x] Python package bootstrapped.
- [x] CI configured.
- [ ] code quality tooling configured.
- [x] diagnostics framework defined.
- [x] serialization/version strategy implemented.

### Source model

- [ ] source document object.
- [ ] hierarchy/section model.
- [x] source spans.
- [x] source hashes.
- [ ] cross-reference model.
- [x] effective-version model.

### Rule IR

- [x] production schema.
- [x] expression system.
- [x] entities and variables.
- [x] parameter model.
- [x] temporal semantics.
- [x] exceptions/priority semantics.
- [x] ambiguity representation.
- [x] interpretation/review state.
- [ ] provenance relation model.

### Runtime and verification

- [x] evaluator.
- [ ] type checker.
- [x] reference resolver.
- [x] dependency graph.
- [x] cycle detection.
- [x] temporal validator.
- [ ] contradiction diagnostics.
- [ ] completeness diagnostics.
- [x] execution trace.

### Test generation

- [x] threshold boundary generator.
- [x] date-transition generator.
- [ ] exception generator.
- [ ] combinatorial case generator.
- [ ] property-based test framework.
- [x] approved human test fixture format.

### Ingestion/compiler

- [ ] plain-text/HTML ingestion.
- [ ] PDF ingestion.
- [ ] Akoma Ntoso ingestion.
- [ ] clause segmentation.
- [ ] definition extraction.
- [ ] parameter extraction.
- [ ] rule extraction.
- [ ] cross-reference linking.
- [ ] ambiguity proposal.
- [ ] prompt/version registry.
- [x] provider-neutral model interface.

### Review

- [x] review decision model.
- [x] approval workflow.
- [ ] source/rule side-by-side UI.
- [ ] edit/reject/approve UX.
- [x] audit log.

### Adapters

- [ ] OpenFisca mapping specification validated with examples.
- [ ] OpenFisca code generator.
- [ ] OpenFisca test exporter.
- [ ] LegalRuleML export.
- [ ] Catala export.

### Version change analysis

- [x] source version differ.
- [x] semantic rule differ.
- [x] downstream dependency impact analysis.
- [ ] affected test analysis.

### Benchmark

- [ ] corpus selected.
- [x] source licensing reviewed.
- [ ] annotation schema.
- [ ] gold rules.
- [ ] gold source links.
- [ ] gold tests.
- [ ] metrics implementation.
- [ ] reproducible benchmark runner.

## Immediate next milestone

**M0 — Executable IR without LLMs.**

Before building the AI compiler, create a tiny fictional benefit policy by hand and prove that RuleWeaver can represent, validate, execute, trace, and test it.

Exit criteria:

- at least 10 hand-authored rules;
- parameters that change by date;
- at least one exception;
- at least one dependency chain;
- source spans attached to every rule;
- deterministic evaluation;
- generated boundary tests;
- explicit `UNKNOWN` behavior;
- execution trace explaining which rule/parameter caused the result.

## Health indicators

Keep these up to date once implementation starts:

| Indicator | Current |
|---|---|
| Core package exists | Yes — `src/ruleweaver/{ir,runtime}` |
| IR schema version | 0.1.0 |
| Golden policy corpora | 1 (SNAP, 15 rules from 7 CFR 273.9 and 273.10) |
| Deterministic rule features implemented | 12 expression nodes, exceptions, overrides, 4-state values, trace |
| Tests | 145 passing (`pytest`) |
| Mutation score | **22/22 caught (100%)** |
| Validators implemented | 16, stable `RWxxxx` codes |
| Test generators | boundary + date transition |
| Amendment impact | semantic diff + dependency closure + outcome comparison |
| CLI | `validate`, `evaluate`, `boundaries`, `diff`, `schema` |
| Model interface | Provider-neutral; Claude + GPT adapters; injection guard |
| Review gate | Append-only log, derived status, seeded-error catch rate |
| LLM compiler passes implemented | 0 — the interface exists; no extraction pass yet |
| Approved adapter targets | 0 built, 1 planned (OpenFisca, as a code generator) |
| External contributors | 0 |
| Public benchmark release | No |
| First external pilot | No |

### M0 exit criteria

| Criterion | State |
|---|---|
| At least 10 hand-authored rules | **Met** — 15 |
| Parameters that change by date | **Met** — dated `ParameterValue` intervals |
| At least one exception | **Met** — 2, both substitutive |
| At least one dependency chain | **Met** — gross income → deductions → net income → eligibility |
| Source spans attached to every rule | **Met** — all 15 cite a clause |
| Deterministic evaluation | **Met** — fixed-point evaluator, no model in the path |
| Generated boundary tests | **Met** — generator probes every threshold at x-1/x/x+1 |
| Explicit `UNKNOWN` behaviour | **Met** — propagates to the decision, raises on `__bool__` |
| Execution trace explaining the result | **Met** — records rule, target, scope, and base/exception/override |

**M0 is closed.** All nine criteria met.

The mutation harness is what makes that claim worth anything. Its first run scored 44%,
and each of the ten survivors was a real hole: the suite could not detect a deleted
"notwithstanding" override, could not distinguish conjunction from disjunction in the
final decision, and never exercised four floor guards. Those are now closed and the score
is 17/17.

### Next milestone — M1: validators

Deterministic checks that reject a bad package before it can be evaluated:
reference resolution, cycle detection, temporal consistency, unreachable-rule detection
(the mutation harness already surfaced one unconditionally overridden rule), and
provenance completeness.

## Known risks already identified

1. Treating ambiguous law as deterministic logic.
2. Generating plausible but wrong cross-references.
3. Losing the distinction between source text and an interpretation.
4. Under-specifying temporal semantics.
5. Building an IR around one country's benefit vocabulary.
6. Overfitting to OpenFisca and losing target neutrality.
7. Generating tests that simply mirror the generated rule instead of independent policy intent.
8. Hiding errors behind model confidence.
9. Expanding to high-discretion legal domains too early.
10. Spending too much time on UI before compiler semantics are stable.
