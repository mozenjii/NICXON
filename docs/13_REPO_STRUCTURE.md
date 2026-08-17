# 13 — Proposed Repository Structure

This is the target structure, not the current implemented state.

```text
ruleweaver/
├── README.md
├── CLAUDE.md
├── LICENSE
├── CONTRIBUTING.md
├── CODE_OF_CONDUCT.md
├── SECURITY.md
├── pyproject.toml
├── Makefile
├── .github/
│   ├── workflows/
│   └── ISSUE_TEMPLATE/
│
├── docs/
│   ├── 00_PROJECT_BRIEF.md
│   ├── 01_PROJECT_STATUS.md
│   ├── 02_PRODUCT_SPEC.md
│   ├── 03_ARCHITECTURE.md
│   ├── 04_RULE_IR_SPEC.md
│   ├── 05_COMPILER_PIPELINE.md
│   ├── 06_VERIFICATION_SAFETY.md
│   ├── 07_DATA_BENCHMARK_EVAL.md
│   ├── 08_ADAPTERS_INTEROP.md
│   ├── 09_IMPLEMENTATION_ROADMAP.md
│   ├── 10_BACKLOG.md
│   ├── 11_DECISIONS.md
│   ├── 12_RESEARCH_REFERENCES.md
│   ├── 13_REPO_STRUCTURE.md
│   └── 14_GLOSSARY.md
│
├── src/ruleweaver/
│   ├── __init__.py
│   ├── diagnostics/
│   ├── source/
│   │   ├── manifest.py
│   │   ├── document.py
│   │   ├── node.py
│   │   ├── span.py
│   │   ├── references.py
│   │   └── versions.py
│   ├── ir/
│   │   ├── package.py
│   │   ├── values.py
│   │   ├── entities.py
│   │   ├── expressions.py
│   │   ├── variables.py
│   │   ├── parameters.py
│   │   ├── rules.py
│   │   ├── temporal.py
│   │   ├── definitions.py
│   │   ├── ambiguity.py
│   │   └── provenance.py
│   ├── runtime/
│   │   ├── evaluator.py
│   │   ├── context.py
│   │   ├── parameter_lookup.py
│   │   └── trace.py
│   ├── verify/
│   │   ├── schema.py
│   │   ├── types.py
│   │   ├── references.py
│   │   ├── dependencies.py
│   │   ├── temporal.py
│   │   └── provenance.py
│   ├── testgen/
│   │   ├── boundaries.py
│   │   ├── dates.py
│   │   ├── exceptions.py
│   │   └── mutations.py
│   ├── ingest/
│   │   ├── text.py
│   │   ├── html.py
│   │   ├── pdf.py
│   │   └── akoma_ntoso.py
│   ├── compiler/
│   │   ├── pipeline.py
│   │   ├── classify.py
│   │   ├── concepts.py
│   │   ├── rules.py
│   │   ├── link.py
│   │   └── ambiguity.py
│   ├── models/
│   │   ├── protocol.py
│   │   ├── registry.py
│   │   └── prompts/
│   ├── review/
│   │   ├── states.py
│   │   ├── decisions.py
│   │   └── approvals.py
│   ├── diff/
│   │   ├── source.py
│   │   ├── semantic.py
│   │   └── impact.py
│   └── adapters/
│       ├── protocol.py
│       ├── openfisca/
│       ├── legalruleml/
│       └── catala/
│
├── schemas/
│   └── ruleweaver-0.1.schema.json
│
├── examples/
│   ├── fictional-benefit/
│   └── real-corpus-example/
│
├── benchmark/
│   ├── manifests/
│   ├── annotations/
│   ├── metrics/
│   └── reports/
│
├── tests/
│   ├── unit/
│   ├── golden/
│   ├── compiler/
│   ├── runtime/
│   ├── verification/
│   └── adapters/
│
├── cli/
├── api/
└── web/
```

## Ownership principles

### `source/`

Facts about the source document only.

### `ir/`

Canonical semantics. No model-provider or target-runtime imports.

### `runtime/`

Reference semantics for approved IR.

### `verify/`

Pure/deterministic semantic checks where possible.

### `compiler/`

Semantic proposal pipeline. May depend on model interfaces, source, and IR.

### `models/`

Provider integrations only. No business semantics hidden here.

### `adapters/`

One-way translation from canonical approved IR to external formats/runtimes.

### `review/`

Approval/audit state independent of web framework.

### `web/`

Presentation layer only. It must not become the only location where review semantics exist.

## File-size discipline

If a module begins owning parsing + semantic logic + persistence + API behavior, split it.

Compiler work is context-heavy. Small modules with explicit typed contracts will make human and AI-agent contributions safer.
