"""Orchestrate one serialized run. All external behavior uses replaceable adapters."""
from __future__ import annotations

from datetime import timedelta
from zoneinfo import ZoneInfo

from .domain import (MailerError, ProviderError, apply_command, date_time, expire_pauses, help_text,
                     iso, make_email, message_id, next_batch_number, parse_reply, question_sequence, render_batch)
from .generation import generate_batch, review_batch
from .providers import SendRejected


class Runner:
    def __init__(self, config, store, gmail, model, now):
        self.config, self.store, self.gmail, self.model, self.now = config, store, gmail, model, now
        self.report = {"commands": 0, "daily_sent": 0, "notifications_sent": 0,
                       "test_sent": 0,
                       "reconciled": 0, "uncertain": 0, "send_failures": 0,
                       "fallback": False, "generation_unavailable": False}

    def save(self):
        self.store.save(self.state)

    def poll(self):
        since = max(date_time(self.state["created_at"]), date_time(self.state["last_poll"]) - timedelta(days=2))
        messages = self.gmail.incoming(since)  # Fetch the entire scan before changing state or sending.
        for incoming in messages:
            if incoming["id"] in self.state["commands"]:
                continue
            parsed = parse_reply(incoming["raw"], self.gmail.sender, self.state["subscribers"])
            if parsed is None:
                continue
            subscriber_id, command, days = parsed
            subscriber = self.state["subscribers"][subscriber_id]
            if incoming["received"] < date_time(subscriber["enrolled_at"]):
                continue
            order = [iso(incoming["received"]), incoming["id"]]
            if "last_command" in subscriber and order <= subscriber["last_command"]:
                # A late-indexed old reply cannot undo a newer STOP already processed.
                self.state["commands"][incoming["id"]] = {
                    "subscriber": subscriber_id, "command": command, "received": order[0], "ignored": "stale"}
                continue
            apply_command(subscriber, command, days, incoming["received"])
            subscriber["last_command"] = order
            expire_pauses(self.state, self.now)
            self.state["commands"][incoming["id"]] = {
                "subscriber": subscriber_id, "command": command, "received": iso(incoming["received"])}
            status = subscriber["status"]
            until = " until " + subscriber["pause_until"] if subscriber["pause_until"] else ""
            body = (f"Processed: {command}.\nSubscription status at processing: {status}{until}.\n\n"
                    + help_text(self.config))
            self.state["notifications"][incoming["id"]] = {"subscriber": subscriber_id, "body": body}
            self.report["commands"] += 1
        expire_pauses(self.state, self.now)
        self.state["last_poll"] = iso(self.now)
        self.save()  # Subscription changes and notification intent precede every send.

    def reconcile(self):
        for record in self.state["deliveries"].values():
            if record["status"] not in ("pending", "uncertain"):
                continue
            found = self.gmail.find_sent(record["message_id"])
            if found:
                record.update(status="sent", gmail_id=found)
                self.report["reconciled"] += 1
            else:
                record["status"] = "uncertain"
                self.report["uncertain"] += 1
        self.save()

    def deliver(self, key, subscriber, kind, subject, body, day, batch_date=None):
        existing = self.state["deliveries"].get(key)
        if existing and existing["status"] in ("sent", "pending", "uncertain", "cancelled"):
            return
        if kind == "daily" and subscriber["status"] != "active":
            return
        raw = make_email(self.gmail.sender, subscriber, key, subject, body)
        record = {"subscriber": subscriber["id"], "date": day, "kind": kind,
                  "message_id": message_id(key, self.gmail.sender), "status": "pending"}
        if kind == "daily":
            record["batch_date"] = batch_date or day
        self.state["deliveries"][key] = record
        self.save()  # A crash after this point must reconcile, never blindly resend.
        try:
            gmail_id = self.gmail.send(raw)
        except SendRejected:
            record["status"] = "failed"
            self.report["send_failures"] += 1
        except ProviderError:
            record["status"] = "uncertain"
            self.report["uncertain"] += 1
        else:
            record.update(status="sent", gmail_id=gmail_id)
            metric = {"daily": "daily_sent", "notification": "notifications_sent", "test": "test_sent"}[kind]
            self.report[metric] += 1
        self.save()

    def run(self):
        self.state = self.store.load()
        self.poll()
        self.reconcile()
        local = self.now.astimezone(ZoneInfo(self.config.timezone))
        day = local.date().isoformat()
        for incoming_id, notification in self.state["notifications"].items():
            subscriber = self.state["subscribers"][notification["subscriber"]]
            self.deliver("notification:" + incoming_id, subscriber, "notification",
                         "Interview practice — email preferences", notification["body"], day)
        if local.strftime("%H:%M") < self.config.send_time:
            return self.report
        active = [s for s in self.state["subscribers"].values() if s["status"] == "active"]
        if len(active) > self.config.max_subscribers:
            raise MailerError("Active list exceeds the configured subscriber limit.")
        for subscriber in active:
            key = f"daily:{day}:{subscriber['id']}"
            existing = self.state["deliveries"].get(key)
            if existing and existing["status"] in ("sent", "pending", "uncertain", "cancelled"):
                continue
            # Resolve an ambiguous send before moving this person through the sequence.
            if any(d["subscriber"] == subscriber["id"] and d["kind"] == "daily"
                   and d["status"] in ("pending", "uncertain") for d in self.state["deliveries"].values()):
                continue
            number = next_batch_number(self.state, subscriber)
            sequence = question_sequence(self.state)
            if number <= len(sequence):
                batch = sequence[number - 1]
            else:
                batch = self.prepare_batch(day)
            self.report["fallback"] |= not batch["fresh"]
            subject = f"Interview practice — {day} — batch {number}" + (" (review)" if not batch["fresh"] else "")
            body = render_batch(dict(batch, date=day, number=number), self.config)
            self.deliver(key, subscriber, "daily", subject, body, day, batch["date"])
        return self.report

    def prepare_batch(self, day):
        """Extend the shared library only when someone reaches its end."""
        if day not in self.state["batches"]:
            # Persist fallback first: a killed process cannot spend more model calls on a rerun.
            self.state["batches"][day] = review_batch(self.state, day)
            self.state["batches"][day]["generation"] = "reserved"
            self.save()
            try:
                batch = generate_batch(self.state, self.config, self.model, day)
            except MailerError:
                self.state["batches"][day]["generation"] = "unavailable"
                self.report["generation_unavailable"] = True
            else:
                self.state["batches"][day] = batch
            self.save()
        return self.state["batches"][day]
