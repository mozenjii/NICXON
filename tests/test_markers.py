"""Marker hierarchy reconstruction.

The (i)-is-both-a-letter-and-a-numeral collision is the reason this module exists, so most
of these tests are about that. Getting it wrong reparents whole subtrees, which silently
moves every rule's provenance to the wrong clause.
"""

from __future__ import annotations

import pytest

from ruleweaver.ingest.markers import (
    Hierarchy,
    alpha_to_int,
    int_to_alpha,
    int_to_roman,
    kinds_of,
    ordinal,
    render,
    roman_to_int,
)


class TestNumerals:
    @pytest.mark.parametrize("text,value", [
        ("i", 1), ("ii", 2), ("iv", 4), ("v", 5), ("ix", 9), ("x", 10),
        ("xiv", 14), ("xl", 40), ("l", 50), ("c", 100), ("cd", 400), ("m", 1000),
    ])
    def test_roman_round_trips(self, text, value):
        assert roman_to_int(text) == value
        assert int_to_roman(value) == text

    @pytest.mark.parametrize("text", ["", "iiii", "vv", "ic", "abc", "1"])
    def test_rejects_non_roman(self, text):
        assert roman_to_int(text) is None

    @pytest.mark.parametrize("text,value", [("a", 1), ("z", 26), ("aa", 27), ("ab", 28)])
    def test_alpha_round_trips(self, text, value):
        assert alpha_to_int(text) == value
        assert int_to_alpha(value) == text


class TestKinds:
    def test_a_digit_is_only_a_digit(self):
        assert kinds_of("12") == ["digit"]

    def test_an_ambiguous_letter_reports_both_readings(self):
        assert kinds_of("i") == ["roman_lower", "alpha_lower"]
        assert kinds_of("v") == ["roman_lower", "alpha_lower"]

    def test_an_unambiguous_letter_reports_one(self):
        assert kinds_of("b") == ["alpha_lower"]
        assert kinds_of("h") == ["alpha_lower"]

    def test_case_separates_the_upper_sequences(self):
        assert kinds_of("A") == ["alpha_upper"]
        assert kinds_of("I") == ["roman_upper", "alpha_upper"]

    def test_nothing_is_reported_for_junk(self):
        assert kinds_of("") == []
        assert kinds_of("a1") == []

    def test_ordinal_and_render_are_inverse(self):
        for kind in ("digit", "alpha_lower", "roman_lower", "alpha_upper", "roman_upper"):
            for index in (1, 2, 9, 27):
                assert ordinal(render(index, kind), kind) == index


class TestHierarchy:
    def paths(self, markers: list[str]) -> list[list[str]]:
        h = Hierarchy()
        return [h.place(m)[0] for m in markers]

    def test_nests_the_standard_cfr_sequence(self):
        assert self.paths(["a", "1", "i", "A"]) == [
            ["a"], ["a", "1"], ["a", "1", "i"], ["a", "1", "i", "A"]]

    def test_siblings_stay_at_one_level(self):
        assert self.paths(["a", "b", "c"]) == [["a"], ["b"], ["c"]]

    def test_i_after_h_continues_the_letters(self):
        """The collision. (h) then (i) is two siblings, not a new roman level."""
        paths = self.paths(["a", "b", "c", "d", "e", "f", "g", "h", "i", "j"])
        assert paths[-2] == ["i"]
        assert paths[-1] == ["j"]

    def test_i_after_a_digit_opens_a_roman_level(self):
        """The same marker, the other reading — because nothing precedes it to continue."""
        assert self.paths(["a", "1", "i", "ii"]) == [
            ["a"], ["a", "1"], ["a", "1", "i"], ["a", "1", "ii"]]

    def test_a_digit_closes_a_deeper_roman_level(self):
        assert self.paths(["a", "1", "i", "ii", "2"]) == [
            ["a"], ["a", "1"], ["a", "1", "i"], ["a", "1", "ii"], ["a", "2"]]

    def test_returning_to_the_outer_letters_closes_everything(self):
        assert self.paths(["a", "1", "i", "b"]) == [
            ["a"], ["a", "1"], ["a", "1", "i"], ["b"]]

    def test_v_after_iv_continues_the_numerals(self):
        """(v) is the other collision, and after (iv) the numeral reading must win."""
        paths = self.paths(["a", "1", "i", "ii", "iii", "iv", "v"])
        assert paths[-1] == ["a", "1", "v"]

    def test_a_confident_parse_is_not_flagged(self):
        h = Hierarchy()
        assert all(not h.place(m)[1] for m in ["a", "1", "i", "A", "2", "b"])

    def test_a_skipped_marker_is_salvaged_and_flagged(self):
        """Amended regulations really do go (a), (c) — the paragraph between was removed."""
        h = Hierarchy()
        h.place("a")
        path, uncertain = h.place("c")
        assert path == ["c"]
        assert uncertain, "a gap in the sequence must be reported, not hidden"

    def test_junk_attaches_to_the_open_level_and_is_flagged(self):
        h = Hierarchy()
        h.place("a")
        path, uncertain = h.place("a1")
        assert path == ["a"]
        assert uncertain
