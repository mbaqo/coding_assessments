"""Run with python -m mailer. Offline preview and tests need only Python 3.9+."""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

from .domain import (UTC, Config, MailerError, add_subscriber, address, fallback_questions,
                     iso, new_state, render_batch)
from .engine import Runner
from .providers import SCOPES, Gemini, Gmail, GoogleAPI
from .storage import SheetStore


def oauth_setup(client_file, output):
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise MailerError("Install mailer/requirements-setup.txt to run OAuth setup.") from None
    path = Path(output)
    if path.exists():
        raise MailerError("OAuth output already exists; choose a new path to avoid overwriting credentials.")
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        flow = InstalledAppFlow.from_client_secrets_file(client_file, SCOPES, autogenerate_code_verifier=True)
        credentials = flow.run_local_server(port=0, access_type="offline", prompt="consent")
        if not credentials.refresh_token:
            raise MailerError("No refresh token received; grant offline access and try again.")
        # No bearer access token needs to be persisted or published in Actions secrets.
        data = json.loads(credentials.to_json())
        data.pop("token", None)
        with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as handle:
            json.dump(data, handle)
    except MailerError:
        raise
    except Exception:
        raise MailerError("OAuth setup failed. Check the client file, enabled APIs, and consent-screen configuration.") from None
    print("OAuth credentials saved privately. Do not commit or paste them into logs.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Daily interview mailing list; no learner accounts or completion tracking.")
    parser.add_argument("--config", help="Optional JSON configuration; defaults match mailer/config.example.json")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("preview", help="Render the local review batch without network calls or file writes")
    commands.add_parser("run", help="Process replies and deliver today's batch when due")
    commands.add_parser("check-model", help="Read Gemini model metadata; does not generate or send questions")
    commands.add_parser("init-state", help="Create a new private state Sheet; never resets an existing one")
    oauth = commands.add_parser("oauth-setup", help="Authorize the dedicated Gmail account locally")
    oauth.add_argument("--client", required=True, help="Downloaded Desktop OAuth client JSON")
    oauth.add_argument("--output", default=".mailer-private/google-credentials.json")
    subscribers = commands.add_parser("subscribers", help="Local-only mailing list administration")
    operations = subscribers.add_subparsers(dest="operation", required=True)
    for operation in ("add", "reenroll"):
        sub = operations.add_parser(operation)
        sub.add_argument("--email", required=True, help="Address of an invited, consenting recipient")
    operations.add_parser("list")
    test = commands.add_parser("send-test", help="Send the saved review batch to one enrolled recipient")
    test.add_argument("--email", required=True)
    resolve = commands.add_parser("resolve-delivery", help="Resolve an ambiguous send after checking Gmail Sent mail")
    resolve.add_argument("--key", required=True, help="Delivery key from the private Sheet")
    resolve.add_argument("--resolution", required=True, choices=("sent", "retry", "cancel"))
    args = parser.parse_args(argv)
    try:
        config = Config.read(args.config)
        now = datetime.now(UTC)
        day = now.astimezone(ZoneInfo(config.timezone)).date().isoformat()
        if args.command == "preview":
            print(render_batch({"date": day, "fresh": False, "stage": "Foundations",
                                "questions": fallback_questions()}, config))
            return 0
        if os.environ.get("GITHUB_ACTIONS") == "true" and args.command not in ("run", "check-model"):
            raise MailerError("Administration and OAuth setup must run locally, outside public Actions logs.")
        if args.command == "oauth-setup":
            oauth_setup(args.client, args.output)
            return 0
        model = Gemini.from_environment(config.model)
        if args.command == "check-model":
            model.check()
            print("Configured Gemini model supports generation. Confirm free-tier billing and quotas in AI Studio.")
            return 0
        sender = address(os.environ.get("MAILER_SENDER", ""))
        google = GoogleAPI.from_environment()
        gmail = Gmail(google, sender)
        if args.command == "init-state":
            if os.environ.get("MAILER_SHEET_ID"):
                raise MailerError("MAILER_SHEET_ID is already configured; initialization will not replace existing state.")
            sheet_id = SheetStore.create(google)
            store = SheetStore(google, sheet_id)
            store.save(new_state(now))
            print("Private state initialized. Set MAILER_SHEET_ID to: " + sheet_id)
            return 0
        store = SheetStore(google, os.environ.get("MAILER_SHEET_ID", ""))
        if args.command == "run":
            report = Runner(config, store, gmail, model, now).run()
            print(json.dumps(report, sort_keys=True))  # Counts only; no addresses, tokens, or bodies.
            return 1 if report["uncertain"] or report["send_failures"] else 0
        state = store.load()
        if args.command == "subscribers":
            if args.operation == "list":
                for subscriber in state["subscribers"].values():
                    print(subscriber["email"], subscriber["status"], subscriber["pause_until"] or "")
            else:
                if address(args.email) == sender:
                    raise MailerError("Use a recipient address different from the dedicated sending account.")
                add_subscriber(state, args.email, now, config.max_subscribers, args.operation == "reenroll")
                store.save(state)
                print("Subscriber saved. No email was sent; daily delivery begins at the next eligible run.")
            return 0
        if args.command == "send-test":
            subscriber = next((s for s in state["subscribers"].values() if s["email"] == address(args.email)), None)
            if subscriber is None or subscriber["status"] != "active":
                raise MailerError("Test recipient must be an active enrolled subscriber.")
            runner = Runner(config, store, gmail, model, now)
            runner.state = state
            runner.poll()
            runner.reconcile()
            if subscriber["status"] != "active":
                raise MailerError("Recipient paused or stopped delivery; test was not sent.")
            # Stable per day/recipient: repeated test commands cannot flood the inbox.
            runner.deliver(f"test:{day}:{subscriber['id']}", subscriber, "test", "Interview practice — setup test",
                           render_batch({"date": day, "fresh": False, "stage": "Foundations",
                                         "questions": fallback_questions()}, config), day)
            print(json.dumps(runner.report, sort_keys=True))
            return 1 if runner.report["uncertain"] or runner.report["send_failures"] else 0
        if args.command == "resolve-delivery":
            record = state["deliveries"].get(args.key)
            if not record or record["status"] not in ("pending", "uncertain"):
                raise MailerError("Only pending or uncertain deliveries can be manually resolved.")
            found = gmail.find_sent(record["message_id"])
            if found:
                record.update(status="sent", gmail_id=found)
            else:
                record["status"] = {"sent": "sent", "retry": "failed", "cancel": "cancelled"}[args.resolution]
                record["operator_resolved_at"] = iso(now)
            store.save(state)
            print("Delivery resolution saved. Retry applies at the next eligible run; past daily batches are not backfilled.")
            return 0
    except MailerError as error:
        print("Error: " + str(error), file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError, IndexError, AttributeError):
        # Never dump arbitrary API/state values or credentials in a public traceback.
        print("Error: unexpected configuration/provider data; inspect the private services and retry.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
