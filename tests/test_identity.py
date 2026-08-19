"""Reviewer identity.

The audit log is only worth what its reviewer field is worth, so these tests are mostly
about forgery: a tampered signature, an edited expiry, a header set by someone who is not
the proxy. A resolver that accepts any of those produces a record that looks like evidence
and is not.
"""

from __future__ import annotations

import time

import pytest
from fastapi import HTTPException

from ruleweaver.review import identity
from ruleweaver.review.identity import (
    IdentityNotConfigured,
    InsecureReviewerResolver,
    SignedTokenResolver,
    TrustedProxyResolver,
    mint_token,
)

SECRET = "a" * 48
OTHER = "b" * 48


class FakeRequest:
    """Enough of a request for a resolver: headers, cookies, and a peer address."""

    def __init__(self, *, headers=None, cookies=None, peer=None):
        self.headers = headers or {}
        self.cookies = cookies or {}
        self.client = type("Client", (), {"host": peer})() if peer else None


class TestSignedTokens:
    def test_a_minted_token_round_trips(self):
        resolver = SignedTokenResolver(SECRET)
        assert resolver.verify(mint_token("alice@example.gov", SECRET)) == "alice@example.gov"

    def test_a_token_signed_with_another_secret_is_rejected(self):
        resolver = SignedTokenResolver(SECRET)
        with pytest.raises(HTTPException, match="signature does not verify"):
            resolver.verify(mint_token("alice", OTHER))

    def test_a_tampered_payload_is_rejected(self):
        """Editing the reviewer id in a token must not silently work."""
        token = mint_token("alice", SECRET)
        payload, signature = token.split(".", 1)
        forged = identity._b64(identity._unb64(payload).replace(b"alice", b"mallo"))
        with pytest.raises(HTTPException, match="signature does not verify"):
            SignedTokenResolver(SECRET).verify(f"{forged}.{signature}")

    def test_an_expiry_the_holder_edits_does_not_extend_the_token(self):
        """The expiry is inside the signed payload; moving it breaks the signature."""
        token = mint_token("alice", SECRET, ttl=-1)
        payload, signature = token.split(".", 1)
        raw = identity._unb64(payload).decode()
        name, _ = raw.rsplit("|", 1)
        extended = identity._b64(f"{name}|{int(time.time()) + 9999}".encode())
        with pytest.raises(HTTPException, match="signature does not verify"):
            SignedTokenResolver(SECRET).verify(f"{extended}.{signature}")

    def test_an_expired_token_is_rejected(self):
        with pytest.raises(HTTPException, match="expired"):
            SignedTokenResolver(SECRET).verify(mint_token("alice", SECRET, ttl=-1))

    def test_malformed_tokens_are_rejected_rather_than_crashing(self):
        resolver = SignedTokenResolver(SECRET)
        for token in ("", "no-dot", "!!!.???", "a.b.c"):
            with pytest.raises(HTTPException):
                resolver.verify(token)

    def test_a_short_secret_is_refused_at_construction(self):
        """Failing at startup beats failing quietly for the life of the deployment."""
        with pytest.raises(ValueError, match="at least 32 characters"):
            SignedTokenResolver("short")

    def test_a_reviewer_id_cannot_smuggle_the_field_separator(self):
        with pytest.raises(ValueError, match=r"may not contain"):
            mint_token("alice|99999999999", SECRET)

    def test_a_bearer_header_is_accepted(self):
        resolver = SignedTokenResolver(SECRET)
        request = FakeRequest(headers={"Authorization": f"Bearer {mint_token('bo', SECRET)}"})
        assert resolver(request) == "bo"

    def test_a_cookie_is_accepted(self):
        resolver = SignedTokenResolver(SECRET)
        request = FakeRequest(cookies={identity.SESSION_COOKIE: mint_token("bo", SECRET)})
        assert resolver(request) == "bo"

    def test_no_token_at_all_is_rejected(self):
        with pytest.raises(HTTPException, match="no session token"):
            SignedTokenResolver(SECRET)(FakeRequest())


class TestTrustedProxy:
    def test_the_proxy_identity_is_accepted(self):
        resolver = TrustedProxyResolver("X-Forwarded-User", ["10.0.0.5"])
        request = FakeRequest(headers={"X-Forwarded-User": "carol"}, peer="10.0.0.5")
        assert resolver(request) == "carol"

    def test_another_client_setting_the_header_is_refused(self):
        """The whole control: the header means nothing from an untrusted peer."""
        resolver = TrustedProxyResolver("X-Forwarded-User", ["10.0.0.5"])
        request = FakeRequest(headers={"X-Forwarded-User": "mallory"}, peer="10.0.0.9")
        with pytest.raises(HTTPException) as exc:
            resolver(request)
        assert exc.value.status_code == 403

    def test_the_refusal_does_not_name_the_header(self):
        """A caller that is not the proxy has no business learning what would have worked."""
        resolver = TrustedProxyResolver("X-Forwarded-User", ["10.0.0.5"])
        with pytest.raises(HTTPException) as exc:
            resolver(FakeRequest(peer="10.0.0.9"))
        assert "X-Forwarded-User" not in str(exc.value.detail)

    def test_a_trusted_proxy_that_supplies_nothing_is_rejected(self):
        resolver = TrustedProxyResolver("X-Forwarded-User", ["10.0.0.5"])
        with pytest.raises(HTTPException, match="did not supply"):
            resolver(FakeRequest(peer="10.0.0.5"))

    def test_an_empty_trust_list_is_refused_at_construction(self):
        with pytest.raises(ValueError, match="at least one trusted peer"):
            TrustedProxyResolver("X-Forwarded-User", [])


class TestResolverFromEnv:
    def test_a_secret_selects_signed_tokens(self):
        resolver = identity.resolver_from_env({identity.ENV_SECRET: SECRET})
        assert isinstance(resolver, SignedTokenResolver)

    def test_a_header_and_peers_select_the_proxy_resolver(self):
        resolver = identity.resolver_from_env({
            identity.ENV_TRUSTED_HEADER: "X-Forwarded-User",
            identity.ENV_TRUSTED_PEERS: "10.0.0.5, 10.0.0.6",
        })
        assert isinstance(resolver, TrustedProxyResolver)

    def test_the_insecure_resolver_needs_an_explicit_opt_in(self):
        with pytest.warns(RuntimeWarning):
            resolver = identity.resolver_from_env({identity.ENV_ALLOW_INSECURE: "1"})
        assert isinstance(resolver, InsecureReviewerResolver)

    def test_nothing_configured_fails_closed(self):
        """Previously this silently returned the insecure resolver."""
        with pytest.raises(IdentityNotConfigured) as exc:
            identity.resolver_from_env({})
        assert identity.ENV_SECRET in str(exc.value)

    def test_a_trusted_header_without_peers_is_an_error_not_a_downgrade(self):
        with pytest.raises(ValueError, match="trusted peer"):
            identity.resolver_from_env({identity.ENV_TRUSTED_HEADER: "X-Forwarded-User"})
