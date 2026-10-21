import itertools
import random
import unittest

from ..q05_merge_sorted_lists import merge_sorted


class MergeSortedListsTests(unittest.TestCase):
    def check_merge(self, left, right):
        left_before = left.copy()
        right_before = right.copy()
        result = merge_sorted(left, right)
        self.assertIsInstance(result, list)
        self.assertTrue(all(type(value) is int for value in result), "Output values must be integers")
        self.assertEqual(result, sorted(left + right))
        self.assertIsNot(result, left)
        self.assertIsNot(result, right)
        self.assertEqual(left, left_before, "Left input must not change")
        self.assertEqual(right, right_before, "Right input must not change")

    def test_examples_and_boundaries(self):
        cases = [
            ([], []),
            ([], [2, 3]),
            ([1, 2], []),
            ([1, 2, 4], [1, 3, 4]),
            ([-5, -1, 0], [-6, -1, 9]),
            ([7, 7, 7], [7, 7]),
            ([1], [2, 3, 4, 5]),
        ]
        for left, right in cases:
            with self.subTest(left=left, right=right):
                self.check_merge(left, right)

    def test_all_short_sorted_lists(self):
        options = [list(values) for length in range(5) for values in itertools.combinations_with_replacement((-1, 0, 1), length)]
        for left in options:
            for right in options:
                with self.subTest(left=left, right=right):
                    self.check_merge(left, right)

    def test_aliased_inputs(self):
        for values in ([], [1], [-2, 0, 0, 7]):
            self.check_merge(values, values)

    def test_seeded_inputs(self):
        rng = random.Random(105)
        for _ in range(100):
            left = sorted(rng.choices(range(-100, 101), k=rng.randrange(100)))
            right = sorted(rng.choices(range(-100, 101), k=rng.randrange(100)))
            with self.subTest(left=left, right=right):
                self.check_merge(left, right)

    def test_large_inputs(self):
        self.check_merge(list(range(0, 200000, 2)), list(range(1, 200000, 2)))
        self.check_merge([-10**12] * 100000, [10**12])
