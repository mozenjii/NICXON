# 09 — Implementation Roadmap

This roadmap is ordered to reduce architectural risk. Do not start with the flashy LLM/UI pieces.

## Phase 0 — Repository and semantic foundations

### Goal

Prove the project can represent and deterministically execute rules before introducing model uncertainty.

### Build

- Python package skeleton;
- CI/tests/lint/type-checking;
- diagnostic types;
- source span/source manifest types;
- initial Rule IR Pydantic models;
- JSON Schema export;
- deterministic evaluator;
- execution trace;
- minimal fictional policy fixture.

### Exit criteria

A hand-authored fictional policy with:

- 10+ rules;
- one entity relationship;
- threshold parameter;
- dated parameter change;
- exception;
- computed amount;
- missing-input/unknown behavior;
- complete provenance;
- passing gold tests.

## Phase 1 — Verification and test generation

### Build

- type checker;
- reference resolver;
- dependency graph;
- cycle detection;
- temporal validator;
- parameter availability checks;
- boundary test generator;
- date test generator;
- exception test generator;
- mutation framework.

### Exit criteria

Deliberately broken rules produce stable diagnostics, and generated tests catch a set of planted semantic mutations.

## Phase 2 — Source ingestion

### Build

- text/HTML source ingestion;
- native PDF text ingestion;
- hierarchical source document;
- source hashes;
- citation/source-span UI primitives;
- Akoma Ntoso importer prototype.

### Exit criteria

One real policy source is represented reproducibly with stable source IDs.

## Phase 3 — LLM semantic compiler

### Build

- provider-neutral model interface;
- prompt registry/versioning;
- clause classifier;
- definition/parameter extraction;
- rule proposal pass;
- cross-reference proposal pass;
- ambiguity proposal pass;
- compiler provenance records.

### Exit criteria

The model can compile the selected corpus into schema-valid proposals with measurable source alignment and abstention behavior.

## Phase 4 — Review workflow

### Build

- proposal/review/approval state machine;
- side-by-side source/rule review UI;
- edit/reject/approve;
- ambiguity resolution;
- test review;
- audit history.

### Exit criteria

A domain-aware reviewer can create an approved rule package without manually editing raw JSON.

## Phase 5 — OpenFisca adapter

### Build

- capability analyzer;
- entity/variable/parameter mappings;
- formula generation from supported expression AST;
- YAML test export;
- package/template generation;
- differential test runner.

### Exit criteria

Approved rules run equivalently in RuleWeaver and OpenFisca for the supported fixture corpus.

## Phase 6 — Policy amendment / semantic diff

### Build

- source version diff;
- changed source node detection;
- rule staleness propagation;
- parameter change detection;
- dependency impact;
- affected-test set;
- review queue for amended rules.

### Exit criteria

Given v1/v2 of the example policy, RuleWeaver accurately identifies which approved rules/tests need review.

## Phase 7 — Benchmark release

### Build

- real corpus annotations;
- metric library;
- reproducible benchmark runner;
- baseline models;
- per-task reports;
- public dataset manifest.

### Exit criteria

Anyone can reproduce a documented baseline and inspect per-example errors.

## Phase 8 — Developer experience

### Build

- CLI;
- API;
- Docker;
- docs site;
- examples;
- GitHub workflows;
- plugin/adapter documentation.

Possible CLI:

```text
ruleweaver ingest source.pdf
ruleweaver compile policy.rws
ruleweaver verify package.json
ruleweaver test package.json
ruleweaver review serve ./workspace
ruleweaver diff old/ new/
ruleweaver export openfisca package.json
ruleweaver bench run benchmark.yaml
```

## Phase 9 — Research hardening

Investigate:

- ambiguity benchmark;
- formal verification possibilities;
- LegalRuleML mapping;
- Catala mapping;
- structured decoding/model comparisons;
- active learning from reviewer edits;
- semantic mutation testing;
- multi-jurisdiction portability.

## Milestone names

### M0 — Rules can execute

No LLM required.

### M1 — Rules can be verified

Compiler semantics have strong deterministic checks.

### M2 — Sources can be compiled

LLM proposals exist with provenance.

### M3 — Humans can approve

Review workflow is usable.

### M4 — Rules can leave RuleWeaver

OpenFisca adapter validated.

### M5 — Changes can be maintained

Amendment impact works.

### M6 — Claims can be measured

Public benchmark exists.

## What to postpone deliberately

Until after M4/M5, avoid:

- many model providers;
- complex permissions/RBAC;
- Kubernetes;
- graph databases;
- multi-tenant SaaS architecture;
- generalized legal reasoning;
- dozens of adapters;
- polished public marketing site;
- training/fine-tuning models.
