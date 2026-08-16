# 15 — Controlled Vocabulary (SNAP, v0.1)

**Required by ADR-018.** No clause is encoded — by hand or by model — until its terms
appear here. Approval of a rule is only meaningful relative to an agreed vocabulary.

**Why this file exists.** In *Encoding legislation* (Artif Intell Law, DOI
10.1007/s10506-023-09350-1), three experienced coders independently encoded the same Act
and reached **0% exact and 3% semantic agreement on rules**. After agreeing shared terms,
agreement rose to 10-30% exact and 26-53% semantic. Without a fixed vocabulary, "approve
or reject this rule" is not a well-posed question and ADR-004's human gate rests on
nothing.

**Sources.** `examples/snap/sources/` — 7 CFR 271.2 and 7 CFR 273.9, point-in-time
2026-01-01, sha256 recorded in `manifest.json`.

**Status of every term below:** `proposed`. Nothing here is agreed until a second reader
has signed off. Do not encode against a `proposed` term without recording that you did.

---

## Naming rules

- Term IDs are `snake_case`, value-free, and stable. Never encode an amount, a date or a
  jurisdiction into an ID (`04_RULE_IR_SPEC.md:63`).
- A term means exactly what its cited source says. Where the regulation defines a term,
  the definition is quoted, not paraphrased.
- Where a term is **not** defined in the source, it is marked `DERIVED` and carries an
  explicit rationale. Derived terms are the highest-risk objects in the vocabulary and
  must be reviewed first.

---

## Entities

| Term | Definition | Source |
|---|---|---|
| `household` | The unit whose eligibility and allotment are determined. Composition rules are in 7 CFR 273.1 and are **out of scope for v0.1** — the fixture takes household composition as given input. | 7 CFR 273.1 |
| `household_member` | A natural person belonging to a `household`. | 7 CFR 273.1 |
| `state_agency` | The agency administering the program in a jurisdiction. Not a computational entity in v0.1. | 7 CFR 271.2 |

**Aggregation note.** `household` is a *group* entity and `household_member` a *member*
entity. Every income and size rule below aggregates over members. This is the construct
`04_RULE_IR_SPEC.md:377` leaves open and ADR-020 requires.

---

## Classification terms

| Term | Definition | Source |
|---|---|---|
| `elderly_or_disabled_member` | "a member of a household who: (1) Is 60 years of age or older; (2) Receives supplemental security income benefits under title XVI of the Social Security Act or disability or blindness payments under titles I, II, X, XIV, or XVI…" — a **disjunction of nine qualifying conditions**. | 7 CFR 271.2 |
| `household_has_elderly_or_disabled_member` | `DERIVED` — true where any member satisfies `elderly_or_disabled_member`. Not defined as such in the source; it is the existential aggregation the deduction rules actually test. | derived from 7 CFR 271.2 |

**Note.** `elderly_or_disabled_member` is a nine-branch disjunction spanning several
Social Security Act titles. v0.1 encodes branch (1) — age ≥ 60 — as computable and the
remaining branches as **input predicates**, not derived facts. The system is told whether
a member receives SSI; it does not compute Social Security eligibility.

---

## Monetary and income terms

| Term | Definition | Source |
|---|---|---|
| `household_income` | "all income from whatever source excluding only items specified in paragraph (c)". | 7 CFR 273.9(b) |
| `earned_income` | Wages and salaries of an employee, and the categories enumerated at (b)(1). | 7 CFR 273.9(b)(1) |
| `unearned_income` | Income enumerated at (b)(2). | 7 CFR 273.9(b)(2) |
| `gross_monthly_income` | `DERIVED` — `household_income` for a calendar month, before deductions. The regulation works in monthly terms without naming this quantity. | derived from 7 CFR 273.9(a),(b) |
| `net_monthly_income` | `DERIVED` — `gross_monthly_income` less the deductions at (d). Named "net income" throughout (a) but never given a standalone definition. | derived from 7 CFR 273.9(a),(d) |
| `allotment` | "the total value of benefits a household is authorized to receive during each month or other time period." | 7 CFR 271.2 |

---

## Threshold and parameter terms

| Term | Definition | Source |
|---|---|---|
| `federal_poverty_level` | The Federal income poverty guidelines, published annually and varying by household size and jurisdiction. **External dated input**, not computed here. | 7 CFR 273.9(a) |
| `gross_income_standard` | 130 percent of `federal_poverty_level`, annual figure divided by 12, **rounded upward**. | 7 CFR 273.9(a)(1),(a)(3)(i) |
| `net_income_standard` | `federal_poverty_level` itself, annual divided by 12, **rounded upward**. | 7 CFR 273.9(a)(2),(a)(3)(ii) |
| `standard_deduction` | 8.31 percent of `net_income_standard` for the household size, rounded up to the nearest whole dollar; **clamped at the six-person value** for larger households; and subject to a jurisdiction-specific **minimum** that overrides the computed value. | 7 CFR 273.9(d)(1) |
| `earned_income_deduction` | 20 percent of `earned_income`. | 7 CFR 273.9(d)(2) |
| `excess_shelter_deduction` | Shelter expenses above 50 percent of income remaining after all other deductions; **capped** by area, *unless* the household contains an elderly or disabled member. | 7 CFR 273.9(d)(6)(ii) |
| `dependent_care_deduction` | Costs of care necessary for a member to work, train or study. | 7 CFR 273.9(d)(4) |
| `jurisdiction` | One of: 48 contiguous states + DC, Alaska, Hawaii, Guam, Virgin Islands. A **parameter dimension**, not a rule condition. | 7 CFR 273.9(a),(d) |

---

## Benefit calculation terms

Added 2026-08-17 for 7 CFR 273.10(e). **Process note:** these rules were encoded before
the terms were recorded here, which inverts ADR-018. The order matters — the vocabulary
exists so that "approve this rule" is a well-posed question — and the lapse is recorded
rather than quietly corrected.

| Term | Definition | Source |
|---|---|---|
| `max_allotment` | The Thrifty Food Plan maximum for the household size. Published annually by FNS; an **external dated input**, not computed. | 7 CFR 273.10(e)(2)(ii)(A) |
| `benefit_reduction` | `DERIVED` — thirty percent of `net_monthly_income`. The regulation names the proportion but not the quantity. | 7 CFR 273.10(e)(2)(ii)(A) |
| `allotment` | "the total value of benefits a household is authorized to receive during each month or other time period" — computed as `max_allotment` less `benefit_reduction`, floored at zero. | 7 CFR 271.2; 273.10(e)(2)(ii)(A) |
| `minimum_benefit` | "8 percent of the maximum allotment for a household of one, rounded to the nearest whole dollar." Applies to eligible one- and two-person households except in an initial month. | 7 CFR 273.10(e)(2)(ii)(C) |

### An unresolved discretionary choice

`273.10(e)(2)(ii)(A)` gives the State agency a **choice** of two rounding methods:

1. round thirty percent of net income up to the nearest dollar; or
2. do not round it, and instead round the resulting allotment down.

These produce different amounts. v0.1 implements method (1) and records the choice on
`rule.snap.benefit_reduction`. This is not an ambiguity in the law — the law is clear that
both are permitted — it is **jurisdictional configuration**, and modelling it as a
parameter dimension is the correct fix. Filed as open vocabulary question 4.

**Out of v0.1 scope:** initial-month proration (`273.10(a)(1)`) and the $10 initial-month
threshold (`(e)(2)(ii)(B)`), both of which depend on a certification-period model the IR
does not yet carry.

---

## Constructs these terms force into IR v0.1

This is the point of encoding real law before freezing the IR. Every construct below is
required by the table above and is currently missing or unresolved.

| Construct | Forced by | Spec status |
|---|---|---|
| **Aggregation over group members** | `household_income` sums member income; `household_has_elderly_or_disabled_member` is an existential over members | open question 4 (`04:377`) — **required** |
| **Period conversion** | annual poverty guideline ÷ 12 → monthly standard | open question 1 (`04:374`) — **required** |
| **Explicit rounding** | "rounding the results upwards as necessary"; "rounded up to the nearest whole dollar" | open question 5 (`04:378`) — **required** |
| **Parameter dimensions** | every threshold varies by `household_size` × `jurisdiction` | partially supported (`04:132`) |
| **Schedule clamp / fold** | standard deduction fixed at the six-person value above six; poverty guideline increments above eight persons | **absent** — no fold in the AST |
| **Substitutive exception** | shelter cap applies *unless* an elderly or disabled member is present | **absent** — only `disable_base_rule` exists (`04:261`) |
| **Norm override** | `(d)(1)(iii)` opens "**Notwithstanding** paragraphs (d)(1)(i) and (d)(1)(ii)" — a floor that overrides the computed value | **absent** — no cross-rule precedence (ADR-020) |
| **Ordered deduction sequence** | excess shelter is computed on income *after* deductions (d)(1)-(d)(5) | expressible via dependencies, but ordering is semantic and must be explicit |

**Deliberately out of scope for v0.1:** household composition (273.1), categorical
eligibility, work requirements and ABAWD time limits (273.7, 273.24), the standard utility
allowance options at (d)(6)(iii), and CPI indexation of thresholds. These are input
parameters or later work, not v0.1 rules.

---

## Open vocabulary questions

1. Is `gross_monthly_income` computed before or after income exclusions at (c)? The
   regulation's "all income… excluding only items specified in paragraph (c)" implies
   exclusions apply first, making "gross" already net of exclusions. **Confirm before
   encoding** — it changes every threshold comparison.
2. Does `household_income` for the gross test include the income of members excluded from
   the household under 273.1? Out of v0.1 scope, but the fixture must state its assumption.
3. `standard_deduction` has three interacting rules — percentage, six-person clamp, and
   statutory minimum. Encoding order determines the result. ADR-020's precedence model
   must resolve this, and it is the best available test case for it.
4. The rounding method at `273.10(e)(2)(ii)(A)` is a State agency choice, not a fact about
   the law. It should become a parameter dimension so a jurisdiction selects it, rather
   than being hard-coded as it is in v0.1.
