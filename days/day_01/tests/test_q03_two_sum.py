import itertools
import random
import unittest

from ..q03_two_sum import two_sum


class TwoSumTests(unittest.TestCase):
    def check_pair(self, nums, target, possible=None):
        original = nums.copy()
        result = two_sum(nums, target)
        self.assertEqual(nums, original, "The input list must not change")
        if possible is None:
            possible = any(nums[i] + nums[j] == target for i in range(len(nums)) for j in range(i + 1, len(nums)))
        if not possible:
            self.assertIsNone(result)
            return
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        i, j = result
        self.assertIs(type(i), int)
        self.assertIs(type(j), int)
        self.assertTrue(0 <= i < j < len(nums))
        self.assertEqual(nums[i] + nums[j], target)

    def test_examples_and_boundaries(self):
        cases = [
            ([], 0),
            ([1], 1),
            ([2, 7, 11, 15], 9),
            ([3, 3], 6),
            ([1, 2, 3], 9),
            ([-3, 4, 3, 90], 0),
            ([0, 0, 0], 0),
            ([10**12, -(10**12)], 0),
        ]
        for nums, target in cases:
            with self.subTest(nums=nums, target=target):
                self.check_pair(nums, target)

    def test_short_lists_and_targets(self):
        for length in range(5):
            for values in itertools.product((-2, -1, 0, 1, 2), repeat=length):
                for target in range(-4, 5):
                    with self.subTest(values=values, target=target):
                        self.check_pair(list(values), target)

    def test_distinct_positions_and_original_indexes(self):
        for nums, target in (([3], 6), ([3, 2, 4], 6), ([8, 1, 6, 3], 9),
                             ([0], 0), ([5, 1, 5], 10)):
            with self.subTest(nums=nums, target=target):
                self.check_pair(nums, target)

    def test_seeded_inputs(self):
        rng = random.Random(103)
        for _ in range(150):
            nums = [rng.randrange(-50, 51) for _ in range(rng.randrange(40))]
            target = rng.randrange(-100, 101)
            with self.subTest(nums=nums, target=target):
                self.check_pair(nums, target)

    def test_large_inputs(self):
        # Known existence avoids a quadratic oracle at assessment-sized inputs.
        self.check_pair(list(range(100000)), -1, possible=False)
        self.check_pair(list(range(100000)), 199997, possible=True)
