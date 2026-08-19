"""Who a reviewer is.

The audit log's entire value is the answer to "who approved this rule, on what version of
the source". A reviewer field the client can set makes the log a record of what someone
typed, which is worth nothing in front of a regulator and worse than nothing in front of a
court — it looks like evidence.

Three resolvers, and the default is now the one that fails closed:

`SignedTokenResolver` verifies an HMAC-signed session token. The signature is over the
reviewer id and an expiry, compared in constant time. No dependency beyond the standard
library, which matters: an identity control that needs a package nobody installed is an
identity control nobody uses.

`TrustedProxyResolver` accepts a header set by an authenticating proxy — an SSO gateway,
oauth2-proxy, an ingress with OIDC. This is how most real deployments authenticate, and
refusing to support it would push people back to the insecure resolver. It requires an
explicit list of peers it will believe, because a header is only trustworthy if nothing
else can reach the application.

`InsecureReviewerResolver` remains for local work and says what it is. It is no longer the
default: `resolver_from_env` returns it only when a deployment explicitly asks for it.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time

from fastapi import HTTPException, Request

SESSION_COOKIE = "rw_session"
DEFAULT_TTL_SECONDS = 8 * 60 * 60

# Environment variables, named here so an operator can find all of them in one place.
ENV_SECRET = "RULEWEAVER_SESSION_SECRET"
ENV_TRUSTED_HEADER = "RULEWEAVER_TRUSTED_HEADER"
ENV_TRUSTED_PEERS = "RULEWEAVER_TRUSTED_PEERS"
ENV_ALLOW_INSECURE = "RULEWEAVER_ALLOW_INSECURE_REVIEWER"


class IdentityNotConfigured(Exception):
    """No identity provider is configured, and none may be guessed."""

    def __init__(self) -> None:
        super().__init__(
            "the reviewer application has no identity provider configured.\n"
            f"  Set {ENV_SECRET} to sign session tokens, or\n"
            f"  set {ENV_TRUSTED_HEADER} and {ENV_TRUSTED_PEERS} to trust an "
            "authenticating proxy, or\n"
            f"  set {ENV_ALLOW_INSECURE}=1 for local work only.\n"
            "Refusing to start rather than recording approvals against an identity "
            "anyone can claim."
        )


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def mint_token(reviewer: str, secret: str, *, ttl: int = DEFAULT_TTL_SECONDS,
               issued_at: float | None = None) -> str:
    """Issue a session token for `reviewer`.

    The expiry is inside the signed payload rather than beside it. A token whose lifetime
    the holder can edit does not expire.
    """
    if "|" in reviewer:
        raise ValueError("a reviewer id may not contain '|' — it separates the fields")
    expires = int((issued_at if issued_at is not None else time.time()) + ttl)
    payload = f"{reviewer}|{expires}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest()
    return f"{_b64(payload.encode())}.{_b64(signature)}"


class SignedTokenResolver:
    """Reads the reviewer from an HMAC-signed token in a cookie or bearer header."""

    def __init__(self, secret: str, *, cookie: str = SESSION_COOKIE) -> None:
        if not secret or len(secret) < 32:
            raise ValueError(
                "the session secret must be at least 32 characters. A short secret is "
                "brute-forceable, and the thing it protects is the approval record.")
        self._secret = secret.encode()
        self._cookie = cookie

    def verify(self, token: str) -> str:
        try:
            encoded_payload, encoded_signature = token.split(".", 1)
            payload = _unb64(encoded_payload)
            signature = _unb64(encoded_signature)
        except Exception as exc:
            raise HTTPException(401, "malformed session token") from exc

        expected = hmac.new(self._secret, payload, hashlib.sha256).digest()
        # Constant time: a comparison that returns early leaks the signature one byte at
        # a time to anyone who can measure it.
        if not hmac.compare_digest(signature, expected):
            raise HTTPException(401, "session token signature does not verify")

        try:
            reviewer, expires = payload.decode().rsplit("|", 1)
            deadline = int(expires)
        except Exception as exc:
            raise HTTPException(401, "malformed session payload") from exc

        if time.time() > deadline:
            raise HTTPException(401, "session token has expired")
        if not reviewer:
            raise HTTPException(401, "session token names no reviewer")
        return reviewer

    def __call__(self, request: Request) -> str:
        authorization = request.headers.get("Authorization", "")
        if authorization.lower().startswith("bearer "):
            return self.verify(authorization[7:].strip())
        token = request.cookies.get(self._cookie)
        if not token:
            raise HTTPException(401, "no session token")
        return self.verify(token)


class TrustedProxyResolver:
    """Accepts an identity header, but only from a peer on the trusted list.

    The list is not optional. A header is trustworthy exactly when the application cannot
    be reached except through the thing that sets it, and that is a deployment property
    the application cannot verify on its own — so it verifies the next best thing, and
    refuses everything else.
    """

    def __init__(self, header: str, trusted_peers: list[str]) -> None:
        if not trusted_peers:
            raise ValueError(
                "TrustedProxyResolver needs at least one trusted peer address. Without "
                "one, any client that can reach the port can set the header.")
        self._header = header
        self._trusted = set(trusted_peers)

    def __call__(self, request: Request) -> str:
        peer = request.client.host if request.client else None
        if peer not in self._trusted:
            # Deliberately not naming the header. A caller that is not the proxy has no
            # business learning which header would have worked.
            raise HTTPException(403, "requests are only accepted from the authenticating "
                                     "proxy")
        reviewer = request.headers.get(self._header)
        if not reviewer:
            raise HTTPException(401, "the proxy did not supply a reviewer identity")
        return reviewer


class InsecureReviewerResolver:
    """Reads the reviewer from a header. **Not fit for deployment.**

    Present so the application runs locally without an identity provider wired up. It
    warns on construction because an audit log whose reviewer field the client can set is
    not an audit log, and that failure is otherwise silent.
    """

    def __init__(self) -> None:
        import warnings

        warnings.warn(
            "InsecureReviewerResolver trusts the X-Reviewer header. Anyone can claim to "
            "be anyone. Use SignedTokenResolver or TrustedProxyResolver in any "
            "deployment — the audit log's value depends entirely on this field being "
            "trustworthy.",
            RuntimeWarning,
            stacklevel=2,
        )

    def __call__(self, request: Request) -> str:
        reviewer = request.headers.get("X-Reviewer") or request.cookies.get("reviewer")
        if not reviewer:
            raise HTTPException(401, "no reviewer identity")
        return reviewer


def resolver_from_env(env: dict[str, str] | None = None):
    """Pick a resolver from the environment, failing closed.

    The old default was the insecure resolver, which meant a deployment that forgot to
    configure identity still started, still served, and still recorded approvals — just
    against a name the client chose. Nothing announced the problem except a warning in a
    log nobody reads. Now that configuration is a startup failure.
    """
    env = env if env is not None else dict(os.environ)

    secret = env.get(ENV_SECRET)
    if secret:
        return SignedTokenResolver(secret)

    header = env.get(ENV_TRUSTED_HEADER)
    if header:
        peers = [p.strip() for p in env.get(ENV_TRUSTED_PEERS, "").split(",") if p.strip()]
        return TrustedProxyResolver(header, peers)

    if env.get(ENV_ALLOW_INSECURE) in ("1", "true", "yes"):
        return InsecureReviewerResolver()

    raise IdentityNotConfigured()
