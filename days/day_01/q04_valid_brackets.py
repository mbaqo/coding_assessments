"""
# 4. Valid Brackets

**Difficulty:** Easy · **Topic:** Stacks · **Target:** 15–20 minutes

Write `valid_brackets(text: str) -> bool`. The input contains only `()[]{}`. Return
whether every opening bracket has a matching closing bracket in the correct order.

Examples:

```text
"()[]{}" -> True
"([{}])" -> True
"([)]"   -> False
"("      -> False
```

The empty string is valid. Aim for O(n) time. Think through both an unexpected closing
bracket and leftover opening brackets.

## Contract and assessment

The input string has at most 100,000 characters. Inputs satisfy the types and conditions
above; invalid-input handling is not required.

Before coding, explain a simple approach and its cost. After solving, explain your
invariant, time and extra space complexity, and one boundary case you initially missed.
Tests check behavior; review your code separately to confirm the complexity target.
"""

def valid_brackets(text: str) -> bool:
    """Return whether a string of round, square, and curly brackets is balanced."""
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
