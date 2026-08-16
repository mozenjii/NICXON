# 07 — Data, Benchmark, and Evaluation Plan

## Why the benchmark matters

A strong public benchmark may become one of RuleWeaver's most important contributions.

Without a benchmark, “the LLM successfully converted this policy” is mostly a demo claim.

The benchmark should evaluate separate compiler abilities rather than only end-to-end text similarity.

## First benchmark scope

Start with a narrow corpus of computable tax/public-benefit rules.

Requirements for the first corpus:

- authoritative source available;
- clear version/date;
- enough thresholds/definitions/exceptions to be meaningful;
- manageable domain size;
- legal/reuse status understood;
- ideally some existing worked examples or calculators for validation.

Do not select a huge national tax code as the first corpus.

## Dataset layers

### Layer A — source manifest

Fields:

```text
source_id
origin_url/origin_note
retrieval_date
hash
jurisdiction
publication_date
effective_date
license/reuse_status
document_type
language
```

### Layer B — source structure gold

- sections;
- paragraphs;
- table cells where needed;
- stable source IDs;
- cross-references.

### Layer C — semantic annotation

- definition spans;
- parameter spans;
- effective dates;
- rule-bearing clauses;
- exceptions;
- non-computable/human-judgment clauses;
- source-to-IR mappings.

### Layer D — gold Rule IR

Expert-reviewed structured representation.

### Layer E — policy-intent tests

Human/source-derived scenario tests independent of model output.

### Layer F — ambiguity cases

Annotated clauses where:

- interpretation is genuinely ambiguous;
- external source is needed;
- the concept is intentionally discretionary;
- multiple scopes are plausible.

## Benchmark task families

### T1 Clause classification

Metrics:

- macro precision/recall/F1;
- per-class precision/recall;
- multi-label performance.

### T2 Definition and parameter extraction

Metrics:

- span F1;
- normalized value accuracy;
- unit/currency accuracy;
- effective-date accuracy.

### T3 Rule structure generation

Evaluate semantic components instead of raw string match:

- operator accuracy;
- variable/reference accuracy;
- boolean structure;
- parameter link accuracy;
- exception attachment;
- effective period.

### T4 Source alignment

Metrics:

- exact/overlap span accuracy;
- citation precision;
- unsupported rule-element rate.

### T5 Ambiguity/abstention

Metrics:

- blocking ambiguity recall;
- false ambiguity rate;
- unsupported-feature detection;
- unsafe forced-interpretation rate.

### T6 Executable behavior

Run gold scenarios against:

- gold IR;
- model-proposed reviewed/unreviewed IR;
- adapter outputs.

Metric:

- outcome agreement;
- trace agreement where defined.

### T7 Change impact

Given source v1 and v2:

- changed-rule recall;
- changed-parameter recall;
- downstream impact recall;
- affected-test recall;
- false affected-object rate.

## Critical metrics

### Unsupported semantic assertion rate

Percentage of generated semantic claims with no valid source support.

This is one of the most important metrics.

### Dangerous operator error rate

Examples:

- `<` vs `<=`;
- `and` vs `or`;
- inclusion vs exclusion;
- before vs after date;
- exception attached to the wrong base rule.

Track these separately from generic structural errors.

### Review effort

Measure:

- time per rule;
- edits per rule;
- percent accepted unchanged;
- percent rejected;
- percent marked ambiguous;
- comparison with manual-from-scratch implementation.

## Test generation evaluation

Generated tests should be evaluated by **fault detection**, not beauty.

Create mutations such as:

- flip `<` to `<=`;
- change `and` to `or`;
- move a threshold by one unit;
- remove an exception;
- shift effective date;
- reference wrong parameter.

Measure how often generated + human tests catch them.

## Data licensing

For each source, explicitly record redistribution rights.

If source redistribution is uncertain:

- distribute source URL/identifier;
- content hash;
- scripts to obtain it where lawful;
- annotations by source offsets/IDs;
- do not casually republish source text.

For annotations created by the project, choose a clear open data license after review.

## Evaluation splits

Avoid random clause splits that leak nearly identical rules across train/dev/test.

Prefer splitting by:

- program;
- jurisdiction;
- source chapter;
- amendment/version;
- rule family.

A meaningful generalization benchmark should test unseen rule structures or jurisdictions.

## Reproducibility record

Every benchmark report should record:

```text
git commit
IR schema version
source manifest version
model/provider
model version/identifier
prompt versions
retrieval configuration
random seed where relevant
runtime versions
per-example outputs
metric implementation version
```

## Suggested public benchmark release sequence

### Bench v0

- fictional policies only;
- validates evaluator/test infrastructure.

### Bench v0.1

- one real authoritative policy corpus;
- 100–300 meaningful rule clauses depending on complexity.

### Bench v0.2

- second jurisdiction/program;
- tests generalization.

### Bench v1

- multiple jurisdictions/programs;
- amendment/change-impact tasks;
- public leaderboard with reproducible submissions.
