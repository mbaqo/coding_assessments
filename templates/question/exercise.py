"""
# <global ID>. <Title>

**Difficulty:** <Easy/Medium/Hard> · **Topic:** <Patterns> · **Target:** <min–max> minutes

## Task

Implement `answer(nums: list[int]) -> bool`. Replace this example signature and
explain exact behavior, including accepted alternative outputs.

## Examples

```text
<normal input>   -> <output>
<boundary input> -> <output>
<negative case> -> <output>
```

## Contract and constraints

- Input types, value bounds, and maximum sizes: <fill in>.
- Empty inputs and missing results: <fill in>.
- Duplicates, ordering, and alternative answers: <fill in>.
- Input mutation and returned-object identity: <fill in>.
- Invalid inputs: <explicitly in or out of scope>.

## Complexity target

<Time and extra space target; define variables and output space.>

Explain a baseline, your invariant or correctness argument, and complexity.
Tests check behavior; code review checks the complexity target.
"""
from __future__ import annotations


def answer(nums: list[int]) -> bool:
    """Replace with the question's required signature and function contract."""
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
