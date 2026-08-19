"""Source ingestion. Turns an authoritative snapshot into addressable clauses.

Nothing here calls a model or reaches the network. Ingestion is deterministic so that a
compilation can be reproduced from the manifest alone.
"""

from .corpus import Corpus, CorpusError, load_corpus, sha256_of, verify_manifest
from .document import Clause, SourceDocument, SpanResolution, resolve_span, slugify
from .ecfr import parse_file, parse_section
from .markers import Hierarchy, split_runin

__all__ = [
    "Clause",
    "Corpus",
    "CorpusError",
    "Hierarchy",
    "SourceDocument",
    "SpanResolution",
    "load_corpus",
    "parse_file",
    "parse_section",
    "resolve_span",
    "sha256_of",
    "slugify",
    "split_runin",
    "verify_manifest",
]
