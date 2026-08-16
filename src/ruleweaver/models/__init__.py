"""Provider-neutral model layer. Never consulted at evaluation time — see ADR-003."""

from .base import (
    MissingCredentials,
    ModelProvider,
    Proposal,
    ProviderError,
    RunMetadata,
    Settings,
    digest,
)
from .guard import fence, guarded_context, scan
from .providers import AnthropicProvider, OpenAIProvider, RecordedProvider

__all__ = [
    "AnthropicProvider",
    "MissingCredentials",
    "ModelProvider",
    "OpenAIProvider",
    "Proposal",
    "ProviderError",
    "RecordedProvider",
    "RunMetadata",
    "Settings",
    "digest",
    "fence",
    "guarded_context",
    "scan",
]
