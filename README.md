# Coding Interview Practice

**Open one file, read the question, write your answer, and run it.** Start with five easy Python exercises. Request the next five when ready; the bank grows with your progress. Python 3.9+ and its standard library are all you need.

## Start here

Open [question 1](days/day_01/q01_contains_duplicate.py). The prompt and examples are at the top, your answer function is directly below, and reflection notes follow it. Replace `raise NotImplementedError` with your implementation, then run the file in your editor or terminal:

```bash
python3 days/day_01/q01_contains_duplicate.py
```

This runs the exercise's full grading suite, stopping at its first failing test. The starting stub fails until you implement it. Keep the function name and signature, and leave the runner block at the bottom intact.

Record your attempt:

```bash
python3 practice.py record 1 --minutes 18 --hints 0 --confidence 4 --notes "Missed empty input"
```

Your answer is the function you write. Worked reference answers live separately in `tests/reference_solutions.py` and contain spoilers. Try independently before opening references or the grading tests.

## Your first five

| Open this exercise | Patterns | Target |
| --- | --- | --- |
| [1. Contains Duplicate](days/day_01/q01_contains_duplicate.py) | Arrays, hash sets | 10–15 min |
| [2. Valid Palindrome](days/day_01/q02_valid_palindrome.py) | Strings, two pointers | 15–20 min |
| [3. Two Sum](days/day_01/q03_two_sum.py) | Arrays, hash maps | 15–20 min |
| [4. Valid Brackets](days/day_01/q04_valid_brackets.py) | Stacks | 15–20 min |
| [5. Merge Sorted Lists](days/day_01/q05_merge_sorted_lists.py) | Sorted arrays, two pointers | 15–20 min |

These are learning targets. A “day” is a batch and can span several sessions. Question 5 uses Python lists, not linked lists.

## Useful commands

Run from the project directory. Direct exercise execution also works from another directory when you supply its full path.

| Command | Purpose |
| --- | --- |
| `python3 practice.py list` | Find exercise files, topics, and time targets |
| `python3 practice.py show 3` | Read just the prompt in the terminal |
| `python3 practice.py test 3` | Grade one answer; equivalent to running its file |
| `python3 practice.py test all --day 1` | Grade a batch, continuing to the next question after a failure |
| `python3 practice.py test all` | Grade the whole bank |
| `python3 practice.py status` | See your latest recorded outcomes |
| `python3 practice.py check` | Verify project infrastructure and grading quality |

`list`, `status`, and `test all` support `--day 1` and `--topic two-pointers`. Empty selections are errors. Both direct execution and the `test`/`record` commands accept `--full` to show all failures and `--timeout 60` to change the default 30-second limit per suite. For example:

```bash
python3 days/day_01/q03_two_sum.py --full --timeout 60
```

## How progress works

Running an exercise or `test` never changes progress. `record` grades the answer and appends the result to `progress.json`, including failures and timeouts. It preserves earlier attempts. Status reflects the latest recorded attempt; editing code does not update it automatically. Minutes and hints must be nonnegative; confidence is 1–5.

A missing progress file starts a fresh history. Malformed history is reported and preserved. Writes replace the file atomically; run one recording command at a time and back up your history. The log stores outcomes, not snapshots of your code.

Exit codes are `0` for success, `1` for failed grading/checks, `2` for command/data errors, and `130` for interruption. A failed `record` still saves the attempt.

## What lives where

```text
days/day_01/
  q01_contains_duplicate.py   Prompt + your answer + reflection + Run support
  q02_valid_palindrome.py
  ...                        Five exercises per batch
  catalog.json               Batch metadata; maintained when adding questions
  tests/                     Separate grading suites
```

You only need to edit the exercise files during practice. Each prompt has one source: its opening Python docstring. `show` reads that docstring without executing your answer, even if the function below is temporarily incomplete.

`practice.py check` verifies the catalog, progress format, runner behavior, reference answers, and rejection of representative wrong answers. It works with unfinished stubs. Syntax/import errors must still be fixed for tests to load. Tests cover examples, boundaries, exhaustive small inputs, deterministic generated cases, and large cases. Explain and review complexity separately; tests do not prove Big O.

## Get the next five

> Review my progress.json, current exercise files, and CURRICULUM.md. Generate exactly the next five questions in the next batch using CONTRIBUTING.md and the exercise template. Adapt to my weak areas, avoid duplicate problems, preserve prior work, and validate the grading suites. Here is what felt difficult: …

The next batch is `days/day_02/`, starting with `q06_…py`. Stable IDs keep your attempt history connected as the bank grows.

[Curriculum](CURRICULUM.md) · [Design document](docs/DESIGN.md) · [Authoring guide](CONTRIBUTING.md) · [Exercise template](templates/question/exercise.py)

## Daily email automation

The optional [mailer](docs/MAILER.md) sends five shared questions daily through a dedicated Gmail account, using Python in GitHub Actions and a free external timer. The repository can stay public; recipient data lives in a private Google Sheet. Replies support `PAUSE`, `PAUSE 7`, `RESUME`, and `STOP`. Emails continue without answers; this version does not track completion.

Preview an email locally without credentials or network access:

```bash
python3 -m mailer preview
```

Follow the [setup and activation guide](docs/MAILER.md) to configure Gmail, free-tier Gemini, private storage, and the scheduler. Sending is disabled in Actions until configured. The existing exercise files and practice commands remain independent.
