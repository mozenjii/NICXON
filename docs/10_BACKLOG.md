# 10 — Backlog

> **Status, 2026-08-20.** 83 of 134 items are done. `docs/01_PROJECT_STATUS.md` is the
> authority on what is built; this file is the plan. An item is ticked only when there is
> an implementation *and* a test — a backlog that overstates progress is worse than one
> nobody updated, because someone will trust it.
>
> Every P0 is done. The type checker was the last one: validators resolved references and
> detected cycles, but nothing checked that an expression's operand types could meet, so a
> comparison between a money value and a date passed validation. `RW2003`-`RW2008` now
> reject it.
>
> The most valuable P1 left is **Epic K's differential test harness** — the missing
> evidence for the OpenFisca adapter, see ADR-029. Everything else is breadth.

Legend:

- **P0** blocks the core architecture.
- **P1** required for first credible public release.
- **P2** useful after core semantics stabilize.
- **P3** expansion/research.

## Epic A — Repository foundation

- [x] **P0** Bootstrap Python package.
- [x] **P0** Add pytest.
- [x] **P0** Add static type checking.
- [x] **P0** Add formatting/linting.
- [x] **P0** Add CI workflow.
- [x] **P0** Define diagnostic object and code ranges.
- [ ] **P1** Add release/version tooling.
- [x] **P1** Add JSON Schema generation/check.

## Epic B — Source model

- [x] **P0** `SourceManifest`.
- [x] **P0** `SourceDocument`.
- [x] **P0** `SourceNode` hierarchy.
- [x] **P0** `SourceSpan` selector model.
- [x] **P0** source hashing.
- [ ] **P1** cross-reference object.
- [x] **P1** version/effective metadata.
- [x] **P1** source validation diagnostics.

## Epic C — Rule IR

- [x] **P0** IR package envelope/versioning.
- [x] **P0** stable ID conventions.
- [x] **P0** value types.
- [x] **P0** expression AST.
- [x] **P0** variables.
- [x] **P0** parameters.
- [x] **P0** rules.
- [x] **P0** effective periods.
- [x] **P0** source provenance links.
- [x] **P0** review status.
- [x] **P1** definitions.
- [x] **P1** simple exceptions/priority.
- [x] **P1** ambiguity objects.
- [ ] **P1** human-judgment predicate representation.

## Epic D — Reference evaluator

- [x] **P0** expression interpreter.
- [x] **P0** three/four-state unknown semantics.
- [x] **P0** parameter lookup by date.
- [x] **P0** rule assignment/evaluation.
- [x] **P0** deterministic execution trace.
- [x] **P1** exception evaluation.
- [x] **P1** entity context.
- [ ] **P2** performance/vectorization investigation.

## Epic E — Verification

- [x] **P0** schema validator.
- [x] **P0** type checker.
- [x] **P0** reference resolver.
- [x] **P0** duplicate ID diagnostics.
- [x] **P0** dependency graph.
- [x] **P0** cycle detection.
- [x] **P1** temporal overlap/gap diagnostics.
- [ ] **P1** parameter availability diagnostics.
- [x] **P1** exception priority diagnostics.
- [ ] **P2** basic contradiction checks.

## Epic F — Tests

- [x] **P0** rule package test-case schema.
- [x] **P0** test runner.
- [x] **P0** human/source test provenance.
- [x] **P1** threshold boundary generator.
- [x] **P1** effective-date generator.
- [ ] **P1** exception generator.
- [ ] **P1** dependency-path generator.
- [x] **P2** mutation testing.
- [ ] **P2** property-based test suite.

## Epic G — Initial fictional corpus

- [~] **P0** write fictional benefit source in plain English. **Superseded** — the corpus is real: 7 CFR 271.2, 273.9 and 273.10, verified against recorded digests. A fictional source cannot surface the cases that broke the parser.
- [x] **P0** hand-author source structure.
- [x] **P0** hand-author gold Rule IR.
- [x] **P0** hand-author policy-intent tests.
- [x] **P0** include dated threshold amendment.
- [x] **P0** include exception and cross-reference.
- [x] **P0** include one deliberate ambiguity example.

## Epic H — Source ingestion

- [ ] **P1** plain text importer.
- [ ] **P1** HTML importer.
- [ ] **P1** native PDF text importer.
- [ ] **P1** structure normalization.
- [ ] **P2** Akoma Ntoso importer.
- [ ] **P2** DOCX importer.
- [ ] **P3** OCR.

## Epic I — Model/compiler infrastructure

- [x] **P1** provider-neutral model interface.
- [x] **P1** structured-output abstraction.
- [x] **P1** prompt asset registry.
- [x] **P1** prompt version hashes.
- [x] **P1** compiler run metadata/provenance.
- [x] **P1** clause classifier.
- [ ] **P1** concept extractor.
- [x] **P1** rule proposal compiler.
- [ ] **P1** reference linker.
- [x] **P1** ambiguity detector.
- [ ] **P2** local-model backend.

## Epic J — Review workflow

- [x] **P1** review state machine.
- [x] **P1** decision/audit model.
- [x] **P1** package approval policy.
- [x] **P1** minimal review API.
- [x] **P1** source/rule side-by-side UI.
- [x] **P1** approve/edit/reject.
- [ ] **P1** ambiguity resolution UI.
- [ ] **P1** test approval UI.
- [ ] **P2** reviewer comments.
- [ ] **P2** multi-reviewer policy.

## Epic K — OpenFisca adapter

- [x] **P1** feature capability report.
- [x] **P1** entity mapping.
- [x] **P1** variables mapping.
- [x] **P1** parameters mapping.
- [x] **P1** expression-to-formula generator.
- [ ] **P1** formula/date mapping.
- [ ] **P1** YAML test export.
- [x] **P1** package scaffold output.
- [ ] **P1** target validation.
- [ ] **P1** differential test harness.

## Epic L — Amendment/change impact

- [x] **P1** source snapshot versions.
- [ ] **P1** structural source diff.
- [x] **P1** semantic object diff.
- [x] **P1** mark affected rules stale.
- [x] **P1** downstream dependency impact.
- [ ] **P1** affected-test calculation.
- [ ] **P2** reviewer change dashboard.

## Epic M — Benchmark

- [x] **P1** choose first real corpus.
- [x] **P1** licensing/reuse review.
- [ ] **P1** annotation guidelines.
- [ ] **P1** gold source structure.
- [ ] **P1** gold semantic labels.
- [ ] **P1** gold Rule IR.
- [ ] **P1** policy-intent scenarios.
- [ ] **P1** ambiguity set.
- [ ] **P1** metrics library.
- [ ] **P1** reproducible runner.
- [ ] **P2** leaderboard/reporting.

## Epic N — Developer experience

- [x] **P1** CLI.
- [ ] **P1** Docker image.
- [x] **P1** example project.
- [x] **P1** architecture docs kept current.
- [ ] **P2** FastAPI service.
- [ ] **P2** GitHub Action.
- [ ] **P2** plugin SDK.

## Epic O — Later adapters/research

- [ ] **P3** LegalRuleML export.
- [ ] **P3** Catala export.
- [ ] **P3** W3C PROV export.
- [ ] **P3** broader temporal logic.
- [ ] **P3** richer defeasible semantics.
- [ ] **P3** formal verification experiments.
- [ ] **P3** LSP/editor tooling.

## First 20 implementation tickets

If starting today, create these issues in this order:

1. Bootstrap package + CI.
2. Define diagnostics API.
3. Define source manifest/node/span types.
4. Define IR package/version envelope.
5. Define value types and expression AST.
6. Define variable/parameter types.
7. Define basic rule and effective period.
8. Implement schema serialization/golden fixture.
9. Implement expression evaluator.
10. Implement parameter lookup by date.
11. Implement rule evaluator + trace.
12. Write fictional policy source.
13. Hand-author 10+ gold rules.
14. Add human policy-intent tests.
15. Implement reference resolver/type checker.
16. Implement dependency graph/cycle checks.
17. Implement boundary/date test generation.
18. Plant semantic mutations and measure test detection.
19. Implement text/HTML source ingestion.
20. Only then implement the first LLM clause/rule compiler pass.
