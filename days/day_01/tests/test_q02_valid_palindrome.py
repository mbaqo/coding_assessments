import itertools
import random
import unittest

from ..q02_valid_palindrome import is_palindrome


def ascii_alphanumeric(character: str) -> bool:
    return "a" <= character <= "z" or "A" <= character <= "Z" or "0" <= character <= "9"


class ValidPalindromeTests(unittest.TestCase):
    def test_examples_and_boundaries(self):
        cases = [
            ("A man, a plan, a canal: Panama", True),
            ("race a car", False),
            ("", True),
            ("...", True),
            ("0P", False),
            ("1a1", True),
            ("abBA", True),
            ("a_!A", True),
            ("éAé", True),
            ("a😊b", False),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertIs(is_palindrome(value), expected)

    def test_all_short_strings(self):
        alphabet = "aA1!? "
        for length in range(5):
            for chars in itertools.product(alphabet, repeat=length):
                value = "".join(chars)
                cleaned = [char.lower() for char in value if ascii_alphanumeric(char)]
                with self.subTest(value=value):
                    self.assertIs(is_palindrome(value), cleaned == cleaned[::-1])

    def test_ascii_filter_before_case_conversion(self):
        for value, expected in (("éa", True), ("１a", True), ("KaK", False),
                                ("İaI", False), ("ßaS", False), ("\tA\n:a", True),
                                ("😃é１", True)):
            with self.subTest(value=value):
                self.assertIs(is_palindrome(value), expected)

    def test_seeded_inputs(self):
        rng = random.Random(102)
        for _ in range(200):
            value = "".join(rng.choices("abAB09 !?éKİ😊", k=rng.randrange(100)))
            cleaned = "".join(c.lower() for c in value if ascii_alphanumeric(c))
            with self.subTest(value=value):
                self.assertIs(is_palindrome(value), cleaned == cleaned[::-1])

    def test_large_inputs(self):
        for value, expected in (("!" * 100000, True), ("A" * 99999 + "b", False),
                                ("A!" * 50000, True)):
            self.assertIs(is_palindrome(value), expected)
