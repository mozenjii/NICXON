"""Content hashing.

One definition, in a module that depends on nothing. Approval, provenance and run
metadata all pin content by hash, and they must agree byte for byte: an approval recorded
against one digest of a rule and checked against another is worse than no approval at all,
because it fails open and looks like it worked.

Kept out of `models/` deliberately. A deployment that only executes approved rules
installs no model SDK (ADR-003), so the approval gate cannot reach into the model layer
for its hash function.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def digest(value: Any) -> str:
    """Stable content hash, prefixed with its algorithm.

    Non-strings are canonicalised as sorted-key JSON so that dict ordering, which is not
    semantic, cannot change the digest. `ensure_ascii=False` keeps the hash stable across
    Python versions that differ in how they escape non-ASCII.
    """
    if not isinstance(value, str):
        value = json.dumps(value, sort_keys=True, ensure_ascii=False)
    return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()
