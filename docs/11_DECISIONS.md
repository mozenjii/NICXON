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

## ADR-023 — Apache-2.0 for code; source law is public domain

**Status:** Accepted
**Date:** 2026-08-17

### Decision

Project code is licensed **Apache-2.0**. The SNAP source snapshots under
`examples/snap/sources/` are US federal regulations and carry no copyright.

### Why Apache rather than MIT

The project's stated aim is that other systems adopt its IR and interfaces. Apache-2.0
carries an explicit patent grant and a defensive termination clause; MIT does not. For a
format intended as shared infrastructure, contributors and adopters both benefit from
that grant being explicit rather than implied.

### Source text

US federal regulations are not subject to copyright under the government edicts doctrine,
so the snapshots are redistributable and the fixture reproduces offline without a fragile
URL fetch. `examples/snap/sources/manifest.json` records the basis alongside each hash.

**This does not generalise.** UK and Canadian legislation is Crown copyright, EU material
falls under the Open Data Directive, and agency benefit manuals frequently state no status
at all. Any future corpus needs its own rights review before redistribution — the
manifest has a `rights` block for exactly that.

### Reversible

No external contributions have been accepted yet, so this can still be changed without
relicensing anyone else's work. After the first outside contribution it cannot.

---

## ADR-024 — Approval is enforced at execution, not documented

**Status:** accepted (2026-08-20)

README principle 4 — "no extracted rule is executable in an approved package until it
passes review" — was true of the documentation and false of the code. The evaluator ran
whatever package it was handed. Review recorded decisions; nothing consulted them.

`src/ruleweaver/approval.py` is the enforcement. `ruleweaver evaluate --require-approval`
reads the log and refuses; the OpenFisca adapter refuses by default, with no flag that
makes refusal the exception.

### Excluding a rule leaves its target unknown, not false

A filtered package is still a valid package. Rules that survive reference variables the
excluded rules would have assigned, and those evaluate to `unknown` and propagate. "This
determination rests on a rule nobody has approved" and "this household does not qualify"
are different claims, and conflating them is the specific failure this project exists to
avoid.

### Why not a flag on the rule

Status is derived from the log, so a rule whose clause was re-fetched and changed falls out
of the approved set without anyone remembering to revoke it. A stored flag would need
somebody to notice, and nobody ever does.

---

## ADR-025 — Ingestion verifies digests on every load, and the check is not optional

**Status:** accepted (2026-08-20)

`load_corpus` checks each snapshot against the sha256 in the manifest before parsing it.
Failure raises. There is a `verify=False` for the case of deliberately replacing a
snapshot, and a corpus loaded that way is marked so nothing downstream mistakes it for a
verified one.

### Justified on its first run

With `core.autocrlf` enabled — the Windows default — git rewrote the line endings of every
snapshot on checkout, and every recorded digest failed. Nothing else would have noticed:
the XML still parsed, the rules still evaluated, and the provenance chain the project rests
on was quietly broken in a way that depended on each contributor's git configuration.

`.gitattributes` now pins `examples/snap/sources/*.xml` as binary. The check is what made
the corruption visible, which is the argument for running it every time rather than
trusting the checkout.

---

## ADR-026 — A quote must be contiguous text from the clause it cites

**Status:** accepted (2026-08-20)

Every `SourceSpan.quote` must appear, whitespace-normalised, inside the cited clause or its
subtree. `RW1001` enforces it whenever a corpus is available.

### What this rejects

Paraphrase, truncation that changes meaning, and composites joined with an ellipsis. All
three read as quotations and none of them can be checked. When ingestion was first pointed
at the fixture, **fourteen of the fifteen hand-encoded rules failed** — and the failures
were not sloppiness. They were the natural result of writing a quote from memory of what a
clause said rather than from the clause.

### Whitespace is normalised, nothing else

A quote transcribed from a rendered page differs from the source in line breaks and runs of
spaces. Failing on that would train reviewers to ignore the check, which is worse than the
laxity. Any other difference is a failure.

### A citation covers its subtree

"7 CFR 273.9(d)" names a subsection, not a paragraph. Quoting a child of the clause you
cite is normal legal practice, so resolution checks the clause and everything nested under
it.

---

## ADR-027 — The extraction pass is bounded by checks, not by prompt wording

**Status:** accepted (2026-08-20)

Six checks run on every proposal, in `compile/extract.py`, and none can be disabled: the
output must parse as IR; the rule must cite the clause it was shown; every quote must
resolve against the verified source; `interpretation.status` is overwritten to
`needs_review`; `model_confidence` is recorded and never branched on; and injection
findings escalate to a blocking ambiguity.

### Why the prompt is not the control

The prompt says the model may not mark its own work approved. That instruction is worth
having — it shapes the output and documents the intent — but a model can decline to follow
it, and a prompt edit can drop it without any test failing. The status is therefore
overwritten in code. A test asserts both: that the code forces the status, and that the
sentence is still in the prompt.

### A rejected proposal still comes back

Carrying its diagnostics. A reviewer needs to see what the model produced *and* why it was
refused. Returning nothing teaches them nothing and hides a systematic failure behind an
empty queue.

### Injection findings are escalated, never dropped

Modelled as a blocking ambiguity so they inherit behaviour that already exists: they block
approval, they appear beside the rule, and a person has to resolve them. Silently
discarding a flagged proposal would hide the attempt from the only party who can act on it.

---

## ADR-028 — Reviewer identity fails closed

**Status:** accepted (2026-08-20)

The reviewer application resolves identity from an HMAC-signed session token, or from a
header set by an authenticating proxy on a trusted-peer list. With neither configured it
raises `IdentityNotConfigured` and does not start.

### What changed

The previous default trusted an `X-Reviewer` header and emitted a `RuntimeWarning`. A
deployment that forgot to wire up identity still started, still served, and still recorded
approvals — against whatever name the client sent. The only signal was a warning in a log
nobody reads.

### Why an audit log with a forgeable actor is worse than none

It looks like evidence. ADR-022's position — that the deterministic runtime is defensible
under GDPR Art. 22 because an accountable human approved each rule — depends entirely on
being able to name that human. A log whose reviewer field the client controls cannot
support the claim it is being offered for.

### Trusted-proxy support is deliberate

Most real deployments authenticate at an SSO gateway. Refusing to support that pattern
would push operators back to the insecure resolver, so it is supported — with a mandatory
list of peers the application will believe, because a header is trustworthy exactly when
nothing else can reach the port.

---

## ADR-029 — The OpenFisca adapter reports the four-state gap rather than absorbing it

**Status:** accepted (2026-08-20)

OpenFisca has no unknown. Every variable has a type default, so a fact nobody supplied is
indistinguishable from a fact that is genuinely zero. The IR spends its whole design
refusing that conflation.

The gap is not repairable inside the adapter, so every export emits `RW8001` and the
generated module repeats the warning at the top of the file.

### Why not silently approximate

An adapter that dropped four-state semantics quietly would produce a model that denies
benefits for missing paperwork while claiming to implement the same rules. That is the
exact harm the four-state evaluator exists to prevent, arriving through the one path nobody
is watching.

### Exceptions do lower faithfully

A substitutive exception becomes `np.select` over the conditions in descending priority,
with the base expression as the default. The IR already requires distinct priorities, so
the order is total and the selection is decidable. `disable_base_rule` does not lower: it
says the rule produces *nothing*, and OpenFisca would render that as a zero.

### The export is unverified

Generated, parses, every variable carries its citation — and never executed. Running it
under OpenFisca and comparing against the deterministic evaluator is the evidence that
would make this a claim about behaviour. Until then it is a claim about structure, and
`docs/01_PROJECT_STATUS.md` says so.

---

## Pending ADRs

These should be decided with examples/tests, not prematurely:

- entity/group aggregation semantics;
- exact exception/priority model;
- period/periodicity algebra;
- rounding rules;
- human-required predicate semantics;
- canonical plugin packaging (license choices settled by ADR-023);
- canonical plugin packaging.
