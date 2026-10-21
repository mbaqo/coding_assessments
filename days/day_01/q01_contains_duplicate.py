"""
# 1. Contains Duplicate

**Difficulty:** Easy · **Topic:** Arrays and hash sets · **Target:** 10–15 minutes

Write `contains_duplicate(nums: list[int]) -> bool`. Return `True` if any integer occurs
at least twice, and `False` otherwise.

Examples:

```text
[1, 2, 3, 1] -> True
[1, 2, 3, 4] -> False
[]           -> False
```

The input may contain negative integers and may be empty. Do not change the input list.
Aim for O(n) time, where n is the list length. Consider what the extra space cost is.

## Contract and assessment

Each input list has at most 100,000 items. Integers are in the range [-10^12, 10^12].
Inputs satisfy the types and conditions above; invalid-input handling is not required.

Before coding, explain a simple approach and its cost. After solving, explain your
invariant, time and extra space complexity, and one boundary case you initially missed.
Tests check behavior; review your code separately to confirm the complexity target.
"""

def contains_duplicate(nums: list[int]) -> bool:
    """Return whether any value in nums occurs more than once."""
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
