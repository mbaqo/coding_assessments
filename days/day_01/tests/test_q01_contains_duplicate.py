import itertools
import random
import unittest

from ..q01_contains_duplicate import contains_duplicate


class ContainsDuplicateTests(unittest.TestCase):
    def test_examples_and_boundaries(self):
        cases = [
            ([], False),
            ([7], False),
            ([1, 2, 3, 1], True),
            ([1, 2, 3, 4], False),
            ([-5, 0, 5, -5], True),
            ([0, 0], True),
            ([10**12, -(10**12), 10**12], True),
        ]
        for nums, expected in cases:
            with self.subTest(nums=nums):
                original = nums.copy()
                self.assertIs(contains_duplicate(nums), expected)
                self.assertEqual(nums, original, "The input list must not change")

    def test_all_short_lists(self):
        for length in range(6):
            for values in itertools.product((-1, 0, 1), repeat=length):
                nums = list(values)
                with self.subTest(nums=nums):
                    original = nums.copy()
                    self.assertIs(contains_duplicate(nums), len(set(nums)) != len(nums))
                    self.assertEqual(nums, original)

    def test_seeded_inputs(self):
        rng = random.Random(101)
        for _ in range(100):
            nums = rng.sample(range(-1000, 1000), rng.randrange(1, 100))
            if rng.choice((True, False)):
                nums.append(rng.choice(nums))
            rng.shuffle(nums)
            original = nums.copy()
            with self.subTest(nums=nums):
                self.assertIs(contains_duplicate(nums), len(set(nums)) != len(nums))
                self.assertEqual(nums, original)

    def test_large_inputs(self):
        for nums, expected in ((list(range(100000)), False), (list(range(99999)) + [0], True)):
            original = nums.copy()
            self.assertIs(contains_duplicate(nums), expected)
            self.assertEqual(nums, original)
