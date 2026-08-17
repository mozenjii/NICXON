# 10 — Engineering Backlog

Legend:

- **P0** blocks the core architecture.
- **P1** required for first credible public release.
- **P2** useful after core semantics stabilize.
- **P3** expansion/research.

## Epic A — Repository foundation

- [ ] **P0** Bootstrap Python package.
- [ ] **P0** Add pytest.
- [ ] **P0** Add static type checking.
- [ ] **P0** Add formatting/linting.
- [ ] **P0** Add CI workflow.
- [ ] **P0** Define diagnostic object and code ranges.
- [ ] **P1** Add release/version tooling.
- [ ] **P1** Add JSON Schema generation/check.

## Epic B — Source model

- [ ] **P0** `SourceManifest`.
- [ ] **P0** `SourceDocument`.
- [ ] **P0** `SourceNode` hierarchy.
- [ ] **P0** `SourceSpan` selector model.
- [ ] **P0** source hashing.
- [ ] **P1** cross-reference object.
- [ ] **P1** version/effective metadata.
- [ ] **P1** source validation diagnostics.

## Epic C — Rule IR

- [ ] **P0** IR package envelope/versioning.
- [ ] **P0** stable ID conventions.
- [ ] **P0** value types.
- [ ] **P0** expression AST.
- [ ] **P0** variables.
- [ ] **P0** parameters.
- [ ] **P0** rules.
- [ ] **P0** effective periods.
- [ ] **P0** source provenance links.
- [ ] **P0** review status.
- [ ] **P1** definitions.
- [ ] **P1** simple exceptions/priority.
- [ ] **P1** ambiguity objects.
- [ ] **P1** human-judgment predicate representation.

## Epic D — Reference evaluator

- [ ] **P0** expression interpreter.
- [ ] **P0** three/four-state unknown semantics.
- [ ] **P0** parameter lookup by date.
- [ ] **P0** rule assignment/evaluation.
- [ ] **P0** deterministic execution trace.
- [ ] **P1** exception evaluation.
- [ ] **P1** entity context.
- [ ] **P2** performance/vectorization investigation.

## Epic E — Verification

- [ ] **P0** schema validator.
- [ ] **P0** type checker.
- [ ] **P0** reference resolver.
- [ ] **P0** duplicate ID diagnostics.
- [ ] **P0** dependency graph.
- [ ] **P0** cycle detection.
- [ ] **P1** temporal overlap/gap diagnostics.
- [ ] **P1** parameter availability diagnostics.
- [ ] **P1** exception priority diagnostics.
- [ ] **P2** basic contradiction checks.

## Epic F — Tests

- [ ] **P0** rule package test-case schema.
- [ ] **P0** test runner.
- [ ] **P0** human/source test provenance.
- [ ] **P1** threshold boundary generator.
- [ ] **P1** effective-date generator.
- [ ] **P1** exception generator.
- [ ] **P1** dependency-path generator.
- [ ] **P2** mutation testing.
- [ ] **P2** property-based test suite.

## Epic G — Initial fictional corpus

- [ ] **P0** write fictional benefit source in plain English.
- [ ] **P0** hand-author source structure.
- [ ] **P0** hand-author gold Rule IR.
- [ ] **P0** hand-author policy-intent tests.
- [ ] **P0** include dated threshold amendment.
- [ ] **P0** include exception and cross-reference.
- [ ] **P0** include one deliberate ambiguity example.

## Epic H — Source ingestion

- [ ] **P1** plain text importer.
- [ ] **P1** HTML importer.
- [ ] **P1** native PDF text importer.
- [ ] **P1** structure normalization.
- [ ] **P2** Akoma Ntoso importer.
- [ ] **P2** DOCX importer.
- [ ] **P3** OCR.

## Epic I — Model/compiler infrastructure

- [ ] **P1** provider-neutral model interface.
- [ ] **P1** structured-output abstraction.
- [ ] **P1** prompt asset registry.
- [ ] **P1** prompt version hashes.
- [ ] **P1** compiler run metadata/provenance.
- [ ] **P1** clause classifier.
- [ ] **P1** concept extractor.
- [ ] **P1** rule proposal compiler.
- [ ] **P1** reference linker.
- [ ] **P1** ambiguity detector.
- [ ] **P2** local-model backend.

## Epic J — Review workflow

- [ ] **P1** review state machine.
- [ ] **P1** decision/audit model.
- [ ] **P1** package approval policy.
- [ ] **P1** minimal review API.
- [ ] **P1** source/rule side-by-side UI.
- [ ] **P1** approve/edit/reject.
- [ ] **P1** ambiguity resolution UI.
- [ ] **P1** test approval UI.
- [ ] **P2** reviewer comments.
- [ ] **P2** multi-reviewer policy.

## Epic K — OpenFisca adapter

- [ ] **P1** feature capability report.
- [ ] **P1** entity mapping.
- [ ] **P1** variables mapping.
- [ ] **P1** parameters mapping.
- [ ] **P1** expression-to-formula generator.
- [ ] **P1** formula/date mapping.
- [ ] **P1** YAML test export.
- [ ] **P1** package scaffold output.
- [ ] **P1** target validation.
- [ ] **P1** differential test harness.

## Epic L — Amendment/change impact

- [ ] **P1** source snapshot versions.
- [ ] **P1** structural source diff.
- [ ] **P1** semantic object diff.
- [ ] **P1** mark affected rules stale.
- [ ] **P1** downstream dependency impact.
- [ ] **P1** affected-test calculation.
- [ ] **P2** reviewer change dashboard.

## Epic M — Benchmark

- [ ] **P1** choose first real corpus.
- [ ] **P1** licensing/reuse review.
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

- [ ] **P1** CLI.
- [ ] **P1** Docker image.
- [ ] **P1** example project.
- [ ] **P1** architecture docs kept current.
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
