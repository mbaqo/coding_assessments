"""Practice coding questions, run checks, and record local attempt history."""
from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import tokenize

ROOT = Path(__file__).resolve().parent
PROGRESS = ROOT / "progress.json"
DEFAULT_TIMEOUT = 30.0


@dataclass(frozen=True)
class Question:
    id: str
    day: str
    slug: str
    title: str
    difficulty: str
    topics: tuple[str, ...]
    target_minutes: tuple[int, int]
    entry_point: str

    @property
    def module(self) -> str:
        return f"days.{self.day}.tests.test_{self.slug}"

    @property
    def path(self) -> Path:
        return Path("days") / self.day / f"{self.slug}.py"


class PracticeError(ValueError):
    """An actionable catalog or progress-file error."""


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise PracticeError(f"Cannot read {path}: {error}") from error


def integer(value, minimum=0):
    return type(value) is int and value >= minimum


def read_prompt(path: Path) -> str:
    """Read the opening docstring without importing or parsing the learner's answer."""
    try:
        with tokenize.open(path) as handle:
            tokens = tokenize.generate_tokens(handle.readline)
            for token in tokens:
                if token.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE):
                    continue
                if token.type == tokenize.STRING:
                    value = ast.literal_eval(token.string)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                break
    except (OSError, SyntaxError, ValueError, tokenize.TokenError) as error:
        raise PracticeError(f"Cannot read prompt in {path}: {error}") from error
    raise PracticeError(f"Missing opening prompt docstring in {path}")


def discover_questions(root: Path = ROOT) -> dict[str, Question]:
    found = {}
    bank = root / "days"
    if not (bank / "__init__.py").is_file():
        raise PracticeError("Missing days/__init__.py")
    for day in sorted(bank.glob("day_*")):
        if not day.is_dir():
            continue
        if not re.fullmatch(r"day_\d{2,}", day.name) or int(day.name[4:]) < 1:
            raise PracticeError(f"Invalid batch directory: {day.name}")
        for filename in ("__init__.py", "tests/__init__.py", "catalog.json"):
            if not (day / filename).is_file():
                raise PracticeError(f"Missing {day / filename}")
        entries = load_json(day / "catalog.json")
        if not isinstance(entries, list) or not entries:
            raise PracticeError(f"Catalog must be a nonempty list: {day}/catalog.json")
        registered_files = set()
        for data in entries:
            location = day / "catalog.json"
            if not isinstance(data, dict):
                raise PracticeError(f"Catalog entries must be objects: {location}")
            filename = data.get("file")
            match = re.fullmatch(r"q(\d+)_[a-z][a-z0-9_]*\.py", filename) if isinstance(filename, str) else None
            if not match or int(match[1]) < 1:
                raise PracticeError(f"Invalid exercise filename in {location}: {filename}")
            number = str(int(match[1]))
            if number in found:
                raise PracticeError(f"Duplicate question number: {number}")
            valid = (
                integer(data.get("id"), 1) and str(data["id"]) == number
                and isinstance(data.get("title"), str) and data["title"].strip()
                and data.get("difficulty") in ("easy", "medium", "hard")
                and isinstance(data.get("topics"), list) and data["topics"]
                and all(isinstance(t, str) and re.fullmatch(r"[a-z]+(?:-[a-z]+)*", t) for t in data["topics"])
                and isinstance(data.get("target_minutes"), list) and len(data["target_minutes"]) == 2
                and all(integer(m, 1) for m in data["target_minutes"])
                and data["target_minutes"][0] <= data["target_minutes"][1]
                and isinstance(data.get("entry_point"), str)
                and re.fullmatch(r"[a-z][a-z0-9_]*", data["entry_point"])
            )
            if not valid:
                raise PracticeError(f"Invalid metadata for {filename} in {location}")
            for required in (day / filename, day / "tests" / f"test_{filename}"):
                if not required.is_file():
                    raise PracticeError(f"Missing {required}")
            registered_files.add(filename)
            found[number] = Question(
                number, day.name, Path(filename).stem, data["title"], data["difficulty"],
                tuple(data["topics"]), tuple(data["target_minutes"]), data["entry_point"],
            )
        actual_files = {p.name for p in day.glob("q*.py")}
        if actual_files != registered_files:
            raise PracticeError(f"Unregistered exercise files in {day}: {sorted(actual_files - registered_files)}")
        expected_tests = {f"test_{name}" for name in registered_files}
        actual_tests = {p.name for p in (day / "tests").glob("test_*.py")}
        if actual_tests != expected_tests:
            raise PracticeError(f"Unregistered test files in {day}: {sorted(actual_tests - expected_tests)}")
    if not found:
        raise PracticeError("No questions found in days/")
    return dict(sorted(found.items(), key=lambda item: int(item[0])))


def run_file(filename: str) -> int:
    """Let an exercise's Run button use the same isolated grader as the CLI."""
    path = Path(filename).resolve()
    try:
        question = next((q for q in discover_questions().values() if ROOT / q.path == path), None)
        if question is None:
            raise PracticeError(f"Exercise is not registered: {path}")
    except (PracticeError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    return main(["test", question.id, *sys.argv[1:]])


# A separate interpreter isolates imports and lets the parent stop infinite loops.
# Count tests explicitly: unittest otherwise reports an empty suite as successful.
TEST_WORKER = """
import sys, unittest
suite = unittest.defaultTestLoader.loadTestsFromName(sys.argv[1])
if suite.countTestCases() == 0:
    print('ERROR: No tests discovered', file=sys.stderr)
    sys.exit(2)
result = unittest.TextTestRunner(verbosity=2, failfast=sys.argv[2] == 'fast').run(suite)
sys.exit(0 if result.wasSuccessful() else 1)
"""


def test_question(question: Question, timeout=DEFAULT_TIMEOUT, full=False) -> bool:
    print(f"\nQuestion {question.id}: {question.title}", flush=True)
    try:
        result = subprocess.run(
            [sys.executable, "-c", TEST_WORKER, question.module, "full" if full else "fast"],
            cwd=ROOT, check=False, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT: question {question.id} exceeded {timeout:g}s. Check for an infinite loop.", flush=True)
        return False
    return result.returncode == 0


def read_attempts(path: Path = PROGRESS) -> list[dict]:
    if not path.exists():
        return []
    data = load_json(path)
    if not isinstance(data, dict) or not isinstance(data.get("attempts"), list):
        raise PracticeError(f"Invalid progress format in {path}; expected an attempts list. File left unchanged.")
    for index, entry in enumerate(data["attempts"], 1):
        valid = (
            isinstance(entry, dict)
            and isinstance(entry.get("question"), str) and re.fullmatch(r"[1-9]\d*", entry["question"])
            and isinstance(entry.get("date"), str)
            and integer(entry.get("minutes")) and integer(entry.get("hints"))
            and integer(entry.get("confidence"), 1) and entry["confidence"] <= 5
            and type(entry.get("passed")) is bool
            and isinstance(entry.get("notes"), str)
        )
        if valid:
            try:
                valid = datetime.fromisoformat(entry["date"]).utcoffset() is not None
            except ValueError:
                valid = False
        if not valid:
            raise PracticeError(f"Invalid attempt {index} in {path}. File left unchanged.")
    return data["attempts"]


def write_attempts(attempts: list[dict], path: Path = PROGRESS):
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=".progress-", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps({"attempts": attempts}, indent=2) + "\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def positive_timeout(value):
    try:
        result = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("timeout must be a positive finite number")
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("timeout must be a positive finite number")
    return result


def add_filters(parser):
    parser.add_argument("--day", type=int, help="Select a batch number, e.g. 1")
    parser.add_argument("--topic", help="Select a topic tag, e.g. two-pointers")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    listing = commands.add_parser("list", help="List questions and their exercise paths")
    add_filters(listing)
    show = commands.add_parser("show", help="Read a prompt without opening its tests")
    show.add_argument("question")
    test = commands.add_parser("test", help="Grade solutions without recording progress")
    test.add_argument("question", help="Global question number or all")
    add_filters(test)
    record = commands.add_parser("record", help="Grade and record one attempt")
    record.add_argument("question")
    record.add_argument("--minutes", type=int, required=True)
    record.add_argument("--hints", type=int, default=0)
    record.add_argument("--confidence", type=int, choices=range(1, 6), required=True)
    record.add_argument("--notes", default="")
    for command in (test, record):
        command.add_argument("--timeout", type=positive_timeout, default=DEFAULT_TIMEOUT,
                             help="Seconds per question (default: 30)")
        command.add_argument("--full", action="store_true", help="Continue after the first failing test")
    status = commands.add_parser("status", help="Summarize latest attempts, including untouched questions")
    add_filters(status)
    commands.add_parser("check", help="Validate catalog, progress, and infrastructure (does not grade your answers)")
    args = parser.parse_args(argv)
    try:
        questions = discover_questions()
        if args.command == "check":
            read_attempts()
            for question in questions.values():
                read_prompt(ROOT / question.path)
            print(f"Catalog valid: {len(questions)} questions. Checking infrastructure and test suites…", flush=True)
            result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"],
                                    cwd=ROOT, check=False, timeout=120)
            return 0 if result.returncode == 0 else 1
        selected = {n: q for n, q in questions.items()
                    if (getattr(args, "day", None) is None or int(q.day[4:]) == args.day)
                    and (getattr(args, "topic", None) is None or args.topic in q.topics)}
        if hasattr(args, "question") and args.question != "all":
            if args.question not in selected:
                parser.error(f"Unknown question or excluded by filters: {args.question}")
            selected = {args.question: selected[args.question]}
        if not selected or (args.command in ("show", "record") and args.question == "all"):
            parser.error("No matching questions; show and record require a single question number")
        if args.command == "list":
            for number, q in selected.items():
                print(f"{number}. {q.title} [{q.difficulty}; {', '.join(q.topics)}; "
                      f"{q.target_minutes[0]}–{q.target_minutes[1]} min]\n   {q.path}")
            return 0
        if args.command == "show":
            print(read_prompt(ROOT / selected[args.question].path))
            return 0
        if args.command == "test":
            results = [test_question(q, args.timeout, args.full) for q in selected.values()]
            print(f"\nPassed: {sum(results)}/{len(results)} questions")
            return 0 if all(results) else 1
        if args.command == "record":
            if args.minutes < 0 or args.hints < 0:
                parser.error("--minutes and --hints must be nonnegative")
            attempts = read_attempts()  # Validate before spending time grading.
            passed = test_question(selected[args.question], args.timeout, args.full)
            attempts.append({"question": args.question, "date": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                             "minutes": args.minutes, "hints": args.hints, "confidence": args.confidence,
                             "passed": passed, "notes": args.notes})
            write_attempts(attempts)
            print(f"Recorded question {args.question}: {'passed' if passed else 'failed'}")
            return 0 if passed else 1
        attempts = read_attempts()
        for number, q in selected.items():
            history = [entry for entry in attempts if entry["question"] == number]
            state = "not attempted"
            if history:
                latest = history[-1]
                state = "passed" if latest["passed"] else "needs work"
                state += (f"; {len(history)} attempt(s), latest {latest['minutes']} min, "
                          f"{latest['hints']} hint(s), confidence {latest['confidence']}/5")
            print(f"{number}. {q.title}: {state}")
        return 0
    except (PracticeError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 2
    except subprocess.TimeoutExpired:
        print("Error: project checks exceeded 120 seconds", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("\nInterrupted; no attempt recorded.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
