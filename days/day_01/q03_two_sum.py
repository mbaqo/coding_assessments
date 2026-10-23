"""
# 3. Two Sum

**Difficulty:** Easy · **Topic:** Arrays and hash maps · **Target:** 15–20 minutes

Write `two_sum(nums: list[int], target: int) -> tuple[int, int] | None`. Find two
**different** positions whose values add to `target`. Return their indexes as `(i, j)`
with `i < j`. If no pair exists, return `None`. If several pairs exist, any valid pair
is accepted.

Examples:

```text
nums=[2, 7, 11, 15], target=9 -> (0, 1)
nums=[3, 3], target=6         -> (0, 1)
nums=[1, 2, 3], target=9      -> None
```

The list may be empty and may include negative numbers or repeated values. Do not change
it. Aim for O(n) time and O(n) extra space.

## Contract and assessment

Each input list has at most 100,000 items. Integers are in the range [-10^12, 10^12].
Inputs satisfy the types and conditions above; invalid-input handling is not required.
"""

from __future__ import annotations


def two_sum(nums: list[int], target: int) -> tuple[int, int] | None:
    """Return indexes of any distinct pair summing to target, or None."""
    raise NotImplementedError

# Reflection (fill in after solving):
# Approach / invariant:
# Time complexity:
# Extra space:
# Mistake or edge case to remember:


if __name__ == "__main__":
    # Run this file from your editor or terminal to grade your answer.
    from pathlib import Path
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from practice import run_file

    raise SystemExit(run_file(__file__))
