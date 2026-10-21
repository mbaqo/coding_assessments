"""SPOILERS: maintainer-only answers used to verify grading suites.

Do not import these from learner solutions. Practice commands never load this file.
"""


def contains_duplicate(nums):
    return len(nums) != len(set(nums))


def is_palindrome(text):
    def accepted(c):
        return 'a' <= c <= 'z' or 'A' <= c <= 'Z' or '0' <= c <= '9'
    left, right = 0, len(text) - 1
    while left < right:
        if not accepted(text[left]):
            left += 1
        elif not accepted(text[right]):
            right -= 1
        elif text[left].lower() != text[right].lower():
            return False
        else:
            left += 1
            right -= 1
    return True


def two_sum(nums, target):
    seen = {}
    for j, value in enumerate(nums):
        if target - value in seen:
            return seen[target - value], j
        seen[value] = j
    return None


def valid_brackets(text):
    stack = []
    matching = {')': '(', ']': '[', '}': '{'}
    for char in text:
        if char in '([{':
            stack.append(char)
        elif not stack or stack.pop() != matching[char]:
            return False
    return not stack


def merge_sorted(left, right):
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result


REFERENCES = {'1': contains_duplicate, '2': is_palindrome, '3': two_sum,
              '4': valid_brackets, '5': merge_sorted}
