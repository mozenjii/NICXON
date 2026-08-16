# 12 — Research and Reference Map

**Research snapshot:** 2026-08-16

This file contains the external foundations that informed the architecture. It is not a substitute for reading the specifications when implementing adapters or standards support.

## 1. OpenFisca

### Why it matters

OpenFisca is an open-source rules-as-code engine for tax and benefit systems. Its architecture models jurisdictions with entities, variables, parameters, formulas, periods, tests, and APIs.

Architectural lessons used by RuleWeaver:

- separate legislation parameters from formulas;
- parameters change over time;
- formulas depend on variables/parameters;
- tests are core to rule implementation;
- start from authoritative rules and treat coding as interpretation;
- boundary values deserve explicit tests.

### Sources

- OpenFisca documentation: https://openfisca.org/doc/
- From law to code: https://openfisca.org/doc/coding-the-legislation/index.html
- Basic formula + tests: https://openfisca.org/doc/coding-the-legislation/10_basic_example.html
- Parameters: https://openfisca.org/doc/key-concepts/parameters.html
- YAML tests: https://openfisca.org/doc/coding-the-legislation/writing_yaml_tests.html
- Architecture: https://openfisca.org/doc/architecture.html
- Getting started / reliable interpretation guidance: https://openfisca.org/doc/training/getting-started.html

## 2. Catala

### Why it matters

Catala is a domain-specific language for high-assurance implementations of tax/social-benefit legislation. It uses literate programming so legal specification and executable code stay close together.

Architectural lessons:

- source-to-code correspondence is a maintenance feature, not cosmetic metadata;
- high-stakes legal automation should be narrow and cautious;
- dependency/exception semantics deserve first-class tooling;
- executable law benefits from specialized language/tooling rather than free-form code generation.

### Sources

- Catala book: https://book.catala-lang.org/
- Basic blocks/law-code relationship: https://book.catala-lang.org/en/2-1-basic-blocks.html
- Literate programming: https://book.catala-lang.org/en/5-1-literate-programming.html
- Compiler reference: https://assets.catala-lang.org/catala.html

## 3. Akoma Ntoso

### Why it matters

Akoma Ntoso is an OASIS standard for legislative, parliamentary, and judicial document structure, interchange, and metadata.

RuleWeaver use:

- structured input;
- stable legal-document IDs;
- hierarchy/reference preservation;
- future annotation/export interoperability.

### Source

- OASIS Akoma Ntoso v1.0: https://www.oasis-open.org/standard/akn-v1-0/

## 4. LegalRuleML

### Why it matters

LegalRuleML is an OASIS standard for machine-readable legal norms/rules. It covers much richer semantics than RuleWeaver v0.1, including temporality, jurisdiction, defeasibility, deontic concepts, and source-rule correspondence.

RuleWeaver should not reimplement all of LegalRuleML. It should export supported subsets later.

### Source

- OASIS LegalRuleML Core v1.0: https://www.oasis-open.org/standard/legalruleml-core-specification-version-1-0-oasis-standard/

## 5. W3C PROV

### Why it matters

W3C PROV provides a standard model for provenance using entities, activities, agents, and derivation/usage/attribution relations.

RuleWeaver use:

- source artifact lineage;
- model/compiler activity lineage;
- reviewer attribution;
- adapter/output lineage;
- future provenance export.

### Source

- PROV-O Recommendation: https://www.w3.org/TR/prov-o/

## 6. JSON Schema

### Why it matters

RuleWeaver serialized IR/package objects need a language-neutral public validation contract.

### Source

- JSON Schema specification (2020-12 current published dialect at research time): https://json-schema.org/specification

## 7. Better Rules

### Why it matters

The Better Rules practice treats rules-as-code as a multidisciplinary policy/legal/technical process rather than a code-generation trick.

Especially important for RuleWeaver:

- concept models;
- decision trees;
- business rule statements;
- rules-as-code;
- test suites as preserved policy intent;
- multidisciplinary review.

### Sources

- Better Rules: https://betterrules.nz/
- Practical Better Rules Workshop Manual: https://betterrules.nz/workshop-manual.html

## 8. Georgetown Beeck Center / Digital Benefits Network

### Why it matters

Their policy-to-code experiments tested LLMs on SNAP and Medicaid policies and found that LLMs can assist but complex policy still requires external knowledge and human oversight.

This directly supports RuleWeaver's architecture:

```text
LLM proposal + explicit evidence + deterministic validation + human review
```

rather than autonomous policy implementation.

### Sources

- AI-Powered Rules as Code: https://beeckcenter.georgetown.edu/report/ai-powered-rules-as-code-experiments-with-public-benefits-policy/
- Project overview: https://beeckcenter.georgetown.edu/projects/digital-benefits-network/
- Policy2Code demo findings: https://beeckcenter.georgetown.edu/the-digital-benefits-network-showcases-twelve-generative-ai-experiments-for-benefits-policy-at-policy2code-demo-day/

## 9. PROLEG / 2026 research

### Why it matters

The 2026 work “Can Legislation Be Made Machine-Readable in PROLEG?” demonstrates an end-to-end pattern in which an LLM converts legal text into if/then rules and PROLEG encoding, with legal experts validating/refining the intermediate artifacts before executable use.

This validates the direction but also defines what RuleWeaver must add to become useful infrastructure:

- reusable IR;
- compiler passes;
- provenance;
- validation;
- tests;
- change impact;
- adapters;
- benchmark;
- review workflow.

### Source

- arXiv: https://arxiv.org/abs/2601.01477

## 10. Adjacent research to monitor

### Legal2LogicICL (2026)

Legal natural language → logical formulas using retrieval/few-shot techniques. Relevant to semantic parsing and benchmark design.

- https://arxiv.org/abs/2604.11699

### Executable Governance for AI / Policy-to-Tests (2025)

Converts prose policies into normalized executable rules/DSL for AI governance. Important competitive/architectural comparison: RuleWeaver must differentiate through legal source provenance, change maintenance, human review, and target interoperability.

- https://arxiv.org/abs/2512.04408

## Research conclusions that are now project requirements

1. **Do not trust one-shot natural-language-to-code generation.**
2. **Do not replace human legal/policy interpretation with model confidence.**
3. **Use typed intermediate artifacts.**
4. **Keep source/rule correspondence.**
5. **Treat tests as policy artifacts, not only engineering tests.**
6. **Explicitly model time, parameters, definitions, and exceptions.**
7. **Measure semantic behavior, not text similarity.**
8. **Start with narrow computable rules before broader legal concepts.**

## Research tasks still open

- compare exact exception semantics in OpenFisca/Catala/LegalRuleML;
- choose first real corpus and verify licensing/reuse;
- survey current public Rule-as-Code IR/DSL attempts before freezing RuleWeaver IR v0.1;
- review formal temporal-rule models useful for amendments;
- benchmark structured-output model performance on legal rule extraction;
- evaluate whether PROLEG should become an adapter target;
- review government rules-as-code governance practices across jurisdictions;
- conduct interviews with rules-as-code practitioners before v1.0.
