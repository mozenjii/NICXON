"""LLM-assisted compilation. Proposes; never decides.

Everything here produces candidates that deterministic validation and a human reviewer
must accept before they can affect an outcome (ADR-003, ADR-004). Nothing in this package
is imported by the runtime, the evaluator, or the approval gate — a deployment that only
executes approved rules never loads it.
"""

from .extract import RuleProposal, Vocabulary, propose
from .pipeline import CompilationRun, compile_corpus
from .prompts import Prompt, PromptError, available
from .prompts import load as load_prompt
from .schemas import CLASSIFICATIONS, SEGMENT_SCHEMA, extract_schema, rule_schema
from .segment import Segment, classify

__all__ = [
    "CLASSIFICATIONS",
    "SEGMENT_SCHEMA",
    "CompilationRun",
    "Prompt",
    "PromptError",
    "RuleProposal",
    "Segment",
    "Vocabulary",
    "available",
    "classify",
    "compile_corpus",
    "extract_schema",
    "load_prompt",
    "propose",
    "rule_schema",
]
