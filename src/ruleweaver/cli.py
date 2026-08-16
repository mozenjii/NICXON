"""Command line interface.

    ruleweaver validate   examples/snap/rules.json
    ruleweaver evaluate   examples/snap/rules.json examples/snap/scenarios/baseline.json
    ruleweaver boundaries examples/snap/rules.json examples/snap/scenarios/baseline.json
    ruleweaver schema

Exit codes: 0 success, 1 validation failed, 2 bad usage.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

from . import InvalidPackage, load
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


def _load_or_exit(path: str, *, verify: bool) -> RulePackage:
    try:
        return load(path, verify=verify)
    except InvalidPackage as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)


def cmd_validate(args) -> int:
    package = RulePackage.model_validate(
        json.loads(Path(args.package).read_text(encoding="utf-8")))
    report = validate(package)
    print(report)
    if report.errors:
        print(f"\n{len(report.errors)} error(s) — package is not evaluable", file=sys.stderr)
        return 1
    warnings = [d for d in report.diagnostics if d.severity == "warning"]
    print(f"\nok — {len(package.rules)} rules, {len(warnings)} warning(s)")
    return 0


def cmd_evaluate(args) -> int:
    package = _load_or_exit(args.package, verify=not args.no_verify)
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
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("evaluate", help="evaluate a scenario against a rule package")
    p.add_argument("package")
    p.add_argument("scenario")
    p.add_argument("--trace", action="store_true", help="show which rule produced each value")
    p.add_argument("--no-verify", action="store_true", help="skip validation (testing only)")
    p.set_defaults(func=cmd_evaluate)

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
