from copy import deepcopy
from datetime import timedelta
from email import policy
from email.parser import BytesParser
import unittest
import json
from zoneinfo import ZoneInfo
from unittest.mock import patch

from mailer.domain import (Config, MailerError, ProviderError, add_subscriber, fallback_questions,
                           new_state, next_batch_number)
from mailer.engine import Runner
from mailer.providers import SendRejected
from mailer.storage import validate_state
from test_domain import NOW, SENDER, reply


class MemoryStore:
    def __init__(self, state):
        self.data = deepcopy(state)
        self.fail_save = False

    def load(self):
        return deepcopy(validate_state(self.data))

    def save(self, state):
        if self.fail_save:
            raise ProviderError("Storage unavailable.")
        self.data = deepcopy(validate_state(state))


class FakeGmail:
    sender = SENDER

    def __init__(self):
        self.messages = []
        self.sent = []
        self.fail_inbox = False
        self.send_error = None
        self.accept_before_error = False
        self.on_send = None

    def incoming(self, since):
        if self.fail_inbox:
            raise ProviderError("Inbox unavailable.")
        return sorted((m for m in self.messages if m["received"] >= since), key=lambda m: (m["received"], m["id"]))

    def find_sent(self, message_id):
        return next((str(i + 1) for i, msg in enumerate(self.sent) if msg["Message-ID"] == message_id), None)

    def send(self, raw):
        if self.send_error and not self.accept_before_error:
            raise self.send_error
        self.sent.append(BytesParser(policy=policy.default).parsebytes(raw))
        if self.on_send:
            self.on_send()
        if self.send_error:
            raise self.send_error
        return str(len(self.sent))


class FakeModel:
    def __init__(self):
        self.calls = 0
        self.fail = False
        self.approved = True

    def generate_json(self, prompt, schema, max_tokens=8192):
        self.calls += 1
        if self.fail:
            raise ProviderError("Model quota exhausted.")
        if schema["type"] == "object":
            return {"approved": self.approved}
        qs = fallback_questions()
        selection = json.loads(prompt.split("Shared syllabus: ")[1].split("\nRecent questions")[0])
        for i, q in enumerate(qs):
            q["title"] = f"Fresh exercise {self.calls} number {i}"
            q["prompt"] = f"Unique task {self.calls}, item {i}. " + q["prompt"]
            q["difficulty"] = "medium" if i < selection["medium"] else "easy"
        return qs


class EngineTests(unittest.TestCase):
    def setUp(self):
        state = new_state(NOW - timedelta(days=1))
        self.subscriber = add_subscriber(state, "learner@example.com", NOW - timedelta(days=1))
        self.store, self.gmail, self.model = MemoryStore(state), FakeGmail(), FakeModel()

    def run_mailer(self, now=NOW, config=None):
        return Runner(config or Config(), self.store, self.gmail, self.model, now).run()

    def incoming(self, text, gmail_id="reply-1", received=NOW, subscriber=None):
        self.gmail.messages.append({"id": gmail_id, "received": received,
                                    "raw": reply(subscriber or self.subscriber, text)})

    def test_daily_without_answers_and_retry_without_duplicates(self):
        first = self.run_mailer()
        self.assertEqual(first["daily_sent"], 1)
        self.assertEqual(self.model.calls, 2)
        self.assertEqual(self.run_mailer(NOW + timedelta(minutes=30))["daily_sent"], 0)
        self.assertEqual(self.model.calls, 2)
        self.assertEqual(self.run_mailer(NOW + timedelta(days=1))["daily_sent"], 1)
        self.assertEqual(self.model.calls, 4)
        self.assertEqual(len(self.gmail.sent), 2)

    def test_scheduled_runs_generate_for_weeks_without_manual_question_batches(self):
        second = add_subscriber(self.store.data, "second@example.com", NOW)
        for offset in range(35):
            # The timer follows local 08:15, including the autumn DST change.
            now = (NOW.astimezone(ZoneInfo(Config().timezone)) + timedelta(days=offset)).astimezone(NOW.tzinfo)
            if offset == 3:
                self.incoming("PAUSE", "pause", now)
            if offset == 6:
                self.incoming("RESUME", "resume", now)
            report = self.run_mailer(now)
            self.assertEqual(report["daily_sent"], 1 if 3 <= offset < 6 else 2)
            self.assertFalse(report["fallback"])
            # One new shared batch per day, even with people at different positions.
            self.assertEqual(self.model.calls, 2 * (offset + 1))
            self.assertEqual(self.run_mailer(now + timedelta(minutes=30))["daily_sent"], 0)
            self.assertEqual(self.model.calls, 2 * (offset + 1))

        self.assertEqual(next_batch_number(self.store.data, self.subscriber), 33)
        self.assertEqual(next_batch_number(self.store.data, second), 36)
        batches = sorted(self.store.data["batches"].items())
        self.assertEqual(len(batches), 35)
        for index, (_, batch) in enumerate(batches):
            self.assertEqual(len(batch["questions"]), 5)
            self.assertEqual(batch["stage"], ("Foundations" if index < 14 else
                                              "Core patterns" if index < 28 else "Trees and search"))

    def test_generation_recovers_automatically_after_multiple_days_unavailable(self):
        self.model.fail = True
        for offset in range(3):
            report = self.run_mailer(NOW + timedelta(days=offset))
            self.assertEqual(report["daily_sent"], 1)
            self.assertTrue(report["fallback"])
            self.assertTrue(report["generation_unavailable"])
            self.assertEqual(len(list(self.store.data["batches"].values())[-1]["questions"]), 5)
            self.assertEqual(next_batch_number(self.store.data, self.subscriber), 1)
        self.assertEqual(self.model.calls, 3)
        self.model.fail = False
        report = self.run_mailer(NOW + timedelta(days=3))
        self.assertEqual(report["daily_sent"], 1)
        self.assertFalse(report["fallback"])
        self.assertEqual(self.model.calls, 5)
        self.assertEqual(next_batch_number(self.store.data, self.subscriber), 2)

    def test_one_shared_batch_with_private_individual_envelopes(self):
        add_subscriber(self.store.data, "second@example.com", NOW)
        self.assertEqual(self.run_mailer()["daily_sent"], 2)
        self.assertEqual(self.model.calls, 2)
        self.assertEqual({m["To"] for m in self.gmail.sent}, {"learner@example.com", "second@example.com"})
        bodies = [m.get_body(preferencelist=("plain",)).get_content() for m in self.gmail.sent]
        self.assertEqual(bodies[0], bodies[1])

    def test_stop_processed_before_generation_and_confirmed_once(self):
        self.incoming("STOP")
        report = self.run_mailer()
        self.assertEqual(report["commands"], 1)
        self.assertEqual(report["daily_sent"], 0)
        self.assertEqual(report["notifications_sent"], 1)
        self.assertEqual(self.model.calls, 0)
        self.run_mailer(NOW + timedelta(minutes=30))
        self.assertEqual(len(self.gmail.sent), 1)
        self.assertEqual(self.store.data["subscribers"][self.subscriber["id"]]["status"], "stopped")

    def test_paused_list_still_processes_resume(self):
        self.incoming("PAUSE")
        self.run_mailer()
        self.incoming("RESUME", "reply-2", NOW + timedelta(days=1))
        self.assertEqual(self.run_mailer(NOW + timedelta(days=1))["daily_sent"], 1)

    def test_chronological_commands_and_timed_expiry(self):
        self.incoming("RESUME", "later", NOW - timedelta(hours=1))
        self.incoming("PAUSE", "earlier", NOW - timedelta(hours=2))
        self.assertEqual(self.run_mailer()["daily_sent"], 1)
        self.incoming("PAUSE 1", "pause-one", NOW + timedelta(days=1))
        self.assertEqual(self.run_mailer(NOW + timedelta(days=1))["daily_sent"], 0)
        self.assertEqual(self.run_mailer(NOW + timedelta(days=2))["daily_sent"], 1)

    def test_unknown_and_unrelated_replies_cannot_change_status(self):
        self.incoming("I solved one problem.\nSTOP")
        stranger = dict(self.subscriber, email="stranger@example.com")
        self.incoming("STOP", "unknown", subscriber=stranger)
        report = self.run_mailer()
        self.assertEqual(report["commands"], 0)
        self.assertEqual(report["daily_sent"], 1)

    def test_free_quota_failure_falls_back_and_does_not_retry_generation(self):
        self.model.fail = True
        result = self.run_mailer()
        self.assertTrue(result["fallback"])
        self.assertEqual(result["daily_sent"], 1)
        self.assertEqual(self.model.calls, 1)
        self.assertIn("review", self.gmail.sent[0]["Subject"])
        self.run_mailer(NOW + timedelta(minutes=30))
        self.assertEqual(self.model.calls, 1)

    def test_review_rejection_uses_saved_questions(self):
        self.model.approved = False
        self.assertTrue(self.run_mailer()["fallback"])
        self.assertEqual(self.model.calls, 2)

    def test_invalid_generation_is_not_sent(self):
        with patch.object(self.model, "generate_json", return_value=[]):
            self.assertTrue(self.run_mailer()["fallback"])
        self.assertIn("Contains Duplicate", self.gmail.sent[0].get_body(preferencelist=("plain",)).get_content())

    def test_inbox_or_storage_failure_prevents_all_sends(self):
        self.gmail.fail_inbox = True
        with self.assertRaises(ProviderError):
            self.run_mailer()
        self.assertEqual(self.gmail.sent, [])
        self.gmail.fail_inbox = False
        self.store.fail_save = True
        with self.assertRaises(ProviderError):
            self.run_mailer()
        self.assertEqual(self.gmail.sent, [])
        self.assertEqual(self.model.calls, 0)

    def test_ambiguous_send_found_in_sent_is_not_duplicated(self):
        self.gmail.send_error = ProviderError("Timed out.")
        self.gmail.accept_before_error = True
        self.assertEqual(self.run_mailer()["uncertain"], 1)
        self.gmail.send_error = None
        retry = self.run_mailer(NOW + timedelta(minutes=30))
        self.assertEqual(retry["reconciled"], 1)
        self.assertEqual(len(self.gmail.sent), 1)

    def test_unresolved_send_is_reported_and_never_blindly_retried(self):
        self.gmail.send_error = ProviderError("Timed out.")
        self.run_mailer()
        self.gmail.send_error = None
        retry = self.run_mailer(NOW + timedelta(minutes=30))
        self.assertEqual(retry["uncertain"], 1)
        self.assertEqual(self.gmail.sent, [])

    def test_definite_rejection_retries_without_regenerating(self):
        self.gmail.send_error = SendRejected("Rejected.")
        self.assertEqual(self.run_mailer()["send_failures"], 1)
        self.gmail.send_error = None
        self.assertEqual(self.run_mailer(NOW + timedelta(minutes=30))["daily_sent"], 1)
        self.assertEqual(self.model.calls, 2)

    def test_crash_after_send_retains_intent_for_reconciliation(self):
        self.gmail.on_send = lambda: setattr(self.store, "fail_save", True)
        with self.assertRaises(ProviderError):
            self.run_mailer()
        record = next(iter(self.store.data["deliveries"].values()))
        self.assertEqual(record["status"], "pending")
        self.gmail.on_send = None
        self.store.fail_save = False
        self.assertEqual(self.run_mailer(NOW + timedelta(minutes=30))["reconciled"], 1)
        self.assertEqual(len(self.gmail.sent), 1)

    def test_paused_recipient_does_not_block_other_recipient(self):
        add_subscriber(self.store.data, "second@example.com", NOW)
        self.incoming("PAUSE")
        self.assertEqual(self.run_mailer()["daily_sent"], 1)
        daily = [m for m in self.gmail.sent if "email preferences" not in m["Subject"]]
        self.assertEqual(daily[0]["To"], "second@example.com")

    def test_no_subscribers_or_before_due_time_does_not_generate(self):
        self.assertEqual(self.run_mailer(NOW - timedelta(minutes=1))["daily_sent"], 0)
        self.assertEqual(self.model.calls, 0)
        self.store.data["subscribers"] = {}
        self.run_mailer()
        self.assertEqual(self.model.calls, 0)

    def test_generation_crash_keeps_fallback_without_new_api_calls(self):
        with patch("mailer.engine.generate_batch", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                self.run_mailer()
        report = self.run_mailer(NOW + timedelta(minutes=30))
        self.assertTrue(report["fallback"])
        self.assertEqual(report["daily_sent"], 1)
        self.assertEqual(self.model.calls, 0)

    def test_late_indexed_old_resume_cannot_undo_newer_stop(self):
        self.incoming("STOP", "newer-stop", NOW)
        self.run_mailer()
        self.incoming("RESUME", "late-old-resume", NOW - timedelta(hours=1))
        report = self.run_mailer(NOW + timedelta(minutes=30))
        self.assertEqual(report["daily_sent"], 0)
        self.assertEqual(self.store.data["subscribers"][self.subscriber["id"]]["status"], "stopped")

    def test_later_quota_failure_reuses_saved_batch(self):
        self.run_mailer()
        self.model.fail = True
        report = self.run_mailer(NOW + timedelta(days=1), Config(days_per_stage=1))
        self.assertTrue(report["fallback"])
        self.assertEqual(report["daily_sent"], 1)
        batches = list(self.store.data["batches"].values())
        self.assertEqual(batches[0]["questions"], batches[1]["questions"])

    def test_winter_timezone_uses_local_send_time(self):
        winter = NOW.replace(month=12, hour=16, minute=14)
        self.assertEqual(self.run_mailer(winter)["daily_sent"], 0)
        self.assertEqual(self.run_mailer(winter + timedelta(minutes=1))["daily_sent"], 1)

    def daily_record(self, offset, subscriber=None):
        day = (NOW + timedelta(days=offset)).date().isoformat()
        return self.store.data["deliveries"][f"daily:{day}:{(subscriber or self.subscriber)['id']}"]

    def test_pause_preserves_individual_sequence_and_stage(self):
        second = add_subscriber(self.store.data, "second@example.com", NOW)
        config = Config(days_per_stage=1)
        self.run_mailer(config=config)
        self.incoming("PAUSE", "pause", NOW + timedelta(days=1))
        self.run_mailer(NOW + timedelta(days=1), config)
        self.run_mailer(NOW + timedelta(days=2), config)
        self.incoming("RESUME", "resume", NOW + timedelta(days=3))
        self.assertEqual(self.run_mailer(NOW + timedelta(days=3), config)["daily_sent"], 2)
        resumed = self.daily_record(3)
        other = self.daily_record(3, second)
        self.assertEqual(resumed["batch_date"], self.daily_record(1, second)["batch_date"])
        self.assertNotEqual(resumed["batch_date"], other["batch_date"])
        self.assertEqual(self.store.data["batches"][resumed["batch_date"]]["stage"], "Core patterns")
        self.assertEqual(self.store.data["batches"][other["batch_date"]]["stage"], "Advanced patterns")
        self.assertEqual(next_batch_number(self.store.data, self.subscriber), 3)
        self.assertEqual(next_batch_number(self.store.data, second), 5)

    def test_new_subscriber_starts_at_first_batch_without_generation(self):
        self.run_mailer()
        self.run_mailer(NOW + timedelta(days=1))
        self.incoming("PAUSE", "pause", NOW + timedelta(days=2))
        second = add_subscriber(self.store.data, "second@example.com", NOW + timedelta(days=2))
        calls = self.model.calls
        self.assertEqual(self.run_mailer(NOW + timedelta(days=2))["daily_sent"], 1)
        self.assertEqual(self.model.calls, calls)
        self.assertEqual(self.daily_record(2, second)["batch_date"], self.daily_record(0)["batch_date"])
        self.assertEqual(self.run_mailer(NOW + timedelta(days=2, minutes=30))["daily_sent"], 0)

    def test_timed_pause_and_stop_reenrollment_keep_position(self):
        self.run_mailer()
        self.incoming("PAUSE 2", "pause", NOW + timedelta(days=1))
        self.assertEqual(self.run_mailer(NOW + timedelta(days=1))["daily_sent"], 0)
        self.assertEqual(self.run_mailer(NOW + timedelta(days=2))["daily_sent"], 0)
        self.assertEqual(self.run_mailer(NOW + timedelta(days=3))["daily_sent"], 1)
        self.assertEqual(next_batch_number(self.store.data, self.subscriber), 3)
        self.incoming("STOP", "stop", NOW + timedelta(days=4))
        self.assertEqual(self.run_mailer(NOW + timedelta(days=4))["daily_sent"], 0)
        self.incoming("RESUME", "resume", NOW + timedelta(days=5))
        self.assertEqual(self.run_mailer(NOW + timedelta(days=5))["daily_sent"], 0)
        add_subscriber(self.store.data, self.subscriber["email"], NOW + timedelta(days=6), reenroll=True)
        self.run_mailer(NOW + timedelta(days=6))
        self.assertEqual(next_batch_number(self.store.data, self.subscriber), 4)

    def test_failed_delivery_keeps_questions_for_next_day(self):
        self.gmail.send_error = SendRejected("Rejected.")
        self.run_mailer()
        self.assertEqual(next_batch_number(self.store.data, self.subscriber), 1)
        self.gmail.send_error = None
        self.run_mailer(NOW + timedelta(days=1))
        self.assertEqual(self.daily_record(1)["batch_date"], self.daily_record(0)["batch_date"])
        self.assertEqual(next_batch_number(self.store.data, self.subscriber), 2)
        self.assertEqual(self.model.calls, 2)

    def test_uncertain_delivery_blocks_only_that_subscribers_sequence(self):
        self.gmail.send_error = ProviderError("Timed out.")
        self.run_mailer()
        self.gmail.send_error = None
        second = add_subscriber(self.store.data, "second@example.com", NOW + timedelta(days=1))
        self.assertEqual(self.run_mailer(NOW + timedelta(days=1))["daily_sent"], 1)
        self.assertEqual(next_batch_number(self.store.data, self.subscriber), 1)
        self.assertEqual(next_batch_number(self.store.data, second), 2)
        # The organizer confirms the original send, as resolve-delivery does.
        self.daily_record(0)["status"] = "sent"
        self.run_mailer(NOW + timedelta(days=2))
        self.assertEqual(next_batch_number(self.store.data, self.subscriber), 3)

    def test_reconciliation_advances_position_once(self):
        self.gmail.send_error = ProviderError("Timed out.")
        self.gmail.accept_before_error = True
        self.run_mailer()
        self.assertEqual(next_batch_number(self.store.data, self.subscriber), 1)
        self.gmail.send_error = None
        self.run_mailer(NOW + timedelta(minutes=30))
        self.assertEqual(next_batch_number(self.store.data, self.subscriber), 2)
        self.run_mailer(NOW + timedelta(minutes=45))
        self.assertEqual(next_batch_number(self.store.data, self.subscriber), 2)

    def test_review_and_test_emails_do_not_advance_position(self):
        self.run_mailer()
        self.model.fail = True
        self.run_mailer(NOW + timedelta(days=1))
        self.assertEqual(next_batch_number(self.store.data, self.subscriber), 2)
        self.model.fail = False
        self.run_mailer(NOW + timedelta(days=2))
        self.assertEqual(next_batch_number(self.store.data, self.subscriber), 3)
        self.daily_record(2)["kind"] = "test"
        self.assertEqual(next_batch_number(self.store.data, self.subscriber), 2)

    def test_legacy_delivery_records_continue_after_last_received_batch(self):
        self.run_mailer()
        self.run_mailer(NOW + timedelta(days=1))
        for record in self.store.data["deliveries"].values():
            record.pop("batch_date", None)
        # Legacy subscribers could have skipped earlier batches while paused.
        del self.store.data["deliveries"][f"daily:{NOW.date().isoformat()}:{self.subscriber['id']}"]
        self.assertEqual(next_batch_number(self.store.load(), self.subscriber), 3)
        self.run_mailer(NOW + timedelta(days=2))
        self.assertEqual(next_batch_number(self.store.data, self.subscriber), 4)


if __name__ == "__main__":
    unittest.main()
