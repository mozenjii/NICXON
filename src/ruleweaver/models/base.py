"""Provider-neutral model interface.

ADR-016: core compiler APIs may not depend on one proprietary model or provider.
ADR-003: nothing here is ever consulted at evaluation time. A provider produces
*proposals*, which are data that must survive validation and human approval before any
determination depends on them.

The shape is the one docs/03_ARCHITECTURE.md specifies:

    structured_generate(task, context, schema, settings) -> typed proposal + run metadata

Run metadata is not optional bookkeeping. Without it a compilation cannot be reproduced,
and docs/06_VERIFICATION_SAFETY.md requires that it can be.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

# Re-exported, not redefined. The approval gate hashes rules with the same function that
# pins model inputs, and two implementations would eventually disagree.
from ..hashing import digest


@dataclass(frozen=True)
class Settings:
    """Decoding settings, recorded verbatim in run metadata.

    temperature defaults to 0. A rule extraction that changes between identical runs
    cannot be reviewed, because the reviewer approves one sample and the next run
    produces another.
    """

    model: str
    temperature: float = 0.0
    max_tokens: int = 4096
    top_p: float | None = None
    seed: int | None = None

    def as_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass(frozen=True)
class RunMetadata:
    """Everything needed to reproduce, or to explain, one model call."""

    provider: str
    model: str
    prompt_id: str
    prompt_version: str
    decoding: dict
    requested_at: str
    input_hashes: dict[str, str]
    output_hash: str
    finish_reason: str | None = None
    usage: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "provider": self.provider,
            "model": self.model,
            "prompt_id": self.prompt_id,
            "prompt_version": self.prompt_version,
            "decoding": self.decoding,
            "requested_at": self.requested_at,
            "input_hashes": self.input_hashes,
            "output_hash": self.output_hash,
            "finish_reason": self.finish_reason,
            "usage": self.usage,
        }


@dataclass
class Proposal:
    """A model's output. Never authoritative, never executable as written."""

    data: dict
    metadata: RunMetadata
    raw: str

    # Set when the guard found instruction-like content in the source document.
    # A flagged proposal is not discarded automatically — it is escalated, because
    # silently dropping a proposal hides an attack from the reviewer.
    injection_flags: list[str] = field(default_factory=list)

    @property
    def suspicious(self) -> bool:
        return bool(self.injection_flags)


class ProviderError(RuntimeError):
    """A provider failed. Distinct from a model returning something unusable."""


class MissingCredentials(ProviderError):
    """No API key was configured.

    The message names the environment variable rather than accepting a key by argument.
    Credentials belong in the environment, not in a call site that might be logged,
    committed, or pasted into an issue.
    """

    def __init__(self, provider: str, env_var: str) -> None:
        super().__init__(
            f"{provider} has no credentials. Set {env_var} in your environment.\n"
            f"  bash:       export {env_var}=...\n"
            f"  PowerShell: $env:{env_var} = '...'\n"
            f"Never commit the key or pass it as a command line argument."
        )
        self.provider = provider
        self.env_var = env_var


@runtime_checkable
class ModelProvider(Protocol):
    """What the compiler is allowed to ask a model for.

    Deliberately narrow. There is no free-form `chat` method, because a compiler pass
    that can ask anything is a compiler pass nobody can audit.
    """

    name: str

    def structured_generate(
        self,
        *,
        task: str,
        context: dict,
        schema: dict,
        settings: Settings,
        prompt_id: str,
        prompt_version: str,
    ) -> Proposal:
        ...
