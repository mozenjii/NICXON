# 11 — Architecture Decision Log

Use this as a lightweight ADR register. Never rewrite old accepted decisions invisibly; append superseding decisions.

## ADR-001 — Standards-first compiler architecture

**Status:** Accepted  
**Date:** 2026-08-16

### Decision

Build RuleWeaver around a canonical intermediate representation and adapters rather than generating target-specific code directly from an LLM.

### Why

- auditable;
- testable;
- provider-neutral;
- reduces arbitrary-code risk;
- enables multiple target runtimes;
- creates a durable OSS asset beyond prompts/models.

## ADR-002 — v0.1 domain is tax/public benefits

**Status:** Accepted

### Decision

Start with explicit computable rules: eligibility, thresholds, parameters, dates, calculations, and explicit exceptions.

### Rejected alternative

“Support any law from day one.”

### Why

Open-textured legal reasoning would force immature semantics and unsafe demonstrations.

## ADR-003 — LLM outside the runtime decision path

**Status:** Accepted

### Decision

LLMs create semantic proposals. Approved rules execute deterministically.

### Why

Reproducibility, auditability, safety, differential testing.

## ADR-004 — Human approval required

**Status:** Accepted

### Decision

A model-proposed rule cannot enter an approved executable package solely based on model confidence or validator success.

### Why

Policy-to-code experiments and existing rules-as-code practice emphasize human interpretation/oversight for complex rules.

## ADR-005 — Ambiguity is first-class

**Status:** Accepted

### Decision

Represent uncertainty as structured ambiguity/unknown/human-judgment states instead of forcing a single interpretation.

## ADR-006 — Provenance is mandatory

**Status:** Accepted

### Decision

Material semantic objects require source provenance and transformation/review provenance.

### Interop direction

W3C PROV concepts may be used for export/mapping.

## ADR-007 — Build a native reference evaluator

**Status:** Accepted

### Decision

Implement a small deterministic evaluator for the canonical IR even though OpenFisca will be the first target adapter.

### Why

- avoids target lock-in;
- establishes reference semantics;
- enables differential adapter testing.

## ADR-008 — OpenFisca first adapter

**Status:** Accepted

### Decision

OpenFisca is the first executable external target because its entities, variables, parameters, periods, formulas, and tests closely match the initial tax/benefit scope.

## ADR-009 — Catala is later, not core dependency

**Status:** Accepted — superseded in part by ADR-019 (target downgraded to reference-only)

### Decision

Use Catala as a later high-assurance interoperability target and design reference. Do not require it for v0.1.

## ADR-010 — Akoma Ntoso for legal document interop

**Status:** Accepted

### Decision

Preserve/use Akoma Ntoso structure and identifiers when supplied. Do not turn the Rule IR into a duplicate legal-document markup standard.

## ADR-011 — LegalRuleML is an interchange target, not the v0.1 IR

**Status:** Accepted — superseded in part by ADR-019 (export target dropped; spec retained as design reference)

### Decision

Use a smaller developer-friendly canonical IR for the first domain, with later LegalRuleML export for supported semantics.

### Why

LegalRuleML is semantically rich; implementing all of it would dramatically expand v0.1.

## ADR-012 — Policy-intent and generated tests are separate

**Status:** Accepted

### Decision

Never let generated tests masquerade as independent validation of the generated rule.

Track test provenance.

## ADR-013 — Parameters over hard-coded legislative numbers

**Status:** Accepted

### Decision

Values that change through legislation/time should normally be represented as dated parameters rather than embedded numeric literals in formulas.

## ADR-014 — Dates use explicit interval semantics

**Status:** Accepted in principle; exact implementation to finalize during M0.

### Decision

Every effective interval must have documented inclusive/exclusive semantics. No implicit host-language date behavior.

## ADR-015 — Start local/simple infrastructure

**Status:** Accepted

### Decision

Filesystem + SQLite is acceptable for early development. PostgreSQL/multi-user infrastructure comes later.

### Why

Compiler semantics are the current risk, not web scale.

## ADR-016 — Provider-neutral model interface

**Status:** Accepted

### Decision

Core compiler APIs may not depend on one proprietary model/provider.

## ADR-017 — v0.1 is redefined as a deterministic core, not the full roadmap

**Status:** Accepted
**Date:** 2026-08-17

### Decision

`v0.1` now means **Phase A (controlled vocabulary + hand-encoded fixture) plus Phase B
(typed IR, deterministic evaluator, validators, boundary tests, mutation harness)**. The
previous ten-point definition in `README.md` becomes `v1.0`.

### Why

The former `v0.1` required OpenFisca export, semantic diff and a public benchmark —
Phases 5-7 of the roadmap, realistically 3-6 person-years. No smaller release was defined
anywhere, which is how projects with good architecture never ship.

### Also resolves

M0 could not close as written. Its P0 fixture required an exception
(`10_BACKLOG.md:92`) built on IR exception types (`:45`) and evaluator exception support
(`:55`), both scheduled P1. Phase 0's exit criterion required "one entity relationship"
(`09_IMPLEMENTATION_ROADMAP.md:28`) while `04_RULE_IR_SPEC.md:375` listed that model as an
open question M0 was meant to decide. Phase A settles those questions before Phase B
depends on them.

---

## ADR-018 — Controlled vocabulary precedes extraction

**Status:** Accepted
**Date:** 2026-08-17

### Decision

No clause is encoded — by hand or by model — until the defined terms for that source are
extracted into an explicit vocabulary document. Approval of a rule is only meaningful
relative to an agreed vocabulary.

### Why

Empirical. In *Encoding legislation* (Artif Intell Law, DOI 10.1007/s10506-023-09350-1),
three experienced coders independently encoded the Australian Copyright Act 1968 and
reached **0% exact and 3% semantic agreement on rules**. After agreeing shared terms,
agreement rose to 10-30% exact and 26-53% semantic.

Qualified experts do not converge on one correct encoding. Without a fixed vocabulary,
"approve or reject this rule" is not a well-posed question, and ADR-004's human approval
gate rests on nothing.

### Consequence

Adds `docs/15_VOCABULARY.md` as a required artifact per corpus. Blocks Phase A step 2.

---

## ADR-019 — Adapter strategy revised: OpenFisca is code generation; Catala and LegalRuleML are references

**Status:** Accepted
**Date:** 2026-08-17
**Supersedes in part:** ADR-009, ADR-011

### Decision

1. **OpenFisca** remains the first and only v1.0 executable target, but the adapter is a
   **code generator**, not a serializer.
2. **Catala** is downgraded from "later target" to **design reference only**.
3. **LegalRuleML export is dropped.** Its specification is retained as the design
   reference for temporal and defeasible semantics.

### Why

- OpenFisca rules are Python `Variable` subclasses whose `formula(entity, period,
  parameters)` bodies are arbitrary vectorised NumPy. There is no declarative rule-
  authoring API. Only *parameters* are YAML — a genuine serialization target. The IR must
  therefore carry enough computational structure to lower into vectorised formulas, or
  under-expressiveness surfaces as ungeneratable code rather than lossy output.
- Catala is literate programming authored by a lawyer-programmer pair; its value is the
  human-audited law↔code correspondence. Machine-generated Catala discards exactly that
  property, so emitting it is technically possible and largely pointless.
- LegalRuleML tooling is dormant — `oasis-tcs/legalruleml` last commit July 2020, tool
  development explicitly out of scope for the TC, all four Statements of Use academic. An
  adapter with no consumer cannot be validated and is unfalsifiable weight.

### Note on the three-target premise

The targets have incompatible semantic cores — OpenFisca's imperative dated vectors,
Catala's prioritised-default logic, LegalRuleML's deontic ontology. An IR expressive
enough for all three is either lowest-common-denominator or three bespoke lowerings.
Target neutrality (ADR-007) is preserved by the native evaluator, not by shipping adapters.

---

## ADR-020 — Exception priority and temporal semantics are adopted, not invented

**Status:** Accepted
**Date:** 2026-08-17

### Decision

- **Exception precedence** adopts Catala's prioritised-default model: a base case plus
  exceptions with declared precedence.
- **Temporal semantics** adopts LegalRuleML Core's multi-axis model — assertion time,
  validity, efficacy, enforcement — rather than the current single `effective` interval.
- Exception effects gain **`substitute`** alongside `disable_base_rule`.

### Why

`04_RULE_IR_SPEC.md:374-381` files exception priority and period algebra as open questions
to settle during M0/M1. Both have published worked answers; re-deriving them is wasted
effort and will land somewhere worse.

`disable_base_rule` alone cannot express the dominant legal form — *"except that for a
household with an elderly member, the limit is $X."* Encoding substitution as
disable-plus-shadow-rule duplicates the condition, severs the source correspondence
required by `README.md:36`, and breaks amendment impact analysis, because amending the
exception clause no longer touches the rule that implements it.

Single-axis time cannot express a provision enacted mid-2026 that applies to tax years
beginning after 31 December 2025, nor recomputation of a past determination under the
rules as they stood. For a system whose promise is audit, that is disqualifying.

---

## ADR-021 — Review is adversarial by design

**Status:** Accepted
**Date:** 2026-08-17

### Decision

The review gate must include seeded-error injection with a monitored catch rate, blind
dual-encoding on a sample of clauses, and timing telemetry. A review UI that presents a
proposed rule and an approve button is not an acceptable implementation of ADR-004.

### Why

Automation bias is measured and severe. Dratsch et al. (*Radiology* 2023, DOI
10.1148/radiol.222176) found that when shown incorrect AI suggestions, correct ratings fell
from 82.3% to **45.5% among very experienced reviewers** (79.7%→19.8% for inexperienced).
Expertise attenuates the effect but does not prevent it.

ADR-004 makes human approval the load-bearing safety control. Unstructured approval
produces rubber-stamping, so the gate needs evidence it is working, not just a workflow
state.

### Secondary benefit

EU AI Act Art 14 requires automation-bias mitigation for high-risk systems. Benefits
eligibility is high-risk under Annex III 5(a). This design doubles as compliance evidence.

---

## ADR-022 — Keep the LLM out of the runtime path for legal, not only technical, reasons

**Status:** Accepted
**Date:** 2026-08-17
**Reinforces:** ADR-003

### Decision

ADR-003 is upgraded from an engineering preference to a **legal position**. No change to
the architecture; a change to how firmly it is held.

### Why

- EU AI Act **Annex III 5(a)** classifies systems used to evaluate eligibility for
  essential public assistance benefits as high-risk, triggering Arts 9-15, 17, 43, 49, 72,
  73 plus deployer duties under Arts 26-27.
- Because RuleWeaver's runtime decider is a deterministic, human-authored rule engine, it
  is arguably not an "AI system" under Art 3(1) — no inference, no adaptiveness. The LLM
  sits pre-deployment as an authoring aid. **This distinction is the entire legal position.**
- **SCHUFA (CJEU C-634/21, 7 Dec 2023)** holds that an automated output is itself an
  Art 22 "decision" where it plays a determining role downstream, even when a different
  party formally decides. Nominal human sign-off does not defeat Art 22 — which is why
  ADR-021's adversarial review matters and a disclaimer does not.

### Timing

The Digital Omnibus (in force 27 Jul 2026) deferred Annex III high-risk obligations from
2 Aug 2026 to **2 Dec 2027**. Art 50 transparency applies from 2 Aug 2026. This is a real
build window, not an exemption.

### Caveat

This is architectural analysis, not legal advice. Obtain counsel before any deployment
claim rests on the Art 3(1) argument.

---

## Pending ADRs

These should be decided with examples/tests, not prematurely:

- entity/group aggregation semantics;
- exact exception/priority model;
- period/periodicity algebra;
- rounding rules;
- human-required predicate semantics;
- public code/data license choices;
- canonical plugin packaging.
