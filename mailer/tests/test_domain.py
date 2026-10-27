from copy import deepcopy
from datetime import datetime, timedelta
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
import json
import unittest

from mailer.domain import (UTC, Config, MailerError, add_subscriber, apply_command, expire_pauses,
                           fallback_questions, iso, make_email, new_state, parse_reply, reply_address,
                           syllabus, validate_questions)
from mailer.storage import decode_rows, encode_rows

NOW = datetime(2026, 10, 22, 15, 15, tzinfo=UTC)
SENDER = "practice.sender@gmail.com"


def reply(subscriber, body, html=False, sender=None, recipient=None, headers=None):
    msg = EmailMessage()
    msg["From"] = sender or subscriber["email"]
    msg["To"] = recipient or reply_address(SENDER, subscriber)
    for key, value in (headers or {}).items():
        msg[key] = value
    msg.set_content(body, subtype="html" if html else "plain")
    return msg.as_bytes()


class DomainTests(unittest.TestCase):
    def setUp(self):
        self.state = new_state(NOW)
        self.subscriber = add_subscriber(self.state, "learner@example.com", NOW)

    def test_case_insensitive_commands_and_valid_duration(self):
        for text, command, days in [("\n pause 7\nThanks!", "PAUSE", 7), ("resume", "RESUME", None),
                                     ("UNSUBSCRIBE", "UNSUBSCRIBE", None), ("PAUSE 365", "PAUSE", 365),
                                     ("PAUSE 0", "HELP", None)]:
            with self.subTest(text=text):
                self.assertEqual(parse_reply(reply(self.subscriber, text), SENDER, self.state["subscribers"]),
                                 (self.subscriber["id"], command, days))

    def test_quoted_footer_answers_signatures_and_auto_mail_do_not_command(self):
        examples = ["Here is my solution\nSTOP", "> STOP", "On Thursday, Sender wrote:\nSTOP",
                    "-- \nSTOP", "Sent from my iPhone\nPAUSE", "Please do not STOP", "PAUSE -1", "PAUSE 9999"]
        for text in examples:
            with self.subTest(text=text):
                self.assertIsNone(parse_reply(reply(self.subscriber, text), SENDER, self.state["subscribers"]))
        for headers in [{"Auto-Submitted": "auto-replied"}, {"Precedence": "bulk"}, {"List-Id": "test.example"}]:
            self.assertIsNone(parse_reply(reply(self.subscriber, "STOP", headers=headers), SENDER, self.state["subscribers"]))

    def test_sender_and_token_must_both_match(self):
        for changes in [{"sender": "other@example.com"}, {"recipient": SENDER}]:
            self.assertIsNone(parse_reply(reply(self.subscriber, "STOP", **changes), SENDER, self.state["subscribers"]))
        old = reply(self.subscriber, "STOP")
        apply_command(self.subscriber, "STOP", None, NOW)
        add_subscriber(self.state, self.subscriber["email"], NOW, reenroll=True)
        self.assertIsNone(parse_reply(old, SENDER, self.state["subscribers"]))

    def test_html_reply_excludes_quotes_and_hidden_code(self):
        self.assertIsNone(parse_reply(reply(self.subscriber, "<blockquote>STOP</blockquote>", html=True),
                                     SENDER, self.state["subscribers"]))
        parsed = parse_reply(reply(self.subscriber, "<div>PAUSE 7</div><blockquote>STOP</blockquote>", html=True),
                             SENDER, self.state["subscribers"])
        self.assertEqual(parsed[1:], ("PAUSE", 7))

    def test_pause_duration_starts_at_receipt_and_stop_never_auto_resumes(self):
        apply_command(self.subscriber, "PAUSE", 7, NOW)
        expire_pauses(self.state, NOW + timedelta(days=6))
        self.assertEqual(self.subscriber["status"], "paused")
        expire_pauses(self.state, NOW + timedelta(days=7))
        self.assertEqual(self.subscriber["status"], "active")
        apply_command(self.subscriber, "STOP", None, NOW)
        apply_command(self.subscriber, "RESUME", None, NOW)
        apply_command(self.subscriber, "PAUSE", 1, NOW)
        expire_pauses(self.state, NOW + timedelta(days=100))
        self.assertEqual(self.subscriber["status"], "stopped")

    def test_indefinite_pause_and_explicit_resume(self):
        apply_command(self.subscriber, "PAUSE", None, NOW)
        expire_pauses(self.state, NOW + timedelta(days=1000))
        self.assertEqual(self.subscriber["status"], "paused")
        apply_command(self.subscriber, "RESUME", None, NOW)
        self.assertEqual(self.subscriber["status"], "active")

    def test_storage_round_trip_corruption_and_duplicate_keys(self):
        rows = encode_rows(self.state)
        self.assertEqual(decode_rows(rows), self.state)
        for bad in [[], rows + [rows[0]], [["meta", "not-json"]]]:
            with self.assertRaises(MailerError):
                decode_rows(bad)
        corrupt = deepcopy(self.state)
        corrupt["subscribers"][self.subscriber["id"]]["status"] = "typo"
        with self.assertRaises(MailerError):
            encode_rows(corrupt)

    def test_validation_rejects_spoilers_duplicates_hard_and_missing_fields(self):
        questions = fallback_questions()
        validate_questions(questions)
        mutations = [lambda qs: qs.pop(), lambda qs: qs[0].pop("constraints"),
                     lambda qs: qs[0].update(difficulty="hard"),
                     lambda qs: qs[0].update(prompt="Solution: do this"),
                     lambda qs: qs[0].update(target_minutes=[True, 20]),
                     lambda qs: qs[1].update(title=qs[0]["title"])]
        for mutation in mutations:
            bad = deepcopy(questions)
            mutation(bad)
            with self.assertRaises(MailerError):
                validate_questions(bad)
        with self.assertRaises(MailerError):
            validate_questions(questions, recent=questions)

    def test_render_is_individual_escaped_and_message_id_stable(self):
        raw = make_email(SENDER, self.subscriber, "daily:example", "Practice", "<script>alert(1)</script>")
        message = BytesParser(policy=policy.default).parsebytes(raw)
        self.assertEqual(message["To"], self.subscriber["email"])
        self.assertIsNone(message["Cc"])
        self.assertIsNone(message["Bcc"])
        self.assertIn("&lt;script&gt;", message.get_body(preferencelist=("html",)).get_content())
        self.assertEqual(message["Reply-To"], reply_address(SENDER, self.subscriber))

    def test_curriculum_sequence_advances_only_for_saved_fresh_batches(self):
        self.state["batches"]["2026-10-20"] = {"fresh": True}
        self.assertEqual(syllabus(self.state, Config(days_per_stage=1))["stage"], "Core patterns")
        self.state["batches"]["2026-10-20"]["fresh"] = False
        self.assertEqual(syllabus(self.state, Config(days_per_stage=1))["stage"], "Foundations")

    def test_subscriber_limit_and_explicit_reenrollment(self):
        with self.assertRaises(MailerError):
            add_subscriber(self.state, "another@example.com", NOW, maximum=1)
        with self.assertRaises(MailerError):
            add_subscriber(self.state, self.subscriber["email"], NOW)
        apply_command(self.subscriber, "STOP", None, NOW)
        add_subscriber(self.state, self.subscriber["email"], NOW, reenroll=True)
        self.assertEqual(self.subscriber["status"], "active")


if __name__ == "__main__":
    unittest.main()
