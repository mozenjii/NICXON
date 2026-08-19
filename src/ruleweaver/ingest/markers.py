"""Reconstructing legal hierarchy from paragraph markers.

eCFR serves a section as a flat list of paragraphs. The hierarchy lives only in the
markers that open them — (a), (1), (i), (A) — so it has to be inferred, and the inference
has one genuinely hard case:

    (h) ... (i) ...        two sibling letters
    (2) ... (i) ...        a digit opening a roman child

`(i)` is both the ninth letter and the first roman numeral, and nothing local
disambiguates it. The same collision hits (v), (x), (l), (c), (d) and (m).

Resolution is by continuation, not by lookahead: a marker that is the *successor* of the
last marker at an open level continues that level; otherwise a marker that is the *first*
of its kind opens a new one. After (h), "i" succeeds it and stays a sibling. After (2)
opened a fresh level, "i" succeeds nothing, so it opens a roman level. This is what a human
reader does, and it is decidable without reading ahead.

When neither rule applies the marker is attached to the deepest open level and flagged.
A salvaged parse that says so is more useful than a confident wrong one, and more useful
than refusing to parse the document at all.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# The CFR's level cycle, outermost first: (a)(1)(i)(A)(1)(i)(A). Digits and lower roman
# numerals genuinely repeat at depth 5 and 6 — 7 CFR 273.9(c)(3)(ii)(C)(1) is a real
# citation — so a flat list of distinct kinds cannot represent this document. Treating the
# second digit level as a restart of the first is what reparents whole subtrees.
LEVEL_KINDS = ("alpha_lower", "digit", "roman_lower", "alpha_upper",
               "digit", "roman_lower", "alpha_upper")

# Every kind that can appear, for classification.
KINDS = ("alpha_lower", "digit", "roman_lower", "alpha_upper", "roman_upper")

_ROMAN_VALUES = (("m", 1000), ("cm", 900), ("d", 500), ("cd", 400), ("c", 100),
                 ("xc", 90), ("l", 50), ("xl", 40), ("x", 10), ("ix", 9),
                 ("v", 5), ("iv", 4), ("i", 1))

_ROMAN_RE = re.compile(r"^m{0,3}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3})$")

# The opening marker of a paragraph: "(a) text", "(1) text", "(iv) text".
MARKER_RE = re.compile(r"^\(([A-Za-z0-9]{1,4})\)\s*")

# The same shape without the anchor, for matching at an offset. `MARKER_RE` keeps its `^`
# so it can never match a parenthesis mid-sentence by accident.
_MARKER_AT = re.compile(r"\(([A-Za-z0-9]{1,4})\)\s*")


def roman_to_int(text: str) -> int | None:
    lowered = text.lower()
    if not lowered or not _ROMAN_RE.match(lowered):
        return None
    total, index = 0, 0
    while index < len(lowered):
        for symbol, value in _ROMAN_VALUES:
            if lowered.startswith(symbol, index):
                total += value
                index += len(symbol)
                break
        else:  # pragma: no cover - the regex already rejects these
            return None
    return total


def int_to_roman(value: int) -> str:
    out = []
    for symbol, amount in _ROMAN_VALUES:
        while value >= amount:
            out.append(symbol)
            value -= amount
    return "".join(out)


def alpha_to_int(text: str) -> int | None:
    """Spreadsheet-style: a=1 … z=26, aa=27. The CFR uses doubled letters past z."""
    if not text.isalpha():
        return None
    total = 0
    for char in text.lower():
        total = total * 26 + (ord(char) - ord("a") + 1)
    return total


def int_to_alpha(value: int) -> str:
    out = ""
    while value > 0:
        value, remainder = divmod(value - 1, 26)
        out = chr(ord("a") + remainder) + out
    return out


def kinds_of(marker: str) -> list[str]:
    """Every kind `marker` could be, most specific first.

    A single lowercase roman letter is genuinely both a letter and a numeral, and both are
    returned. Callers disambiguate by position; nothing here guesses.
    """
    out: list[str] = []
    if marker.isdigit():
        out.append("digit")
        return out
    if marker.islower():
        if roman_to_int(marker) is not None:
            out.append("roman_lower")
        if marker.isalpha():
            out.append("alpha_lower")
    elif marker.isupper():
        if roman_to_int(marker) is not None:
            out.append("roman_upper")
        if marker.isalpha():
            out.append("alpha_upper")
    return out


def ordinal(marker: str, kind: str) -> int | None:
    """Position of `marker` within its own sequence, 1-based."""
    if kind == "digit":
        return int(marker) if marker.isdigit() else None
    if kind in ("roman_lower", "roman_upper"):
        return roman_to_int(marker)
    return alpha_to_int(marker)


def render(index: int, kind: str) -> str:
    """The marker at position `index` of a sequence of `kind`. Inverse of `ordinal`."""
    if kind == "digit":
        return str(index)
    if kind == "roman_lower":
        return int_to_roman(index)
    if kind == "roman_upper":
        return int_to_roman(index).upper()
    if kind == "alpha_lower":
        return int_to_alpha(index)
    return int_to_alpha(index).upper()


@dataclass
class Level:
    kind: str
    marker: str
    index: int


class Hierarchy:
    """Running reconstruction of the open marker levels.

    One instance per document, fed paragraphs in order. `place` returns the path of
    markers from the outermost open level to this one.
    """

    def __init__(self) -> None:
        self.levels: list[Level] = []

    def place(self, marker: str) -> tuple[list[str], bool]:
        """Position `marker` in the hierarchy. Returns (path, uncertain)."""
        candidates = kinds_of(marker)
        if not candidates:
            return [level.marker for level in self.levels], True

        # 1. Continuation of an already-open level, deepest first. Checking deepest first
        #    matters: after (a)(1) a bare "2" continues the digit level, not the letters.
        for depth in range(len(self.levels) - 1, -1, -1):
            level = self.levels[depth]
            if level.kind not in candidates:
                continue
            index = ordinal(marker, level.kind)
            if index is not None and index == level.index + 1:
                self.levels = self.levels[:depth]
                self.levels.append(Level(level.kind, marker, index))
                return [lv.marker for lv in self.levels], False

        # 2. Opening the next level of the CFR cycle. Only the first marker of a sequence
        #    may do this — "(c)" with no "(a)" before it is a gap, not a new level.
        expected = LEVEL_KINDS[min(len(self.levels), len(LEVEL_KINDS) - 1)]
        if expected in candidates and ordinal(marker, expected) == 1:
            self.levels.append(Level(expected, marker, 1))
            return [lv.marker for lv in self.levels], False

        # 3. A first marker of some other kind still opens a level, as long as it is not
        #    the kind already sitting at the bottom of the stack — that would be a restart
        #    of the current sequence, which is a break in the document, not nesting.
        innermost = self.levels[-1].kind if self.levels else None
        for kind in candidates:
            if kind != innermost and ordinal(marker, kind) == 1:
                self.levels.append(Level(kind, marker, 1))
                return [lv.marker for lv in self.levels], False

        # 4. Salvage. A skipped marker — (a) then (c) — is common in amended regulations
        #    where a paragraph was removed, so replace the level rather than dropping the
        #    paragraph, and record that the depth is a guess.
        for depth in range(len(self.levels) - 1, -1, -1):
            level = self.levels[depth]
            if level.kind in candidates:
                index = ordinal(marker, level.kind) or level.index + 1
                self.levels = self.levels[:depth]
                self.levels.append(Level(level.kind, marker, index))
                return [lv.marker for lv in self.levels], True

        kind = candidates[0]
        self.levels.append(Level(kind, marker, ordinal(marker, kind) or 1))
        return [lv.marker for lv in self.levels], True

    def clone(self) -> Hierarchy:
        """A copy, for trial placements that must not mutate the running state."""
        other = Hierarchy()
        other.levels = [Level(lv.kind, lv.marker, lv.index) for lv in self.levels]
        return other

    def accepts(self, markers: list[str]) -> bool:
        """Whether this sequence would place cleanly, without salvage. Non-mutating."""
        trial = self.clone()
        return all(not trial.place(m)[1] for m in markers)


# A run-in marker: the CFR sets a subsection heading and its first child in one paragraph,
# separated by an em dash — "(a) Month of application—(1) Determination of eligibility" —
# and also runs a list into its lead-in — "shall include: (i) All wages". A dash, or a
# full stop, colon or semicolon before the marker are all candidates; whether
# a match is really a new clause is decided by the hierarchy, not by the regex.
RUNIN_RE = re.compile(r"(?:[—–-]|(?<=[.:;])\s)\(([A-Za-z0-9]{1,4})\)\s*")


def split_runin(text: str, hierarchy: Hierarchy) -> list[str]:
    """Split a paragraph that packs several clause levels into one.

    Candidate boundaries come from `RUNIN_RE`; each is accepted only if the resulting
    marker sequence places cleanly in the hierarchy. That test is what keeps ordinary prose
    intact: a cross-reference like "as defined in § 273.2(j)(2)" produces a marker the
    hierarchy will not accept at that position, so the sentence is left whole.
    """
    first = MARKER_RE.match(text)
    if not first:
        return [text]

    accepted: list[str] = [first.group(1)]
    cuts: list[int] = []

    def consume_adjacent(position: int) -> int:
        """Absorb a run of markers with nothing between them.

        "(i)(A) Households which contain" is always nesting — there is no separator to key
        on, so only immediate adjacency qualifies. Elsewhere in a sentence "(a)(1)" is far
        more likely to be a cross-reference than a clause boundary, and the hierarchy
        acceptance test is the second guard against treating one as the other.
        """
        while (nested := _MARKER_AT.match(text, position)) is not None:
            if not hierarchy.accepts(accepted + [nested.group(1)]):
                break
            accepted.append(nested.group(1))
            cuts.append(position)
            position = nested.end()
        return position

    position = consume_adjacent(first.end())

    while (match := RUNIN_RE.search(text, position)) is not None:
        if not hierarchy.accepts(accepted + [match.group(1)]):
            position = match.end()
            continue
        accepted.append(match.group(1))
        # Cut at the parenthesis, dropping the dash or punctuation that introduced it.
        cuts.append(match.start(0) + match.group(0).index("("))
        position = consume_adjacent(match.end())

    if not cuts:
        return [text]

    segments = []
    bounds = [0, *cuts, len(text)]
    for start, end in zip(bounds, bounds[1:]):
        segment = text[start:end].strip().rstrip("—–-").strip()
        if segment:
            segments.append(segment)
    return segments
