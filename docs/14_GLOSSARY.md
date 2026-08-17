# 14 — Glossary

## Authoritative source

The official or designated legal/policy material from which an implementation is derived. RuleWeaver output is not the authoritative source.

## Rules as Code (RaC)

A practice of representing rules/policy in machine-consumable/executable form so they can be tested, simulated, reused, and maintained.

## Source document

RuleWeaver's normalized representation of the authoritative source, before semantic rule interpretation.

## Source span

A precise reference from a semantic object back to the supporting source text/structure.

## RuleWeaver IR

The canonical typed intermediate representation between natural-language source and target executable systems.

## Rule package

A versioned artifact containing sources, rules, parameters, definitions, provenance, tests, review states, and metadata.

## Proposal

A compiler/LLM-generated semantic interpretation that has not yet been approved.

## Approved rule

A rule that has passed the configured human review state and deterministic validations for release.

## Parameter

A legislative/policy value used by rules that may change by date or other dimensions, such as a threshold, rate, or amount.

## Variable

An input or computed property associated with an entity/context.

## Entity

A person, household, organization, or other subject/group about which the rules calculate.

## Expression AST

A structured syntax tree representing logic/arithmetic. RuleWeaver does not store arbitrary executable code as its canonical expression representation.

## Effective period

The date/time interval in which a rule or parameter value applies.

## Exception

A rule that changes/disables/overrides another rule under explicit conditions.

## Ambiguity

A source interpretation problem with multiple plausible meanings or insufficient information. It can block executable approval.

## Human judgment required

A concept the system intentionally refuses to resolve deterministically because the policy/law requires discretion/context or the project does not support faithful computation.

## Policy-intent test

A test scenario approved/derived independently from the implementation, representing intended rule behavior.

## Generated test

A test produced mechanically or by an LLM from rule structure—for example threshold boundaries or date transitions. Useful, but not independent evidence of policy intent.

## Provenance

Information describing where an artifact came from, what activity generated/changed it, and who/what was responsible.

## Diagnostic

A structured compiler/validator message with stable code, severity, location, and details.

## Adapter

A component translating approved canonical IR into an external runtime or standard representation.

## OpenFisca

An open-source engine/framework for modeling tax and benefit systems using entities, variables, formulas, parameters, periods, and tests.

## Catala

A domain-specific programming language designed for high-assurance executable implementations of tax/social-benefit legislation with close legal-text/code correspondence.

## Akoma Ntoso

An OASIS legal document standard for structured legislative/parliamentary/judicial documents and metadata.

## LegalRuleML

An OASIS standard for representing legal norms and rules with richer legal semantics.

## W3C PROV

A W3C provenance model based on entities, activities, agents, and their relationships.

## Differential testing

Running the same scenario against the RuleWeaver reference evaluator and an adapter target to detect semantic mismatches.

## Semantic diff

A comparison of rule meaning/parameters/dependencies between versions, not merely textual line differences.

## Stale rule

An approved rule whose supporting source changed and therefore requires re-evaluation/review.

## Abstention

A deliberate compiler result such as unknown, ambiguous, unsupported, or human-judgment-required instead of guessing.
