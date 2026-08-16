# RuleWeaver

> **An open-source compiler infrastructure for transforming natural-language rules and regulations into provenance-preserving, testable, executable rule representations.**

RuleWeaver is not a legal chatbot and not a system that lets an LLM make final legal decisions. Its purpose is to help experts convert authoritative policy and legislation into structured, reviewable, executable artifacts while preserving a traceable connection to the source text.

## Project thesis

Human rules are published as prose. Production systems need precise logic, parameters, dates, definitions, exceptions, tests, and version history. Today that translation is expensive, duplicated across institutions, difficult to audit, and easy to get wrong.

RuleWeaver treats the translation step as a **compiler problem**:

```text
Authoritative source
      ↓
Source document model
      ↓
LLM-assisted semantic compilation
      ↓
RuleWeaver IR
      ↓
Type / reference / temporal / consistency checks
      ↓
Generated policy-intent tests
      ↓
Human review and approval
      ↓
Deterministic executable targets
      ↓
OpenFisca / Catala / LegalRuleML / other adapters
```

## Non-negotiable principles

1. **The LLM proposes; deterministic software and accountable humans decide.**
2. **Every material semantic object must be linked to an authoritative source span.**
3. **Ambiguity is a first-class output, not something the model is forced to hide.**
4. **No extracted rule is executable in an approved package until it passes review.**
5. **Rule execution is deterministic. LLMs are not in the runtime decision path.**
6. **Tests represent policy intent and must survive implementation changes.**
7. **Dates, amendments, thresholds, exceptions, definitions, and jurisdiction are modeled explicitly.**
8. **The core is domain-neutral, but v0.1 is intentionally narrow: tax and public-benefit eligibility/calculation rules.**
9. **The repository must remain useful even if model vendors change.**
10. **RuleWeaver must never present itself as an authoritative legal source or legal-advice system.**

## Current status — 2026-08-16

### Decided / researched

- [x] Project direction selected: Rules as Code + LLM-assisted compiler.
- [x] Architecture selected: **standards-first compiler with a canonical RuleWeaver IR**.
- [x] Initial target domain selected: **tax and public-benefit rules**.
- [x] OpenFisca selected as first executable adapter.
- [x] Catala selected as a high-assurance/literate-programming interoperability target.
- [x] Akoma Ntoso selected as a useful legal-document interoperability target.
- [x] LegalRuleML selected as a legal-rule interchange target.
- [x] W3C PROV selected as inspiration/interop for provenance.
- [x] Human review, abstention, ambiguity, and generated tests defined as mandatory architectural features.

### Built

- [x] Typed rule IR with a closed expression AST.
- [x] Deterministic evaluator, four-state, with execution traces.
- [x] Verification engine — 16 checks with stable `RWxxxx` diagnostic codes.
- [x] Boundary case generator.
- [x] Mutation harness — **17/17 planted faults caught**.
- [x] Date transition generator.
- [x] Semantic diff and amendment impact analysis.
- [x] Golden corpus: 13 SNAP rules hand-encoded from 7 CFR 273.9.
- [x] CLI.

### Not built yet

- [ ] Source ingestion pipeline.
- [ ] LLM compiler — deliberately last, until the deterministic core is proven.
- [ ] Human review UI.
- [ ] OpenFisca adapter.
- [ ] Public benchmark.

See [`docs/01_PROJECT_STATUS.md`](docs/01_PROJECT_STATUS.md) for the detailed state.

## Quickstart

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # Windows: .venv/Scripts/pip
pytest                                    # 54 tests
```

Check a rule package, then run a household through it:

```bash
ruleweaver validate examples/snap/rules.json
ruleweaver evaluate examples/snap/rules.json examples/snap/scenarios/baseline.json --trace
```

The trace shows which rule produced each value, which is the point:

```text
var.household.standard_deduction      = 204   [rule.snap.standard_deduction_minimum base]
var.household.excess_shelter_deduction = 402  [exception:exception.snap.shelter_cap_applies]
var.household.is_income_eligible      = True  [rule.snap.income_eligible base]
```

The first line is a *notwithstanding* clause overriding a computed value; the second is a
substitutive exception applying a cap because the household has no elderly or disabled
member. Both are traceable to the clause that requires them.

A missing input never becomes a denial — it evaluates to `UNKNOWN` and propagates:

```bash
ruleweaver boundaries examples/snap/rules.json examples/snap/scenarios/baseline.json \
  --observe var.household.is_income_eligible
```

### Amendment impact

Ask what a change to the law actually does to real households:

```bash
ruleweaver diff examples/snap/rules.json \
                examples/snap/amendments/earned-deduction-25pct.json \
                --scenario examples/snap/scenarios/baseline.json \
                --observe var.household.net_monthly_income
```

```text
1 semantic, 0 cosmetic
  [SEMANTIC] parameter_value_changed param.snap.earned_income_deduction_rate: 0.20 -> 0.25

LEGISLATIVE CHANGE IMPACT
  directly affected rules     1
  transitively affected rules 5
  scenarios with a changed outcome 1
    baseline: net_monthly_income  594.0000 -> 481.5000
```

A reworded citation is reported as cosmetic and stops there. Only a change in meaning
propagates into impact analysis.

## Read this documentation in order

1. [`docs/00_PROJECT_BRIEF.md`](docs/00_PROJECT_BRIEF.md)
2. [`docs/01_PROJECT_STATUS.md`](docs/01_PROJECT_STATUS.md)
3. [`docs/02_PRODUCT_SPEC.md`](docs/02_PRODUCT_SPEC.md)
4. [`docs/03_ARCHITECTURE.md`](docs/03_ARCHITECTURE.md)
5. [`docs/04_RULE_IR_SPEC.md`](docs/04_RULE_IR_SPEC.md)
6. [`docs/05_COMPILER_PIPELINE.md`](docs/05_COMPILER_PIPELINE.md)
7. [`docs/06_VERIFICATION_SAFETY.md`](docs/06_VERIFICATION_SAFETY.md)
8. [`docs/07_DATA_BENCHMARK_EVAL.md`](docs/07_DATA_BENCHMARK_EVAL.md)
9. [`docs/08_ADAPTERS_INTEROP.md`](docs/08_ADAPTERS_INTEROP.md)
10. [`docs/09_IMPLEMENTATION_ROADMAP.md`](docs/09_IMPLEMENTATION_ROADMAP.md)
11. [`docs/10_BACKLOG.md`](docs/10_BACKLOG.md)
12. [`docs/11_DECISIONS.md`](docs/11_DECISIONS.md)
13. [`docs/12_RESEARCH_REFERENCES.md`](docs/12_RESEARCH_REFERENCES.md)
14. [`docs/13_REPO_STRUCTURE.md`](docs/13_REPO_STRUCTURE.md)
15. [`docs/14_GLOSSARY.md`](docs/14_GLOSSARY.md)

## v0.1 definition of success

A user can provide a small, authoritative tax/benefit policy source and RuleWeaver can:

1. preserve the source hierarchy and citations;
2. identify definitions, parameters, dates, computable rules, exceptions, and dependencies;
3. compile candidate rules into a typed IR;
4. identify unresolved ambiguity instead of guessing;
5. generate boundary/date/exception tests;
6. let a human review source-to-rule mappings;
7. execute only the approved IR through a deterministic evaluator;
8. export an approved subset to OpenFisca;
9. compare a revised policy version and show impacted rules/tests;
10. produce a reproducible evaluation report.

## What v0.1 is explicitly not

- a general legal reasoning engine;
- a court-case outcome predictor;
- a legal-advice chatbot;
- an autonomous benefits eligibility authority;
- a system that automatically approves laws-to-code translations;
- a universal OCR project;
- a replacement for OpenFisca, Catala, LegalRuleML, or Akoma Ntoso.

RuleWeaver should connect these ecosystems where useful rather than reimplement them.
