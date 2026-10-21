"""Verify grading quality without modifying learner files. Contains spoilers."""
import importlib
import io
import unittest
from unittest.mock import patch

import practice
from reference_solutions import REFERENCES


def unicode_palindrome(text):
    cleaned = ''.join(c.lower() for c in text if c.isalnum())
    return cleaned == cleaned[::-1]


def lowercase_before_filter(text):
    cleaned = ''.join(c for c in text.lower() if c in 'abcdefghijklmnopqrstuvwxyz0123456789')
    return cleaned == cleaned[::-1]


def duplicate_mutates(nums):
    nums.sort()
    return len(set(nums)) != len(nums)


def sum_reuses_index(nums, target):
    for i, value in enumerate(nums):
        if target - value in nums:
            return i, nums.index(target - value)
    return None


def merge_returns_input(left, right):
    if not left:
        return right
    return sorted(left + right)


def merge_drops_duplicates(left, right):
    return sorted(set(left + right))


def brackets_count_only(text):
    return all(text.count(a) == text.count(b) for a, b in ('()', '[]', '{}'))


MUTANTS = {
    '1': [lambda nums: False, duplicate_mutates],
    '2': [unicode_palindrome, lowercase_before_filter],
    '3': [sum_reuses_index, lambda nums, target: None],
    '4': [brackets_count_only, lambda text: bool(text) and REFERENCES['4'](text)],
    '5': [merge_returns_input, merge_drops_duplicates],
}


class QuestionSuiteTests(unittest.TestCase):
    def run_candidate(self, question, candidate, full=True):
        module = importlib.import_module(question.module)
        output = io.StringIO()
        with patch.object(module, question.entry_point, candidate):
            suite = unittest.defaultTestLoader.loadTestsFromModule(module)
            self.assertGreater(suite.countTestCases(), 0)
            result = unittest.TextTestRunner(stream=output, failfast=not full).run(suite)
        return result, output.getvalue()

    def test_every_question_has_a_reference_and_negative_controls(self):
        ids = set(practice.discover_questions())
        self.assertEqual(ids, set(REFERENCES), 'Add reference validation for new questions')
        self.assertEqual(ids, set(MUTANTS), 'Add negative controls for new questions')

    def test_correct_references_pass_every_case(self):
        for number, question in practice.discover_questions().items():
            with self.subTest(question=number):
                result, output = self.run_candidate(question, REFERENCES[number])
                self.assertTrue(result.wasSuccessful(), output)

    def test_representative_wrong_answers_are_rejected(self):
        for number, question in practice.discover_questions().items():
            for candidate in MUTANTS[number]:
                with self.subTest(question=number, candidate=candidate.__name__):
                    result, _ = self.run_candidate(question, candidate, full=False)
                    self.assertFalse(result.wasSuccessful(), 'Incorrect answer was accepted')
                    self.assertTrue(result.failures, 'Reject wrong answers through assertions, not test errors')

    def test_two_sum_accepts_an_alternative_valid_pair(self):
        def reverse_search(nums, target):
            seen = {}
            for i in range(len(nums) - 1, -1, -1):
                if target - nums[i] in seen:
                    return i, seen[target - nums[i]]
                seen[nums[i]] = i
            return None
        result, output = self.run_candidate(practice.discover_questions()['3'], reverse_search)
        self.assertTrue(result.wasSuccessful(), output)
