"""Lab name/ticker sanitization (stdlib unittest; zero deps).

The lab name and ticker are the only player-authored strings that enter the
engine and then flow on to the frontend (legend, panels) and observations. They
are PUBLIC/legible, but they ARE untrusted input, so new_game() must clamp them
before constructing a Lab — length limits, control-char stripping, empty→default
— so a malicious or oversized value can never reach state unbounded. The frontend
escapes again at render (defence in depth), but this is the server-side line that
must hold even if a client posts directly.
"""
import unittest

from backend_v1.engine.game import (
    new_game,
    sanitize_lab_name,
    sanitize_ticker,
    derive_ticker_from_name,
    MAX_LAB_NAME_CHARS,
    MAX_TICKER_CHARS,
    DEFAULT_PLAYER_LAB_NAME,
    DEFAULT_PLAYER_TICKER,
)


def player_lab(state):
    return next(lab for lab in state.labs if lab.is_player)


class TestLabNameSanitization(unittest.TestCase):
    def test_script_tag_name_is_bounded_string(self):
        # An XSS payload is just a (length-clamped) string at THIS layer — the
        # server does not strip markup characters; the frontend escapes them on
        # render (the actual XSS defence). Here we only assert it stays bounded
        # and the function does not choke on angle brackets/quotes.
        short_payload = "<script>alert('xss')</script>"
        cleaned = sanitize_lab_name(short_payload)
        self.assertLessEqual(len(cleaned), MAX_LAB_NAME_CHARS)

    def test_overlong_script_payload_is_truncated(self):
        # A payload longer than the limit must be cut down regardless of content.
        overlong_payload = "<script>" + "A" * 200 + "</script>"
        cleaned = sanitize_lab_name(overlong_payload)
        self.assertEqual(len(cleaned), MAX_LAB_NAME_CHARS)

    def test_overlong_name_is_truncated_to_limit(self):
        overlong = "A" * 500
        cleaned = sanitize_lab_name(overlong)
        self.assertEqual(len(cleaned), MAX_LAB_NAME_CHARS)

    def test_control_characters_are_stripped(self):
        with_controls = "Ev\x00il\nLab\tName\x07"
        cleaned = sanitize_lab_name(with_controls)
        for forbidden_char in ("\x00", "\n", "\t", "\x07"):
            self.assertNotIn(forbidden_char, cleaned)

    def test_empty_name_falls_back_to_default(self):
        self.assertEqual(sanitize_lab_name(""), DEFAULT_PLAYER_LAB_NAME)
        self.assertEqual(sanitize_lab_name("   "), DEFAULT_PLAYER_LAB_NAME)

    def test_non_string_name_falls_back_to_default(self):
        self.assertEqual(sanitize_lab_name(None), DEFAULT_PLAYER_LAB_NAME)
        self.assertEqual(sanitize_lab_name(12345), DEFAULT_PLAYER_LAB_NAME)


class TestTickerSanitization(unittest.TestCase):
    def test_ticker_clamped_and_uppercased(self):
        cleaned = sanitize_ticker("abcdefghij", fallback_name="Whatever")
        self.assertLessEqual(len(cleaned), MAX_TICKER_CHARS)
        self.assertEqual(cleaned, cleaned.upper())

    def test_empty_ticker_derives_from_name(self):
        self.assertEqual(sanitize_ticker("", fallback_name="OpenBrain"), "OPE")

    def test_ticker_strips_control_chars(self):
        cleaned = sanitize_ticker("X\x00Y\nZ", fallback_name="Anything")
        for forbidden_char in ("\x00", "\n"):
            self.assertNotIn(forbidden_char, cleaned)

    def test_derive_skips_non_alphanumeric(self):
        self.assertEqual(derive_ticker_from_name("Open Brain"), "OPE")
        self.assertEqual(derive_ticker_from_name("!!!"), DEFAULT_PLAYER_TICKER)


class TestNewGameAppliesSanitization(unittest.TestCase):
    def test_malicious_name_and_ticker_are_clamped_on_the_lab(self):
        state = new_game(
            seed=1,
            player_lab_name="<script>alert(1)</script>" + "Z" * 200,
            player_ticker="<<<<<<<<<<HACK",
        )
        lab = player_lab(state)
        self.assertLessEqual(len(lab.name), MAX_LAB_NAME_CHARS)
        self.assertLessEqual(len(lab.ticker), MAX_TICKER_CHARS)
        self.assertEqual(lab.ticker, lab.ticker.upper())

    def test_blank_inputs_yield_defaults(self):
        state = new_game(seed=1, player_lab_name="", player_ticker="")
        lab = player_lab(state)
        self.assertEqual(lab.name, DEFAULT_PLAYER_LAB_NAME)
        # default name "Your Lab" → first 3 alphanumerics "YOU"
        self.assertEqual(lab.ticker, "YOU")

    def test_rivals_receive_derived_tickers(self):
        state = new_game(seed=1)
        for rival in state.labs:
            if rival.is_player:
                continue
            self.assertTrue(rival.ticker)
            self.assertEqual(rival.ticker, rival.ticker.upper())


if __name__ == "__main__":
    unittest.main()
