"""Choosing a provider by name.

Kept apart from `models/providers.py` so the model layer stays free of policy. That module
knows how to talk to a vendor; this one knows which vendor the compiler is being asked to
use, what the default model for each is, and how to refuse clearly when the answer is none
of them.

The default is deliberately `recorded`. Reaching a paid API because a flag was forgotten is
the kind of surprise that turns into a bill and a rate limit at the same time, and every
invariant this compiler enforces can be exercised without a network.
"""

from __future__ import annotations

from ..models.base import ModelProvider, Settings
from ..models.providers import AnthropicProvider, OpenAIProvider, RecordedProvider

# The default model per provider. Named here rather than in the adapters so that changing
# which model a compilation used is a visible edit in one place — run metadata records the
# model, and a silent default change would make two runs incomparable for no stated reason.
DEFAULTS = {
    "anthropic": "claude-opus-5",
    "openai": "gpt-5.2",
    "recorded": "recorded",
}

CREDENTIALS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY (or OPENAI_ACCESS_TOKEN for an OAuth token)",
}


class UnknownProvider(Exception):
    """The requested provider is not one this build knows about."""

    def __init__(self, name: str) -> None:
        super().__init__(
            f"unknown provider {name!r}. Available: {', '.join(sorted(DEFAULTS))}.")


def build(name: str, *, model: str | None = None,
          responses: list[dict] | None = None) -> tuple[ModelProvider, Settings]:
    """A provider and the settings to call it with.

    Returns both because they travel together: the settings carry the model id into run
    metadata, and a provider constructed with one model but called with another produces a
    record that does not describe what happened.
    """
    if name not in DEFAULTS:
        raise UnknownProvider(name)

    chosen = model or DEFAULTS[name]
    settings = Settings(model=chosen)

    if name == "anthropic":
        return AnthropicProvider(chosen), settings
    if name == "openai":
        return OpenAIProvider(chosen), settings
    return RecordedProvider(responses or []), settings


def credential_hint(name: str) -> str | None:
    """Which environment variable a provider reads, for an error message.

    Never the value. A hint that echoed the key would put it in a terminal scrollback, a
    CI log, and eventually an issue report.
    """
    return CREDENTIALS.get(name)
