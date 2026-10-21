"""
# 2. Valid Palindrome

**Difficulty:** Easy · **Topic:** Strings and two pointers · **Target:** 15–20 minutes

Write `is_palindrome(text: str) -> bool`. Decide whether the text reads the same forward
and backward after ignoring characters outside ASCII letters (`A-Z`, `a-z`) and digits
(`0-9`), and ignoring letter case.

Examples:

```text
"A man, a plan, a canal: Panama" -> True
"race a car"                     -> False
"..."                            -> True
```

An empty cleaned string counts as a palindrome. Input may contain spaces, punctuation,
and non-ASCII characters; those non-ASCII characters are ignored. Aim for O(n) time and
O(1) extra space, apart from a few variables.

## Contract and assessment

The input string has at most 100,000 characters. Inputs satisfy the types and conditions
above; invalid-input handling is not required.

Before coding, explain a simple approach and its cost. After solving, explain your
invariant, time and extra space complexity, and one boundary case you initially missed.
Tests check behavior; review your code separately to confirm the complexity target.
"""

def is_palindrome(text: str) -> bool:
    """Check a case-insensitive palindrome using ASCII letters and digits only."""
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
