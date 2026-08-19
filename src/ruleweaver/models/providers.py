"""Concrete model providers.

Each adapter is thin on purpose: it translates a `Settings` into one vendor's request
shape, forces structured output against the caller's schema, and records run metadata.
No prompt logic lives here — prompts are versioned assets, and the guard fences untrusted
source text before it ever reaches a provider.

Credentials are read from the environment and never accepted as arguments. A key passed
as a parameter ends up in a stack trace, a log line, or a committed call site.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from typing import Any

from .base import (
    MissingCredentials,
    Proposal,
    ProviderError,
    RunMetadata,
    Settings,
    digest,
)
from .guard import guarded_context

# Models that reject sampling parameters outright. Sending `temperature` to one of these
# is a 400, not a silently ignored field, so the adapter drops them rather than failing
# a compilation over a knob the caller probably set out of habit.
_NO_SAMPLING = ("claude-opus-5", "claude-fable-5", "claude-mythos-5",
                "claude-opus-4-8", "claude-opus-4-7", "claude-sonnet-5")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _input_hashes(task: str, context: dict, schema: dict) -> dict[str, str]:
    return {"task": digest(task), "context": digest(context), "schema": digest(schema)}


class AnthropicProvider:
    """Claude via the official Anthropic SDK.

    Structured output uses `output_config.format`, which constrains the response to the
    caller's JSON Schema. That is what lets the compiler treat a proposal as data: an
    unparseable response is a provider failure, not something a downstream pass has to
    defend against.
    """

    name = "anthropic"
    env_var = "ANTHROPIC_API_KEY"

    def __init__(self, model: str = "claude-opus-5") -> None:
        self.model = model
        self._client: Any = None

    def _connect(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise ProviderError(
                "the anthropic package is not installed — pip install 'ruleweaver[anthropic]'"
            ) from exc
        # An unset ANTHROPIC_API_KEY does not mean there are no credentials: the SDK also
        # resolves ANTHROPIC_AUTH_TOKEN and an `ant auth login` profile. Construct the
        # client and let it resolve, rather than pre-checking one variable.
        try:
            self._client = anthropic.Anthropic()
        except Exception as exc:
            raise MissingCredentials(self.name, self.env_var) from exc
        return self._client

    def structured_generate(
        self, *, task: str, context: dict, schema: dict, settings: Settings,
        prompt_id: str, prompt_version: str,
    ) -> Proposal:
        import anthropic

        client = self._connect()
        safe_context, flags = guarded_context(context)

        request: dict[str, Any] = {
            "model": settings.model,
            "max_tokens": settings.max_tokens,
            "system": task,
            "messages": [{"role": "user", "content": json.dumps(safe_context, indent=2)}],
            "output_config": {"format": {"type": "json_schema", "schema": schema}},
        }
        if not settings.model.startswith(_NO_SAMPLING):
            if settings.temperature is not None:
                request["temperature"] = settings.temperature
            if settings.top_p is not None:
                request["top_p"] = settings.top_p

        try:
            response = client.messages.create(**request)
        except anthropic.RateLimitError as exc:
            raise ProviderError(f"rate limited: {exc}") from exc
        except anthropic.AuthenticationError as exc:
            raise MissingCredentials(self.name, self.env_var) from exc
        except anthropic.APIStatusError as exc:
            raise ProviderError(f"{self.name} returned {exc.status_code}: {exc.message}") from exc
        except anthropic.APIConnectionError as exc:
            raise ProviderError(f"could not reach {self.name}: {exc}") from exc

        if response.stop_reason == "refusal":
            raise ProviderError(
                "the model declined this request; treat the clause as needing human review"
            )

        raw = next((b.text for b in response.content if b.type == "text"), "")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"structured output was not valid JSON: {exc}") from exc

        return Proposal(
            data=data,
            raw=raw,
            injection_flags=flags,
            metadata=RunMetadata(
                provider=self.name,
                model=response.model,
                prompt_id=prompt_id,
                prompt_version=prompt_version,
                decoding=settings.as_dict(),
                requested_at=_now(),
                input_hashes=_input_hashes(task, context, schema),
                output_hash=digest(raw),
                finish_reason=response.stop_reason,
                usage={
                    "input_tokens": response.usage.input_tokens,
                    "output_tokens": response.usage.output_tokens,
                },
            ),
        )


class OpenAIProvider:
    """GPT via the official OpenAI SDK.

    Present so that ADR-016 is enforced by construction rather than by intention: a second
    provider makes vendor leakage into the compiler a compile-time failure instead of
    something noticed years later.
    """

    name = "openai"
    env_var = "OPENAI_API_KEY"

    def __init__(self, model: str = "gpt-5.2") -> None:
        self.model = model
        self._client: Any = None

    def _connect(self) -> Any:
        if self._client is not None:
            return self._client
        try:
            import openai
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise ProviderError(
                "the openai package is not installed — pip install 'ruleweaver[openai]'"
            ) from exc
        # Supports either an API key or an OAuth access token in the same variable.
        if not (os.environ.get(self.env_var) or os.environ.get("OPENAI_ACCESS_TOKEN")):
            raise MissingCredentials(self.name, self.env_var)
        self._client = openai.OpenAI()
        return self._client

    def structured_generate(
        self, *, task: str, context: dict, schema: dict, settings: Settings,
        prompt_id: str, prompt_version: str,
    ) -> Proposal:
        client = self._connect()
        safe_context, flags = guarded_context(context)

        try:
            response = client.chat.completions.create(
                model=settings.model,
                max_completion_tokens=settings.max_tokens,
                messages=[
                    {"role": "system", "content": task},
                    {"role": "user", "content": json.dumps(safe_context, indent=2)},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": "proposal", "schema": schema, "strict": True},
                },
            )
        except Exception as exc:  # the SDK's error tree differs by version
            raise ProviderError(f"{self.name} request failed: {exc}") from exc

        choice = response.choices[0]
        raw = choice.message.content or ""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ProviderError(f"structured output was not valid JSON: {exc}") from exc

        return Proposal(
            data=data,
            raw=raw,
            injection_flags=flags,
            metadata=RunMetadata(
                provider=self.name,
                model=response.model,
                prompt_id=prompt_id,
                prompt_version=prompt_version,
                decoding=settings.as_dict(),
                requested_at=_now(),
                input_hashes=_input_hashes(task, context, schema),
                output_hash=digest(raw),
                finish_reason=choice.finish_reason,
                usage={
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                },
            ),
        )


class RecordedProvider:
    """Replays fixed responses. No network, no credentials.

    Every test in this repository uses this. A test suite that reaches a real model is
    non-deterministic, costs money, and cannot run in CI — and none of the compiler's
    invariants need a live model to verify.
    """

    name = "recorded"

    def __init__(self, responses: list[dict] | None = None) -> None:
        self.responses = list(responses or [])
        self.calls: list[dict] = []

    def structured_generate(
        self, *, task: str, context: dict, schema: dict, settings: Settings,
        prompt_id: str, prompt_version: str,
    ) -> Proposal:
        safe_context, flags = guarded_context(context)
        self.calls.append({"task": task, "context": safe_context, "prompt_id": prompt_id})
        if not self.responses:
            raise ProviderError("RecordedProvider ran out of recorded responses")

        data = self.responses.pop(0)
        raw = json.dumps(data)
        return Proposal(
            data=data,
            raw=raw,
            injection_flags=flags,
            metadata=RunMetadata(
                provider=self.name,
                model=settings.model,
                prompt_id=prompt_id,
                prompt_version=prompt_version,
                decoding=settings.as_dict(),
                requested_at=_now(),
                input_hashes=_input_hashes(task, context, schema),
                output_hash=digest(raw),
                finish_reason="recorded",
            ),
        )
