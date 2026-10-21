"""
# 5. Merge Sorted Lists

**Difficulty:** Easy · **Topic:** Arrays and two pointers · **Target:** 15–20 minutes

Write `merge_sorted(left: list[int], right: list[int]) -> list[int]`. Both inputs are
sorted in nondecreasing order. Return a **new** sorted list containing every value from
both inputs, including duplicates.

Examples:

```text
[1, 2, 4], [1, 3, 4] -> [1, 1, 2, 3, 4, 4]
[], [2, 3]           -> [2, 3]
[], []               -> []
```

Do not modify either input and do not return one of the original list objects, even when
the other input is empty. Aim for O(len(left) + len(right)) time, without sorting the
combined values again.

## Contract and assessment

Each input list has at most 100,000 items. Integers are in the range [-10^12, 10^12].
Inputs satisfy the types and conditions above; invalid-input handling is not required.

Before coding, explain a simple approach and its cost. After solving, explain your
invariant, time and extra space complexity, and one boundary case you initially missed.
Tests check behavior; review your code separately to confirm the complexity target.
"""

def merge_sorted(left: list[int], right: list[int]) -> list[int]:
    """Merge two nondecreasing lists into a new nondecreasing list."""
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
