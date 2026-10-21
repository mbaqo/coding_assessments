# Coding Interview Practice — Design Document

Status: implemented single-file exercise workflow, 2026-10-20.

## Purpose and scope

Build a personal, progressively expanding question bank that develops independent coding assessment skills. Each requested batch adds five complete exercises with clear contracts and reliable tests. Progress and learner feedback guide later topic choices. The initial release contains exactly five easy problems.

Success means the learner can solve unseen variants, explain correctness and complexity, and debug under time pressure. A green test suite is one signal, alongside hints, time, confidence, and explanation quality.

The current product is a local Python command-line workflow using only the standard library. A website, hosted accounts, automatic problem generation, automatic scheduling, multi-language grading, and a full SWE theory curriculum are outside this baseline. These can become separate extensions when needed.

## User journey

```mermaid
flowchart LR
    A[List or filter questions] --> B[Read prompt]
    B --> C[Clarify and plan]
    C --> D[Write answer beneath prompt]
    D --> E[Run the exercise file]
    E --> F[Debug and explain complexity]
    F --> G[Record attempt]
    G --> H[Review progress and retry]
    H --> I[Request next five]
    I --> A
```

Each exercise is one Python file: the opening docstring contains its prompt and examples, followed by the answer function, reflection comments, and a guarded runner block. Running that file from an editor or terminal invokes grading. Reading prompts does not require opening test files. The default grader stops at the first failure for a question, reducing noise. A batch run still grades every selected question. Full failure output is optional. Solutions remain learner-owned; maintainers verify suites with separate reference implementations.

## Repository layout

```text
practice.py                       CLI, discovery, grading, history, direct-run helper
README.md                         First-session instructions and command reference
CURRICULUM.md                     Topic progression and adaptation rules
CONTRIBUTING.md                   Authoring and validation protocol
progress.json                     Append-only-by-convention attempt history
days/
  __init__.py
  day_01/
    __init__.py
    catalog.json                  Metadata list for the five exercises
    q01_contains_duplicate.py     Prompt + answer + reflection + direct-run block
    q02_valid_palindrome.py
    q03_two_sum.py
    q04_valid_brackets.py
    q05_merge_sorted_lists.py
    tests/
      __init__.py
      test_q01_contains_duplicate.py
      ... one suite per exercise
tests/
  test_practice.py                 Catalog, CLI, persistence, direct-run checks
  test_question_suites.py          Reference and negative-control verification
  reference_solutions.py           Maintainer answers; contains spoilers
templates/question/
  exercise.py                     Complete reusable exercise file
  catalog-entry.json              Metadata object to add to the batch catalog
docs/DESIGN.md                    This document
```

The learner works in one file per question. Grouping files by batch keeps navigation short as the bank grows. Tests live in a separate batch subfolder, and catalog metadata is maintained once per batch. Adding a batch does not require editing the runner. Keep the CLI in one module while it is small; extract separate interfaces when responsibilities become more complex. There is no need for a database at the current scale.

## Why combine the prompt and answer

A separate prompt and solution requires switching files to recheck constraints. Keeping the full prompt in the exercise's opening docstring places the contract directly above the code. Reflection comments encourage explaining correctness and complexity in the same workspace. The prompt has one canonical source; `show` reads it instead of maintaining a second Markdown copy.

The `read_prompt` helper tokenizes only far enough to read the opening string literal. It does not import or execute the exercise, and it does not parse the answer below. This allows viewing prompts even with temporarily incomplete syntax in an answer. A missing or malformed opening docstring produces an actionable error.

Grading suites and worked reference answers remain separate to reduce accidental spoilers and accidental changes to grading rules. Combining tests into the editable exercise would make the file longer and mix learner work with the checks that assess it. A notebook would add tooling and execution-state complexity without a current need for interactive visual output.

## Catalog and identity

Each batch has a `days/day_NN/catalog.json` list; there is no separate global index. Discovery validates package markers, required exercise/test files, directory and file naming, unique positive global IDs, and metadata. It rejects unregistered exercise files and unmatched test files rather than silently skipping them. Numeric sorting works beyond question 99. IDs need not be contiguous, but new batches should use the next available numbers and preserve existing IDs.

| Field | Type and rule | Purpose |
| --- | --- | --- |
| `file` | `qNN_slug.py`, with no path separators | Exercise file within its batch |
| `id` | Positive integer matching the filename ID | Permanent history key |
| `title` | Nonempty string | Display label |
| `difficulty` | `easy`, `medium`, or `hard` | Learning progression |
| `topics` | Nonempty list of lowercase hyphenated tags | Filtering and manual adaptation |
| `target_minutes` | Two positive integers, low ≤ high | Suggested practice window |
| `entry_point` | Lowercase Python-style function name | Reference-test adapter |

Day folders are batches, not dates or deadlines. Paths locate implementation files; global IDs identify exercises across history. Renaming a title does not invalidate attempts. Changing an established question's contract requires careful review, because old passes describe the earlier contract. Future contract versioning should be introduced before such changes become common.

## Grading execution

Running an exercise calls `run_file(__file__)`, which resolves its registered global ID and invokes the same `test` command. Optional `--full` and `--timeout` arguments are forwarded. The guarded block locates the repository relative to the file, allowing execution from another working directory. Importing an exercise for grading does not trigger its runner. Direct execution is equivalent to `test` and never records progress.

`test` launches a fresh Python subprocess for each question with the same interpreter as the CLI and the repository root as its working directory. This isolates ordinary module state between questions and allows a per-question timeout. The child loads the named unittest module, rejects an empty suite, runs it, and returns a success/failure code. Import errors, assertion failures, and timeouts produce a failed grade. Test output remains visible for debugging.

The default timeout is 30 seconds for the entire question suite. `--timeout` accepts a positive finite number. This is a guard against stuck code, not a benchmark or a security sandbox. Learner code is trusted local code; it can access local files and start processes. The timeout terminates the grading interpreter, not an arbitrary process tree created by a solution. Directly running an exercise executes its top-level code before invoking the grader, so the timeout protects answer evaluation in the grading subprocess; keep work inside functions and avoid top-level sample calls.

`--full` disables fail-fast behavior inside a question. A batch aggregates results without stopping after the first failed question. `test` has no progress side effects. CLI selectors reject unknown IDs and empty filter results, preventing a misleading zero-question success.

## Progress storage

The existing JSON structure is retained:

```json
{
  "attempts": [
    {
      "question": "1",
      "date": "2026-10-20T12:00:00+00:00",
      "minutes": 18,
      "hints": 0,
      "confidence": 4,
      "passed": false,
      "notes": "Missed a boundary case"
    }
  ]
}
```

`record` validates history before grading, then appends an outcome with a UTC timestamp. Minutes and hints are nonnegative integers; confidence is 1–5. A timed-out run is stored as a failed attempt. The boolean outcome does not distinguish timeout, import error, and assertion failure; notes can preserve that detail. An interruption before saving records no attempt.

Writes use a temporary file in the same directory followed by atomic replacement, so a failed replacement leaves the previous JSON intact. Temporary files are cleaned up. This prevents partially written JSON during replacement; it is not a guarantee against every power-loss scenario. There is no file lock: concurrent `record` commands can lose one writer's update, so the supported workflow has one writer at a time.

A missing file means no recorded attempts. Malformed JSON or invalid entries produce an actionable error and are never automatically reset. Historical entries for IDs outside the current catalog remain stored but are not shown in the current-question status list. Status reflects the latest record, and may be stale after editing a solution. Source-code snapshots and backups remain the learner's responsibility.

## Verification strategy

Two layers have different purposes:

| Layer | Command | Expected state with untouched stubs |
| --- | --- | --- |
| Learner grading | Run an exercise file, or `python3 practice.py test all` | Fails with `NotImplementedError` |
| Project verification | `python3 practice.py check` | Passes using maintainer references |

The project check validates the catalog, prompt docstrings, and progress, then runs infrastructure tests and suite verification. It patches each test module's imported function with a reference implementation only in memory. It never writes learner answers or attempts. All current question IDs must have references and representative incorrect implementations registered. Question modules must still import successfully; syntax errors in learner code can therefore fail project verification.

| Question | Main coverage |
| --- | --- |
| Contains Duplicate | Empty/singleton lists, signs and large integers, exhaustive small lists, generated unique/duplicate cases, non-mutation, late duplicates and 100,000 unique values |
| Valid Palindrome | Empty cleaned text, case/digit comparisons, punctuation, ASCII-only filtering before case conversion, exhaustive and seeded strings, 100,000-character cases |
| Two Sum | Distinct indexes, duplicate values, absent/multiple pairs, strict index types, non-mutation, exhaustive small lists/targets, generated inputs, large known-answer cases |
| Valid Brackets | Empty input, wrong order/type, leftover opens/closes, exhaustive short strings, generated balanced/unbalanced strings, deep nesting and long sequences |
| Merge Sorted Lists | Empty lists, duplicates, unequal lengths, fresh output, unchanged inputs, aliased inputs, exhaustive small sorted pairs, generated and large lists |

Small-case oracles prioritize clarity and independence. Large-case oracles use known results or efficient computations so validation itself does not become the bottleneck. Generated cases use fixed seeds. Explicitly constructed successful cases supplement random sampling where positives would otherwise be rare.

Suite verification runs correct references through all question cases and checks that representative mistakes fail assertions. It also checks an alternative correct Two Sum implementation, protecting acceptance of multiple valid pairs. These negative controls are not exhaustive mutation testing.

Infrastructure checks cover duplicate/malformed IDs, missing or unregistered files, invalid metadata, prompt extraction without executing incomplete code, absent/corrupt history, failed replacement, history preservation, filters, prompts, latest-attempt status, bad CLI values, timeout handling, empty test suites, direct-run argument forwarding, and execution of every exercise from another directory. Test fixtures use temporary files or mocks rather than writing actual progress.

Limitations: finite tests cannot prove correctness for all inputs. Large cases and timeouts cannot certify asymptotic complexity, constant extra space, or a ban on re-sorting. Review code and ask for an explanation to assess those requirements. Invalid inputs are deliberately outside the initial question contracts.

## Expansion process

1. Review history, current solution quality, and learner feedback.
2. Choose exactly five fresh problems using `CURRICULUM.md`; describe the rationale in the new batch README.
3. Create the next batch with stable global IDs, five combined exercise files, a catalog, and corresponding tests.
4. Review every contract against its tests, including accepted alternative results.
5. Register maintainer references and negative controls; leave learner stubs unfinished.
6. Run the project check, inspect the new batch listing and prompts, verify direct execution, and report results.

Future features should follow demonstrated needs: richer attempt outcomes and contract versions, manual review queues, stdin/stdout assessment fixtures, then optional timed mixed sessions. Add a storage schema version and migration tests before incompatible history changes. Multi-language execution would require a separate runner interface and language-specific fixtures. Hosted execution would require a genuine sandbox and a different security design.

## Acceptance criteria for this baseline

- Exactly five easy exercise files combining prompts, answer stubs, reflection, and direct execution, with separate deterministic grading suites.
- A one-file practice flow plus commands for later batches and topic review. Prompt viewing remains usable with incomplete answers.
- Fresh subprocess grading, explicit empty-suite rejection, and bounded execution.
- Persistent valid attempt history, preserved on malformed-data and failed-replacement paths.
- Project verification succeeds independently of unfinished learner answers.
- Documented template and review protocol support the next five without changing discovery logic.
- No claim that passing tests alone proves mastery or optimal complexity.
