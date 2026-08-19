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

## Current status — 2026-08-20

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
- [x] Verification engine — 17 checks with stable `RWxxxx` diagnostic codes.
- [x] Boundary case generator and date transition generator.
- [x] Mutation harness — **22/22 planted faults caught**.
- [x] Semantic diff and amendment impact analysis.
- [x] Source ingestion — eCFR XML into 468 addressable clauses, every snapshot
      verified against its recorded sha256 before it is read.
- [x] Golden corpus: 15 SNAP rules from 7 CFR 271.2, 273.9 and 273.10, **every one of
      whose 16 citations resolves to verbatim text in the clause it names**.
- [x] LLM compilation — clause segmentation and rule extraction, behind six checks the
      model cannot talk its way past.
- [x] Provider-neutral model interface (Claude + GPT) with prompt-injection guard.
- [x] Adversarial review gate — seeded errors, catch rate, rubber-stamp detection.
- [x] Reviewer application — clause beside rule, hash-chained audit log, authenticated
      identity.
- [x] Approval enforced at execution: unapproved rules do not run.
- [x] OpenFisca adapter — a code generator, per ADR-019.
- [x] CLI.

### Not built yet

- [ ] **Equivalence evidence for the OpenFisca export.** The generated package is checked
      structurally and parses. Nobody has run it under OpenFisca and compared the results
      against the deterministic evaluator, so "exports to OpenFisca" is a structural claim.
- [ ] PDF and Akoma Ntoso ingestion.
- [ ] Parameter extraction — thresholds still come from the hand-encoded package.
- [ ] Public benchmark.

See [`docs/01_PROJECT_STATUS.md`](docs/01_PROJECT_STATUS.md) for the detailed state.

## Quickstart

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"        # Windows: .venv/Scripts/pip
pytest                                    # 370 tests
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

### Reviewing extracted rules

```bash
pip install -e ".[review]"
ruleweaver review examples/snap/rules.json
```

Opens a queue at `http://127.0.0.1:8000`. Each rule is shown beside the statutory text it
came from, with its diagnostics and any unresolved readings. Decisions are written to a
hash-chained, append-only log — a row altered outside the application breaks the chain and
`/metrics` reports where.

Approvals expire on their own: they are recorded against the hash of the clause the rule
cites, so re-fetching a source that has changed moves every rule resting on it back into
the queue.

`/metrics` reports the numbers that decide whether the gate is real — the share of
deliberately seeded faults reviewers caught, the median time spent per rule, and the
approval rate. It warns when those look like rubber-stamping. An unseeded queue is
reported as *unmeasured*, not as a zero catch rate; the two mean opposite things.

**The bundled identity resolver trusts a header and warns that it is unfit for
deployment.** Wire in a real identity provider before running this anywhere real — an
audit log whose reviewer field the client can set is not an audit log.

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

### Compiling from the source

Ingestion is separate from extraction, and both are separate from approval. Each step
refuses to guess:

```bash
ruleweaver ingest examples/snap/sources/manifest.json
```

Every snapshot is checked against the sha256 the manifest records before it is parsed. A
file that does not match stops the command — a corrupted source is not a source.

```bash
ruleweaver validate examples/snap/rules.json --sources examples/snap/sources/manifest.json
```

With `--sources`, validation also resolves every citation: the clause must exist, and the
quote must be contiguous text inside it. This check found that fourteen of the fifteen
hand-encoded rules quoted text that was not in the clause they cited.

```bash
ruleweaver extract examples/snap/sources/manifest.json examples/snap/rules.json   --provider anthropic --source 7cfr-273.9 --out build/candidate.json
```

Segments each clause, proposes a rule for the computable ones, and writes a candidate
package beside a run record — corpus digests, prompt hashes, decoding settings, and every
model call. The default provider calls nothing; reaching a paid API takes an explicit flag.

**Six checks run on every proposal, and the model cannot argue with any of them.** The
output must parse as IR. It must cite the clause it was shown. Its quotes must be present
in the verified source. Its status is forced to `needs_review` whatever the model asked
for — a model may not approve its own work. Confidence is recorded and never acted on. And
if the clause contains text that reads as an instruction to the compiler, the proposal is
escalated with a blocking ambiguity rather than dropped, because dropping it would hide
the attempt from the only person who can do anything about it.

### The gate

```bash
ruleweaver approvals build/candidate.json
ruleweaver evaluate build/candidate.json examples/snap/scenarios/baseline.json   --require-approval
```

A fresh candidate is entirely blocked. `--require-approval` refuses to execute; `--partial`
runs the approved subset instead, and everything that depended on an unapproved rule comes
back `UNKNOWN` — never `False`. "No approved rule decides this" and "this household does
not qualify" are different answers and the runtime keeps them apart.

The reviewer application needs a real identity before it will serve:

```bash
export RULEWEAVER_SESSION_SECRET=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
ruleweaver token alice@example.gov
```

With neither a signing secret nor a trusted proxy configured it refuses to start. It used
to fall back to trusting a header, which meant a deployment that forgot to wire up identity
still recorded approvals — against whatever name the client sent.

### Exporting to OpenFisca

```bash
ruleweaver export examples/snap/rules.json build/openfisca
```

Per ADR-019 this is a **code generator**: OpenFisca rules are Python `Variable` subclasses
with vectorised formulas, and only parameters are data. Unapproved rules are not exported.

Every export reports `RW8001`, and the generated module repeats it at the top of the file:

> OpenFisca has no unknown state. A fact nobody supplied takes the type default — 0 for a
> number, False for a boolean — so a missing input is indistinguishable from a genuine
> zero.

That gap cannot be closed inside the adapter, so it is stated rather than absorbed. It is
the difference between a model that asks a question and one that issues a denial.

**The export has not been executed.** It is generated, it parses, and every variable
carries its citation. Running it under OpenFisca and comparing the results against the
deterministic evaluator is the evidence that would make "exports to OpenFisca" a claim
about behaviour, and that work has not been done.

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
16. [`docs/15_VOCABULARY.md`](docs/15_VOCABULARY.md)

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
