# Adding and reviewing a batch

Preserve existing prompts, solution work, IDs, and attempt history. Only add the next five questions when requested. Read `CURRICULUM.md`, `progress.json`, and the current solutions before deciding topics and difficulty.

## Structure

Use the next available global integer ID, not a number that resets every day. IDs are permanent keys in progress history. Name files `days/day_02/q06_descriptive_name.py`, continuing past 99 as needed. The runner sorts IDs numerically.

Each batch has this layout:

```text
q06_descriptive_name.py            Prompt docstring + answer stub + reflection + runner
q07_another_question.py            Four more exercise files complete the batch
catalog.json                      List of metadata objects, one for each exercise
tests/test_q06_descriptive_name.py unittest suite importing the exercise function
tests/test_q07_another_question.py One suite per exercise
__init__.py                       Empty package marker
tests/__init__.py                 Empty package marker
```

Copy `templates/question/exercise.py` for each question. Fill the opening docstring, replace the function signature, and keep the reflection comments and direct-run block. The prompt exists only in that docstring; do not create a separate prompt Markdown file. Keep imports after the docstring and before the answer. Do not put test execution or sample calls at module scope; importing an exercise must not run it.

Copy the object in `templates/question/catalog-entry.json` into the new batch's `catalog.json` list, filling its file name, ID, and metadata. Add one entry per exercise. Catalog validation rejects duplicate IDs, missing exercise/test files, and files omitted from the catalog. Catalog data is deliberately outside learner files so an incomplete answer does not break discovery.

Create `tests/test_qNN_slug.py` with `from ..qNN_slug import function_name`. The runner imports that suite and keeps grading separate from the learner's editable file. Add a short batch README describing why those five questions were selected, without giving away answers.

## Prompt review

Specify exact return types, accepted alternative outputs, empty-input behavior, value and size bounds, ordering, duplicate handling, and mutation/identity requirements. State whether invalid inputs are in scope. Use compatible Python 3.9 syntax; add `from __future__ import annotations` when using deferred union annotations. Distinguish required behavior from performance targets. Avoid unexplained rules that only appear in tests.

Keep hints and reference solutions out of prompts and stubs. A topic tag is a study cue; it is intentionally visible in learning mode.

## Test review

- Cover each example and each explicit contract rule, plus negative and boundary cases.
- Check types where Python equality would accept a wrong result, such as `True == 1`.
- Check non-mutation and fresh-result identity if required.
- For multiple valid answers, validate membership in the valid result set instead of demanding one answer.
- Enumerate small inputs against a simple independent oracle when practical.
- Use fixed seeds for generated cases; include constructive positive cases when random inputs mostly produce negatives.
- Add large cases with known answers or efficient oracles. Do not use a quadratic oracle on a 100,000-element input.
- Avoid strict elapsed-time assertions. The CLI timeout stops stuck runs, but it does not prove Big O.

Add the new reference function to `tests/reference_solutions.py` and its ID to `REFERENCES`. Add at least two realistic incorrect implementations to `MUTANTS` in `tests/test_question_suites.py`. The maintainer check patches the imported answer in each test module, so use `from ..qNN_slug import function_name` and test that name directly. More complex future signatures may need a richer verification adapter; document that when introduced.

Negative controls should fail assertions rather than crash the test harness. They are sampled regression checks, not exhaustive mutation analysis. Include another correct implementation when multiple outputs or approaches could be incorrectly rejected.

## Validation before delivery

Run `python3 practice.py check` and resolve failures. Confirm `list --day N` shows exactly the intended five, `show ID` reads correctly, and the new stubs remain unfinished. Run a new exercise file directly to confirm its runner reaches the expected unfinished-answer failure. Check that existing progress remains unchanged. The check requires reference and negative-control entries for every discovered question; it does not require learner solutions to pass. Syntax/import errors in exercise modules still need fixing because grading tests import those modules. `list` and `show` remain usable while an answer is incomplete; `show` reads only the opening docstring.

Never fill in learner solutions just to make project validation green. Never edit progress history to manufacture successful attempts. Report the scope actually verified, including manual complexity review and remaining coverage gaps.
