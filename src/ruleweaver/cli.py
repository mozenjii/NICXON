"""Command line interface.

    ruleweaver validate   examples/snap/rules.json
    ruleweaver evaluate   examples/snap/rules.json examples/snap/scenarios/baseline.json
    ruleweaver boundaries examples/snap/rules.json examples/snap/scenarios/baseline.json
    ruleweaver approvals  examples/snap/rules.json
    ruleweaver ingest     examples/snap/sources/manifest.json
    ruleweaver extract    examples/snap/sources/manifest.json examples/snap/rules.json
    ruleweaver schema

Exit codes: 0 success, 1 validation or approval failed, 2 bad usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

from . import InvalidPackage, load
from .approval import approved_subset, check
from .ingest import CorpusError, load_corpus
from .ir import RulePackage
from .runtime import Context, Evaluator, ParameterTable
from .diff import analyse, compare
from .testgen import generate
from .verify import validate


def _decimals(mapping: dict) -> dict:
    """Numeric-looking strings become Decimal; everything else is left alone."""
    out = {}
    for k, v in mapping.items():
        if isinstance(v, str):
            try:
                out[k] = Decimal(v)
                continue
            except Exception:
                pass
        out[k] = v
    return out


def _scenario(path: Path) -> tuple[Context, dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    overrides: dict[str, dict] = {}
    for entry in doc.get("parameters", []):
        at = entry.get("at", {})
        key = tuple(str(at[d]) for d in sorted(at))
        overrides.setdefault(entry["id"], {})[key] = Decimal(str(entry["value"]))
    ctx = Context(
        household=_decimals(doc.get("household", {})),
        members=[_decimals(m) for m in doc.get("members", [])],
        on_date=doc.get("on_date", "2026-01-01"),
    )
    return ctx, overrides


def _review_log(database: str | None):
    """The review log, or an explanation of why it cannot be read.

    SQLAlchemy lives in the `review` extra, so a deployment that only executes rules may
    not have it. That is a legitimate configuration — but it is not a licence to skip the
    gate, so this reports the missing dependency rather than defaulting to "approved".
    """
    try:
        from .review.store import ReviewStore, build_engine
    except ImportError as exc:
        print(f"cannot read the review log: {exc}", file=sys.stderr)
        print('  pip install "ruleweaver[review]"', file=sys.stderr)
        raise SystemExit(1)

    try:
        return ReviewStore(build_engine(database)).load_log()
    except Exception as exc:
        # An unreachable log is not an empty log. Failing here with a readable message
        # beats a driver traceback, and beats the alternative of treating "no approvals
        # found" as "no approvals needed".
        print(f"cannot open the review log: {exc.__class__.__name__}: {exc}",
              file=sys.stderr)
        print("  the gate cannot be evaluated, so nothing was executed", file=sys.stderr)
        raise SystemExit(1)


def _load_or_exit(path: str, *, verify: bool) -> RulePackage:
    try:
        return load(path, verify=verify)
    except InvalidPackage as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)


def _corpus_or_exit(manifest: str | None, *, verify: bool = True):
    if manifest is None:
        return None
    try:
        return load_corpus(manifest, verify=verify)
    except CorpusError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)


def cmd_validate(args) -> int:
    package = RulePackage.model_validate(
        json.loads(Path(args.package).read_text(encoding="utf-8")))
    corpus = _corpus_or_exit(args.sources)
    report = validate(package, corpus=corpus)
    print(report)
    if report.errors:
        print(f"\n{len(report.errors)} error(s) — package is not evaluable", file=sys.stderr)
        return 1
    warnings = [d for d in report.diagnostics if d.severity == "warning"]
    print(f"\nok — {len(package.rules)} rules, {len(warnings)} warning(s)")
    return 0


def cmd_evaluate(args) -> int:
    package = _load_or_exit(args.package, verify=not args.no_verify)

    if args.require_approval:
        subset, report = approved_subset(package, _review_log(args.database))
        if not report.ok:
            print(f"approval gate: {report}", file=sys.stderr)
            if not args.partial:
                print("nothing was evaluated. Review the rules above, or pass "
                      "--partial to evaluate the approved subset and read "
                      "unknown as 'no approved rule decides this'.",
                      file=sys.stderr)
                return 1
            print("evaluating the approved subset — determinations resting on "
                  "the rules above will be unknown", file=sys.stderr)
        package = subset

    ctx, overrides = _scenario(Path(args.scenario))
    Evaluator(package, ParameterTable(package, overrides=overrides)).run(ctx)

    print("outputs")
    for key in sorted(ctx.household):
        print(f"  {key:52} {ctx.household[key]}")
    if args.trace:
        print("\ntrace")
        for step in ctx.trace:
            print(f"  {step}")
    return 0


def cmd_boundaries(args) -> int:
    package = _load_or_exit(args.package, verify=not args.no_verify)
    ctx, overrides = _scenario(Path(args.scenario))
    evaluator = Evaluator(package, ParameterTable(package, overrides=overrides))
    observe = args.observe or []
    cases = generate(package, ctx, evaluator, observe=observe)

    print(f"{len(cases)} generated boundary case(s)")
    print("these are diagnostic, not policy intent — they record what the package does\n")
    for case in cases:
        seen = "  ".join(f"{k.split('.')[-1]}={v}" for k, v in case.observed.items())
        print(f"  {case.position:6} {case.probe.split('.')[-1]:26} = {case.value:>10}   {seen}")
    return 0


def cmd_diff(args) -> int:
    before = _load_or_exit(args.before, verify=not args.no_verify)
    after = _load_or_exit(args.after, verify=not args.no_verify)
    report = compare(before, after)
    print(report)

    if not args.scenario:
        return 0
    if not report.semantic:
        print("\nno semantic change, so no determination can move")
        return 0

    scenarios = {}
    for path in args.scenario:
        ctx, overrides = _scenario(Path(path))
        scenarios[Path(path).stem] = (ctx, overrides)

    observe = args.observe or ["var.household.is_income_eligible"]
    print()
    print(analyse(before, after, report, scenarios, observe))
    return 0


def cmd_ingest(args) -> int:
    """Verify a source corpus and report what was parsed out of it."""
    corpus = _corpus_or_exit(args.manifest, verify=not args.no_verify)

    if args.clause:
        for document in corpus.documents.values():
            clause = document.clause(args.clause) or document.by_citation(args.clause)
            if clause is not None:
                print(f"{clause.citation}   [{clause.node_id}] "
                      f"chars {clause.start_char}-{clause.end_char}")
                print()
                print(document.subtree_text(clause.node_id))
                return 0
        print(f"no clause {args.clause!r} in this corpus", file=sys.stderr)
        return 1

    print(corpus)
    rights = corpus.rights.get("status")
    if rights:
        print()
        print(f"rights: {rights} — {corpus.rights.get('basis', '')}")
    if corpus.notes:
        print()
        print(f"{len(corpus.notes)} parse note(s)")
        for note in corpus.notes[:20]:
            print(f"  {note}")
    return 0


def cmd_extract(args) -> int:
    """Compile a source corpus into a candidate rule package.

    Writes the candidate beside a run record. The two belong together: a package nobody can
    trace back to the corpus digests, prompt versions and decoding settings that produced it
    cannot be reproduced, and an extraction nobody can reproduce cannot be argued about.
    """
    from .compile.pipeline import compile_corpus
    from .compile.providers import UnknownProvider, build
    from .models.base import MissingCredentials, ProviderError

    corpus = _corpus_or_exit(args.manifest)
    base = _load_or_exit(args.vocabulary, verify=not args.no_verify)

    replay = None
    if args.replay:
        replay = json.loads(Path(args.replay).read_text(encoding="utf-8"))

    try:
        provider, settings = build(args.provider, model=args.model, responses=replay)
    except UnknownProvider as exc:
        print(str(exc), file=sys.stderr)
        return 2

    if args.provider == "recorded" and replay is None:
        print("the recorded provider replays saved responses and has none. Pass "
              "--replay to supply them, or --provider anthropic / --provider openai "
              "to call a model.", file=sys.stderr)
        return 2
    if args.provider == "recorded":
        print(f"replaying {len(replay)} recorded response(s): no model will be called.",
              file=sys.stderr)

    print(f"compiling {corpus.corpus_id} with {args.provider}/{settings.model}",
          file=sys.stderr)
    try:
        candidate, run, report = compile_corpus(
            corpus, provider=provider, settings=settings, base=base,
            source_ids=args.source or None, limit=args.limit)
    except MissingCredentials as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except ProviderError as exc:
        print(f"the provider failed: {exc}", file=sys.stderr)
        return 1

    print()
    print(run)
    if report.diagnostics:
        print()
        print(report)

    if args.out:
        out = Path(args.out)
        out.write_text(
            json.dumps(candidate.model_dump(mode="json", by_alias=True, exclude_none=True),
                       indent=2, ensure_ascii=False),
            encoding="utf-8")
        record = out.with_suffix(".run.json")
        record.write_text(json.dumps(run.as_dict(), indent=2), encoding="utf-8")
        print()
        print(f"candidate:  {out}")
        print(f"run record: {record}")
        print("every rule is unreviewed — run 'ruleweaver review' before executing it")

    # A run that proposed nothing is not a success, whatever the exit code of the model
    # calls. Reporting it as one hides a broken prompt behind an empty queue.
    return 0 if run.usable else 1


def cmd_approvals(args) -> int:
    """Report which rules may execute, and why the rest may not."""
    package = _load_or_exit(args.package, verify=not args.no_verify)
    log = _review_log(args.database)
    report = check(package, log)

    print(f"{args.package}")
    print(report)
    if report.blocked:
        print()
        for rule_id in sorted(report.blocked):
            latest = log.latest_for(rule_id)
            who = f"  last: {latest.reviewer} {latest.decision.value}" if latest else ""
            print(f"  {report.blocked[rule_id].value:28} {rule_id}{who}")
    return 0 if report.ok else 1


def cmd_review(args) -> int:
    """Serve the reviewer application."""
    try:
        import uvicorn

        from .review.app import create_app
        from .review.store import ReviewStore, build_engine
    except ImportError as exc:
        print(f"the review extra is not installed: {exc}\n"
              f'  pip install "ruleweaver[review]"', file=sys.stderr)
        return 1

    package = _load_or_exit(args.package, verify=not args.no_verify)
    store = ReviewStore(build_engine(args.database))
    app = create_app(package, store, seed_rate=args.seed_rate, salt=args.salt)

    print(f"reviewing {len(package.rules)} rules from {args.package}")
    print(f"audit log: {args.database or 'sqlite:///ruleweaver-review.db'}")
    print(f"http://{args.host}:{args.port}\n")
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


def cmd_schema(args) -> int:
    print(json.dumps(RulePackage.model_json_schema(), indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ruleweaver", description=__doc__.split("\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("validate", help="check a rule package and report diagnostics")
    p.add_argument("package")
    p.add_argument("--sources", default=None,
                   help="source manifest; also checks that every citation resolves")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("extract", help="compile a source corpus into candidate rules")
    p.add_argument("manifest", help="source manifest to compile from")
    p.add_argument("vocabulary",
                   help="rule package supplying the controlled vocabulary (ADR-018)")
    p.add_argument("--provider", default="recorded",
                   choices=["recorded", "anthropic", "openai"])
    p.add_argument("--model", default=None, help="override the provider's default model")
    p.add_argument("--source", action="append", help="restrict to one source id")
    p.add_argument("--limit", type=int, default=None, help="stop after N clauses")
    p.add_argument("--replay", default=None,
                   help="JSON array of recorded responses, for the recorded provider")
    p.add_argument("--out", default=None, help="write the candidate package here")
    p.add_argument("--no-verify", action="store_true")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("ingest", help="verify and parse a source corpus")
    p.add_argument("manifest")
    p.add_argument("--clause", default=None, help="print one clause by citation or node id")
    p.add_argument("--no-verify", action="store_true",
                   help="parse without checking the recorded digests")
    p.set_defaults(func=cmd_ingest)

    p = sub.add_parser("evaluate", help="evaluate a scenario against a rule package")
    p.add_argument("package")
    p.add_argument("scenario")
    p.add_argument("--trace", action="store_true", help="show which rule produced each value")
    p.add_argument("--require-approval", action="store_true",
                   help="refuse to execute rules that have not passed human review")
    p.add_argument("--partial", action="store_true",
                   help="with --require-approval, evaluate the approved subset anyway")
    p.add_argument("--database", default=None, help="review log to read approvals from")
    p.add_argument("--no-verify", action="store_true", help="skip validation (testing only)")
    p.set_defaults(func=cmd_evaluate)

    p = sub.add_parser("approvals", help="report which rules have passed human review")
    p.add_argument("package")
    p.add_argument("--database", default=None,
                   help="SQLAlchemy URL; defaults to RULEWEAVER_DATABASE_URL or local SQLite")
    p.add_argument("--no-verify", action="store_true")
    p.set_defaults(func=cmd_approvals)

    p = sub.add_parser("boundaries", help="generate boundary cases around every threshold")
    p.add_argument("package")
    p.add_argument("scenario")
    p.add_argument("--observe", action="append", help="variable id to report per case")
    p.add_argument("--no-verify", action="store_true")
    p.set_defaults(func=cmd_boundaries)

    p = sub.add_parser("diff", help="compare two versions and report amendment impact")
    p.add_argument("before")
    p.add_argument("after")
    p.add_argument("--scenario", action="append", help="scenario file to re-run on both versions")
    p.add_argument("--observe", action="append", help="variable id to compare")
    p.add_argument("--no-verify", action="store_true")
    p.set_defaults(func=cmd_diff)

    p = sub.add_parser("review", help="serve the reviewer application")
    p.add_argument("package")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--database", default=None,
                   help="SQLAlchemy URL; defaults to RULEWEAVER_DATABASE_URL or local SQLite")
    p.add_argument("--seed-rate", type=float, default=0.1,
                   help="fraction of rules that carry a deliberately seeded fault")
    p.add_argument("--salt", default="", help="rotate per review campaign")
    p.add_argument("--no-verify", action="store_true")
    p.set_defaults(func=cmd_review)

    p = sub.add_parser("schema", help="print the JSON Schema for a rule package")
    p.set_defaults(func=cmd_schema)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
