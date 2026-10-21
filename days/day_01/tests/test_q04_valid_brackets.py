import itertools
import random
import unittest

from ..q04_valid_brackets import valid_brackets


def reduce_pairs(text):
    previous = None
    while text != previous:
        previous = text
        for pair in ("()", "[]", "{}"):
            text = text.replace(pair, "")
    return not text


class ValidBracketsTests(unittest.TestCase):
    def test_examples_and_boundaries(self):
        cases = [
            ("", True),
            ("()[]{}", True),
            ("([{}])", True),
            ("([)]", False),
            ("(", False),
            (")", False),
            ("())", False),
            ("{[()]}[]", True),
            ("({[)]}", False),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertIs(valid_brackets(value), expected)

    def test_all_short_bracket_strings(self):
        for length in range(6):
            for chars in itertools.product("()[]{}", repeat=length):
                value = "".join(chars)
                with self.subTest(value=value):
                    self.assertIs(valid_brackets(value), reduce_pairs(value))

    def test_seeded_balanced_and_unbalanced_inputs(self):
        rng = random.Random(104)
        for _ in range(100):
            value = ""
            for _ in range(20):
                opening, closing = rng.choice(("()", "[]", "{}"))
                value = opening + value + closing if rng.choice((True, False)) else value + opening + closing
            self.assertIs(valid_brackets(value), True)
            self.assertIs(valid_brackets(value + ")"), False)
            self.assertIs(valid_brackets(value[:-1]), False)

    def test_large_inputs(self):
        for value, expected in (("(" * 50000 + ")" * 50000, True),
                                ("[]" * 50000, True), ("(" * 100000, False),
                                ("(" * 49999 + "[" + ")" * 50000, False)):
            self.assertIs(valid_brackets(value), expected)
