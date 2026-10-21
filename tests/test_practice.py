import contextlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import practice


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.day = self.root / 'days/day_01'
        (self.day / 'tests').mkdir(parents=True)
        (self.root / 'days/__init__.py').touch()
        (self.day / '__init__.py').touch()
        (self.day / 'tests/__init__.py').touch()
        question = practice.discover_questions()['1']
        self.question = self.day / question.path.name
        shutil.copy2(practice.ROOT / question.path, self.question)
        source_tests = practice.ROOT / question.path.parent / 'tests' / f'test_{question.path.name}'
        shutil.copy2(source_tests, self.day / 'tests' / source_tests.name)
        entries = json.loads((practice.ROOT / question.path.parent / 'catalog.json').read_text())
        self.entry = next(entry for entry in entries if entry['id'] == 1)
        self.catalog = self.day / 'catalog.json'
        self.catalog.write_text(json.dumps([self.entry]))

    def test_catalog_order_and_metadata(self):
        questions = practice.discover_questions(self.root)
        self.assertEqual(list(questions), ['1'])
        self.assertEqual(questions['1'].entry_point, 'contains_duplicate')
        self.assertEqual(questions['1'].path.suffix, '.py')

    def test_new_batches_and_three_digit_ids_sort_numerically(self):
        day = self.root / 'days/day_02'
        (day / 'tests').mkdir(parents=True)
        (day / '__init__.py').touch()
        (day / 'tests/__init__.py').touch()
        entries = []
        for number in (100, 2):
            filename = f'q{number:02d}_example.py'
            shutil.copy2(self.question, day / filename)
            (day / 'tests' / f'test_{filename}').touch()
            entries.append(dict(self.entry, id=number, file=filename))
        (day / 'catalog.json').write_text(json.dumps(entries))
        self.assertEqual(list(practice.discover_questions(self.root)), ['1', '2', '100'])

    def test_duplicate_ids_rejected(self):
        self.catalog.write_text(json.dumps([self.entry, self.entry]))
        with self.assertRaisesRegex(practice.PracticeError, 'Duplicate'):
            practice.discover_questions(self.root)

    def test_missing_required_file_rejected(self):
        (self.day / 'tests' / f'test_{self.question.name}').unlink()
        with self.assertRaisesRegex(practice.PracticeError, 'Missing'):
            practice.discover_questions(self.root)

    def test_invalid_metadata_rejected(self):
        for key, value in [('id', 99), ('id', True), ('topics', []), ('difficulty', 'unknown'),
                           ('target_minutes', [20, 10]), ('entry_point', 'not valid'),
                           ('file', '../outside.py'), ('file', 'q_bad.py')]:
            with self.subTest(key=key, value=value):
                self.catalog.write_text(json.dumps([dict(self.entry, **{key: value})]))
                with self.assertRaises(practice.PracticeError):
                    practice.discover_questions(self.root)

    def test_invalid_catalog_shape_rejected(self):
        for data in ({}, [], [None]):
            with self.subTest(data=data):
                self.catalog.write_text(json.dumps(data))
                with self.assertRaises(practice.PracticeError):
                    practice.discover_questions(self.root)

    def test_empty_catalog_rejected(self):
        shutil.rmtree(self.day)
        with self.assertRaisesRegex(practice.PracticeError, 'No questions'):
            practice.discover_questions(self.root)

    def test_unregistered_exercise_rejected(self):
        (self.day / 'q02_unregistered.py').touch()
        with self.assertRaisesRegex(practice.PracticeError, 'Unregistered exercise'):
            practice.discover_questions(self.root)

    def test_unregistered_tests_rejected(self):
        (self.day / 'tests/test_q02_unregistered.py').touch()
        with self.assertRaisesRegex(practice.PracticeError, 'Unregistered test'):
            practice.discover_questions(self.root)

    def test_incomplete_answer_does_not_break_catalog_or_prompt(self):
        self.question.write_text('"""Readable prompt."""\ndef unfinished(\n')
        self.assertEqual(list(practice.discover_questions(self.root)), ['1'])
        self.assertEqual(practice.read_prompt(self.question), 'Readable prompt.')

    def test_reading_prompt_never_executes_exercise(self):
        self.question.write_text('# comment\n\n"""Read me."""\nraise RuntimeError("do not run")\n')
        self.assertEqual(practice.read_prompt(self.question), 'Read me.')

    def test_missing_or_malformed_prompt_is_actionable(self):
        for text in ('def answer(): pass', '"""', '"""   """', 'b"bytes"'):
            with self.subTest(text=text):
                self.question.write_text(text)
                with self.assertRaises(practice.PracticeError):
                    practice.read_prompt(self.question)


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'progress.json'
        self.entry = dict(question='1', date='2026-10-20T12:00:00+00:00', minutes=15,
                          hints=0, confidence=3, passed=False, notes='boundary case')

    def test_missing_file_starts_empty(self):
        self.assertEqual(practice.read_attempts(self.path), [])

    def test_round_trip_and_append(self):
        practice.write_attempts([self.entry], self.path)
        attempts = practice.read_attempts(self.path)
        attempts.append(dict(self.entry, passed=True))
        practice.write_attempts(attempts, self.path)
        self.assertEqual(practice.read_attempts(self.path), [self.entry, dict(self.entry, passed=True)])

    def test_invalid_progress_is_preserved(self):
        for contents in ('{broken', '[]', '{}', '{"attempts": [null]}', '{"attempts": {}}'):
            with self.subTest(contents=contents):
                self.path.write_text(contents)
                with self.assertRaises(practice.PracticeError):
                    practice.read_attempts(self.path)
                self.assertEqual(self.path.read_text(), contents)

    def test_invalid_attempt_fields_rejected(self):
        for key, value in [('question', '01'), ('date', 'invalid'), ('date', '2026-10-20'),
                           ('minutes', -1), ('hints', True), ('confidence', 6), ('passed', 'yes')]:
            with self.subTest(key=key):
                self.path.write_text(json.dumps({'attempts': [dict(self.entry, **{key: value})]}))
                with self.assertRaises(practice.PracticeError):
                    practice.read_attempts(self.path)

    def test_failed_replace_preserves_old_progress_and_cleans_temporary(self):
        practice.write_attempts([self.entry], self.path)
        before = self.path.read_bytes()
        with patch.object(Path, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                practice.write_attempts([], self.path)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.glob('.progress-*')), [])


class CommandTests(unittest.TestCase):
    def invoke(self, args):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = practice.main(args)
        return code, out.getvalue()

    def test_list_filter(self):
        code, output = self.invoke(['list', '--day', '1', '--topic', 'hash-map'])
        self.assertEqual(code, 0)
        self.assertIn('3. Two Sum', output)
        self.assertNotIn('1. Contains Duplicate', output)

    def test_show_prompt(self):
        code, output = self.invoke(['show', '1'])
        self.assertEqual(code, 0)
        self.assertIn('# 1. Contains Duplicate', output)

    def test_unknown_or_empty_selection_is_an_error(self):
        for args in (['test', '99999'], ['test', 'all', '--day', '99999'], ['record', 'all', '--minutes', '1', '--confidence', '3']):
            with self.subTest(args=args), self.assertRaises(SystemExit) as caught:
                self.invoke(args)
            self.assertEqual(caught.exception.code, 2)

    def test_invalid_timing_rejected_before_tests(self):
        for value in ('0', '-1', 'nan', 'inf', 'bad'):
            with self.subTest(value=value), patch('practice.test_question') as run:
                with self.assertRaises(SystemExit):
                    self.invoke(['test', '1', '--timeout', value])
                run.assert_not_called()

    def test_all_runs_remaining_questions_after_failure(self):
        count = len(practice.discover_questions())
        with patch('practice.test_question', side_effect=[False] + [True] * (count - 1)) as run:
            code, output = self.invoke(['test', 'all'])
        self.assertEqual(code, 1)
        self.assertEqual(run.call_count, count)
        self.assertIn(f'Passed: {count - 1}/{count}', output)

    def test_record_preserves_history_and_saves_failed_attempts(self):
        for passed in (True, False):
            prior = [dict(question='1', notes='older')]
            with self.subTest(passed=passed), patch('practice.read_attempts', return_value=prior.copy()), \
                 patch('practice.write_attempts') as write, patch('practice.test_question', return_value=passed):
                code, _ = self.invoke(['record', '1', '--minutes', '12', '--confidence', '4', '--notes', 'new'])
                self.assertEqual(code, 0 if passed else 1)
                saved = write.call_args.args[0]
                self.assertEqual(saved[0], prior[0])
                self.assertEqual(saved[1]['passed'], passed)
                self.assertEqual(saved[1]['notes'], 'new')

    def test_bad_progress_prevents_grading_and_writing(self):
        with patch('practice.read_attempts', side_effect=practice.PracticeError('bad history')), \
             patch('practice.test_question') as run, patch('practice.write_attempts') as write:
            code, _ = self.invoke(['record', '1', '--minutes', '12', '--confidence', '4'])
        self.assertEqual(code, 2)
        run.assert_not_called()
        write.assert_not_called()

    def test_negative_minutes_rejected(self):
        with patch('practice.test_question') as run:
            with self.assertRaises(SystemExit):
                self.invoke(['record', '1', '--minutes', '-1', '--confidence', '3'])
            run.assert_not_called()

    def test_test_does_not_write_progress(self):
        with patch('practice.test_question', return_value=True), patch('practice.write_attempts') as write:
            self.assertEqual(self.invoke(['test', '1'])[0], 0)
            write.assert_not_called()

    def test_status_uses_latest_attempt(self):
        history = [dict(question='1', passed=True, minutes=10, hints=0, confidence=5),
                   dict(question='1', passed=False, minutes=20, hints=2, confidence=2)]
        with patch('practice.read_attempts', return_value=history):
            code, output = self.invoke(['status', '--topic', 'hash-set'])
        self.assertEqual(code, 0)
        self.assertIn('needs work; 2 attempt(s), latest 20 min, 2 hint(s), confidence 2/5', output)

    def test_timeout_is_a_failure(self):
        with patch('practice.subprocess.run', side_effect=subprocess.TimeoutExpired('test', 1)), \
             contextlib.redirect_stdout(io.StringIO()):
            self.assertFalse(practice.test_question(practice.discover_questions()['1'], timeout=1))

    def test_real_infinite_loop_is_terminated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'infinite.py').write_text(
                'import unittest\nclass Stuck(unittest.TestCase):\n'
                '    def test_stuck(self):\n        while True:\n            pass\n')
            question = SimpleNamespace(id='fixture', title='Timeout fixture', module='infinite')
            output = io.StringIO()
            with patch('practice.ROOT', root), contextlib.redirect_stdout(output):
                self.assertFalse(practice.test_question(question, timeout=0.2))
            self.assertIn('TIMEOUT', output.getvalue())

    def test_worker_rejects_an_empty_suite(self):
        result = subprocess.run([sys.executable, '-c', practice.TEST_WORKER, 'json', 'fast'],
                                capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 2)
        self.assertIn('No tests discovered', result.stderr)

    def test_cli_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run([sys.executable, str(practice.ROOT / 'practice.py'), 'show', '1'],
                                    cwd=directory, capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Contains Duplicate', result.stdout)


class DirectRunTests(unittest.TestCase):
    def test_run_file_routes_to_the_registered_question(self):
        question = practice.discover_questions()['1']
        with patch('practice.main', return_value=1) as main, patch('sys.argv', ['exercise.py', '--timeout', '5']):
            self.assertEqual(practice.run_file(str(practice.ROOT / question.path)), 1)
        main.assert_called_once_with(['test', '1', '--timeout', '5'])

    def test_unregistered_file_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(practice.run_file(str(practice.ROOT / 'unknown.py')), 2)

    def test_every_exercise_can_run_from_another_directory(self):
        # --help checks the actual entry point without grading learner answers.
        with tempfile.TemporaryDirectory() as directory:
            for question in practice.discover_questions().values():
                with self.subTest(question=question.id):
                    result = subprocess.run(
                        [sys.executable, str(practice.ROOT / question.path), '--help'],
                        cwd=directory, capture_output=True, text=True, timeout=5,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn('--timeout', result.stdout)
                    self.assertIn('--full', result.stdout)
