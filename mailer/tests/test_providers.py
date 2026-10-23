import base64
from contextlib import redirect_stdout, redirect_stderr
from copy import deepcopy
from email import policy
from email.parser import BytesParser
import io
import json
import os
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError

from mailer.__main__ import main
from mailer.domain import MailerError, new_state
from mailer.providers import Gemini, Gmail, GoogleAPI, HTTPFailure, SendRejected, request_json
from mailer.storage import SheetStore, encode_rows
from test_domain import NOW, SENDER


class ProviderTests(unittest.TestCase):
    def test_http_error_never_exposes_provider_body_or_credentials(self):
        failure = HTTPError("https://example.test?key=secret", 400, "private-address@example.com", {},
                            io.BytesIO(b"sensitive response"))
        with patch("mailer.providers.urlopen", side_effect=failure):
            with self.assertRaises(HTTPFailure) as caught:
                request_json("Example", "GET", "https://example.test?key=secret")
        self.assertEqual(str(caught.exception), "Example request failed (HTTP 400).")

    def test_safe_http_retries_are_bounded_and_send_does_not_retry(self):
        with patch("mailer.providers.urlopen", side_effect=URLError("private details")) as call, \
                patch("mailer.providers.time.sleep"):
            with self.assertRaises(HTTPFailure):
                request_json("Example", "GET", "https://example.test")
            self.assertEqual(call.call_count, 3)
            call.reset_mock()
            with self.assertRaises(HTTPFailure):
                request_json("Example", "POST", "https://example.test", payload={}, retry=False)
            self.assertEqual(call.call_count, 1)

    def test_quota_backoff_allows_a_minute_to_recover(self):
        failures = [HTTPError("https://example.test", 429, "Quota", {}, io.BytesIO()) for _ in range(3)]
        with patch("mailer.providers.urlopen", side_effect=failures), patch("mailer.providers.time.sleep") as sleep:
            with self.assertRaises(HTTPFailure):
                request_json("Sheets", "PUT", "https://example.test", payload={})
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [30, 30])

    def test_google_refresh_uses_fixed_endpoint_and_does_not_use_untrusted_token_uri(self):
        credentials = {"client_id": "client", "client_secret": "secret", "refresh_token": "refresh",
                       "token_uri": "https://untrusted.test"}
        with patch("mailer.providers.request_json", return_value={"access_token": "bearer"}) as call:
            google = GoogleAPI(credentials)
            self.assertEqual(call.call_args.args[2], "https://oauth2.googleapis.com/token")
            with self.assertRaises(MailerError):
                google.call("test", "GET", "https://untrusted.test")

    def test_gmail_profile_mismatch_fails_before_mail_access(self):
        google = Mock()
        google.call.return_value = {"emailAddress": "wrong@gmail.com"}
        with self.assertRaises(MailerError):
            Gmail(google, SENDER)

    def test_gmail_pagination_reads_raw_messages_and_server_receipt_time(self):
        raw = b"From: learner@example.com\r\n\r\nSTOP"
        google = Mock()
        google.call.side_effect = [
            {"emailAddress": SENDER},
            {"messages": [{"id": "1"}], "nextPageToken": "page2"},
            {"messages": [{"id": "2"}]},
            {"raw": base64.urlsafe_b64encode(raw).decode(), "internalDate": str(int(NOW.timestamp() * 1000))},
            {"raw": base64.urlsafe_b64encode(raw).decode(), "internalDate": str(int(NOW.timestamp() * 1000) - 1000)},
        ]
        gmail = Gmail(google, SENDER)
        messages = gmail.incoming(NOW)
        self.assertEqual([m["id"] for m in messages], ["2", "1"])
        self.assertEqual(messages[1]["raw"], raw)
        self.assertIn("pageToken=page2", google.call.call_args_list[2].args[2])

    def test_gmail_rejection_and_server_failure_are_distinct(self):
        google = Mock()
        google.call.return_value = {"emailAddress": SENDER}
        gmail = Gmail(google, SENDER)
        google.call.side_effect = HTTPFailure("Gmail", 429)
        with self.assertRaises(SendRejected):
            gmail.send(b"example")
        self.assertFalse(google.call.call_args.kwargs["retry"])
        google.call.side_effect = HTTPFailure("Gmail", 503)
        with self.assertRaises(HTTPFailure):
            gmail.send(b"example")

    def test_gemini_needs_explicit_free_tier_acknowledgment(self):
        with patch("mailer.providers.request_json") as network:
            for model in (Gemini("gemini-3.1-flash-lite"), Gemini("gemini-3.1-flash-lite", "key")):
                with self.assertRaises(MailerError):
                    model.generate_json("prompt", {})
            network.assert_not_called()

    def test_gemini_uses_json_schema_and_rejects_truncation(self):
        response = {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": '{"approved": true}'}]}}]}
        model = Gemini("gemini-3.1-flash-lite", "key", True)
        with patch("mailer.providers.request_json", return_value=response) as request:
            self.assertEqual(model.generate_json("prompt", {"type": "object"}), {"approved": True})
            args = request.call_args.args
            self.assertEqual(args[3]["x-goog-api-key"], "key")
            self.assertEqual(args[4]["generationConfig"]["responseJsonSchema"], {"type": "object"})
            self.assertFalse(request.call_args.kwargs["retry"])
            response["candidates"][0]["finishReason"] = "MAX_TOKENS"
            with self.assertRaises(MailerError):
                model.generate_json("prompt", {})

    def test_sheet_snapshot_is_raw_and_pads_old_rows(self):
        google = Mock()
        google.call.return_value = {"sheets": [{"properties": {
            "title": "MailerState", "sheetId": 0, "gridProperties": {"rowCount": 1000}}}]}
        store = SheetStore(google, "example-id")
        store.previous_rows = 4
        state = new_state(NOW)
        store.save(state)
        args = google.call.call_args.args
        self.assertEqual(args[1], "PUT")
        self.assertIn("valueInputOption=RAW", args[2])
        self.assertEqual(args[3]["values"][0], encode_rows(state)[0])
        self.assertEqual(args[3]["values"][1:], [["", ""], ["", ""], ["", ""]])

    def test_sheet_expands_grid_before_writing(self):
        google = Mock()
        google.call.return_value = {"sheets": [{"properties": {
            "title": "MailerState", "sheetId": 5, "gridProperties": {"rowCount": 0}}}]}
        SheetStore(google, "example-id").save(new_state(NOW))
        self.assertEqual(google.call.call_args_list[1].args[1], "POST")
        resize = google.call.call_args_list[1].args[3]["requests"][0]
        self.assertEqual(resize["updateSheetProperties"]["properties"]["sheetId"], 5)

    def test_offline_preview_has_no_api_calls_and_admin_refuses_actions(self):
        with patch("mailer.providers.request_json") as network, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(["preview"]), 0)
            network.assert_not_called()
            self.assertIn("Contains Duplicate", output.getvalue())
        with patch.dict(os.environ, {"GITHUB_ACTIONS": "true"}), redirect_stderr(io.StringIO()) as error:
            self.assertEqual(main(["subscribers", "list"]), 2)
            self.assertIn("locally", error.getvalue())

    def test_cli_failure_does_not_dump_private_provider_data(self):
        with patch.dict(os.environ, {"MAILER_SENDER": SENDER}), \
                patch("mailer.__main__.GoogleAPI.from_environment", side_effect=KeyError("private data")), \
                redirect_stderr(io.StringIO()) as error:
            self.assertEqual(main(["run"]), 2)
            self.assertNotIn("private data", error.getvalue())


if __name__ == "__main__":
    unittest.main()
