"""The reviewer application.

One FastAPI process, server-rendered, no JavaScript build step. The whole surface is a
queue, a side-by-side view of clause and rule, and a decision form — which is what the
work actually is for a policy reviewer.

Two design choices carry weight:

**Reviewer identity is authenticated, never self-declared.** The audit log's value is
entirely in "who approved this", so identity resolution is a pluggable dependency rather
than a form field. The default implementation is deliberately unfit for deployment and
says so at startup.

**Review duration is measured in the browser.** The number ADR-021 needs is how long a
human looked at the rule, not how long the request took. The template stamps a monotonic
clock when the rule renders and submits the delta.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..approval import rule_digest, source_digest
from ..ir.rules import RulePackage
from ..verify import validate
from .adversarial import AdversarialQueue
from .decisions import Decision, ReviewEvent, Status
from .store import ReviewStore

TEMPLATES = Path(__file__).parent / "templates"


class InsecureReviewerResolver:
    """Reads the reviewer from a header. **Not fit for deployment.**

    Present so the app runs locally without an identity provider wired up. It warns on
    construction because an audit log whose reviewer field can be set by the client is
    not an audit log, and that failure is silent otherwise.
    """

    def __init__(self) -> None:
        import warnings

        warnings.warn(
            "InsecureReviewerResolver trusts the X-Reviewer header. Anyone can claim to "
            "be anyone. Replace it with a real identity provider before deploying — the "
            "audit log's value depends entirely on this field being trustworthy.",
            RuntimeWarning,
            stacklevel=2,
        )

    def __call__(self, request: Request) -> str:
        reviewer = request.headers.get("X-Reviewer") or request.cookies.get("reviewer")
        if not reviewer:
            raise HTTPException(401, "no reviewer identity")
        return reviewer


def _rule(package: RulePackage, rule_id: str):
    rule = package.rule(rule_id)
    if rule is None:
        raise HTTPException(404, f"unknown rule: {rule_id}")
    return rule


def _rule_hash(package: RulePackage, rule_id: str) -> str:
    """The digest the runtime gate will check this approval against.

    Delegated to `approval` rather than computed here. The reviewer records a hash and the
    gate recomputes it; if the two ever disagreed, every approval would read as stale — or
    worse, a stale one would read as current.
    """
    return rule_digest(_rule(package, rule_id))


def _source_hash(package: RulePackage, rule_id: str) -> str:
    """Digest of the source spans a rule cites.

    Hashing the citations rather than the rule means an approval goes stale when the
    clause it rests on is re-fetched and differs — which is the case that matters and the
    one nobody remembers to check.
    """
    return source_digest(_rule(package, rule_id))


def create_app(
    package: RulePackage,
    store: ReviewStore,
    *,
    reviewer_resolver: Callable[[Request], str] | None = None,
    seed_rate: float = 0.1,
    salt: str = "",
) -> FastAPI:
    app = FastAPI(title="RuleWeaver review", docs_url=None, redoc_url=None)
    templates = Jinja2Templates(directory=str(TEMPLATES))
    resolve_reviewer = reviewer_resolver or InsecureReviewerResolver()
    report = validate(package)

    def current_queue() -> AdversarialQueue:
        return AdversarialQueue(store.load_log(), seed_rate=seed_rate, salt=salt)

    def status_of(rule_id: str) -> Status:
        return store.load_log().status(
            rule_id,
            rule_hash=_rule_hash(package, rule_id),
            source_hash=_source_hash(package, rule_id),
        )

    @app.get("/", response_class=HTMLResponse)
    def queue(request: Request):
        rows: list[dict[str, Any]] = [
            {
                "rule": rule,
                "status": status_of(rule.id),
                "diagnostics": [d for d in report.diagnostics if d.rule_id == rule.id],
            }
            for rule in package.rules
        ]
        # Unreviewed first — a queue sorted by id buries the work.
        order = {Status.UNREVIEWED: 0, Status.STALE: 1, Status.AMBIGUOUS: 2,
                 Status.HUMAN_JUDGMENT_REQUIRED: 3, Status.REJECTED: 4, Status.APPROVED: 5}
        rows.sort(key=lambda r: order.get(r["status"], 9))
        return templates.TemplateResponse(
            request, "queue.html",
            {"rows": rows, "package": package,
             "pending": sum(1 for r in rows if r["status"] is Status.UNREVIEWED)},
        )

    @app.get("/rule/{rule_id}", response_class=HTMLResponse)
    def detail(request: Request, rule_id: str):
        rule = package.rule(rule_id)
        if rule is None:
            raise HTTPException(404, f"unknown rule: {rule_id}")
        log = store.load_log()
        return templates.TemplateResponse(
            request, "detail.html",
            {
                "rule": rule,
                "package": package,
                "status": status_of(rule_id),
                "history": log.events_for(rule_id),
                "diagnostics": [d for d in report.diagnostics if d.rule_id == rule_id],
                "ambiguities": [a for a in package.ambiguities if rule_id in a.affects],
                "decisions": list(Decision),
            },
        )

    @app.post("/rule/{rule_id}/decide")
    def submit(
        request: Request,
        rule_id: str,
        decision: str = Form(...),
        note: str = Form(""),
        duration_seconds: float = Form(0.0),
    ):
        reviewer = resolve_reviewer(request)
        try:
            chosen = Decision(decision)
        except ValueError as exc:
            raise HTTPException(400, f"unknown decision: {decision}") from exc

        seeded = next((s for s in store.seeds() if s["rule_id"] == rule_id), None)

        try:
            event = ReviewEvent(
                rule_id=rule_id,
                reviewer=reviewer,
                decision=chosen,
                rule_hash=_rule_hash(package, rule_id),
                source_hash=_source_hash(package, rule_id),
                duration_seconds=duration_seconds or None,
                note=note or None,
                seeded_error_id=seeded["id"] if seeded else None,
            )
        except ValueError as exc:
            # A rejection without a reason. Send them back rather than storing a
            # decision the next reviewer cannot act on.
            raise HTTPException(400, str(exc)) from exc

        store.append(event)
        return RedirectResponse(f"/rule/{rule_id}", status_code=303)

    @app.get("/metrics", response_class=HTMLResponse)
    def metrics(request: Request):
        queue = current_queue()
        for seed in store.seeds():
            from .adversarial import SeededError

            queue.register(SeededError(
                id=seed["id"], rule_id=seed["rule_id"], description=seed["description"],
                mutated_rule=seed["mutated_rule"],
                expected_decision=Decision(seed["expected_decision"]),
                seeded_at=seed["seeded_at"],
            ))
        m = queue.metrics()
        intact, broken_at = store.verify_chain()
        return templates.TemplateResponse(
            request, "metrics.html",
            {"metrics": m, "warnings": m.warnings(),
             "chain_intact": intact, "broken_at": broken_at},
        )

    return app
