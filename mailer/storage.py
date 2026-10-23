"""Private Google Sheets snapshot storage, serialized by the Actions workflow."""
from __future__ import annotations

import json
import re
from urllib.parse import quote

from .domain import MailerError, address, date_time, validate_questions

COLLECTIONS = ("subscribers", "batches", "deliveries", "commands", "notifications")
TAB = "MailerState"


def validate_state(state):
    """Fail closed on malformed persistence; never reset history automatically."""
    try:
        if set(state) != {"version", "created_at", "last_poll", *COLLECTIONS} or state["version"] != 1:
            raise ValueError()
        date_time(state["created_at"])
        date_time(state["last_poll"])
        for name in COLLECTIONS:
            if not isinstance(state[name], dict):
                raise ValueError()
        emails = set()
        for key, subscriber in state["subscribers"].items():
            if key != subscriber["id"] or not re.fullmatch(r"[a-f0-9]{16}", key):
                raise ValueError()
            if address(subscriber["email"]) != subscriber["email"] or subscriber["email"] in emails:
                raise ValueError()
            emails.add(subscriber["email"])
            if subscriber["status"] not in ("active", "paused", "stopped"):
                raise ValueError()
            if not re.fullmatch(r"[a-f0-9]{24}", subscriber["token"]):
                raise ValueError()
            date_time(subscriber["enrolled_at"])
            if "last_command" in subscriber:
                date_time(subscriber["last_command"][0])
                if len(subscriber["last_command"]) != 2 or not isinstance(subscriber["last_command"][1], str):
                    raise ValueError()
            if subscriber["pause_until"] is not None:
                date_time(subscriber["pause_until"])
                if subscriber["status"] != "paused":
                    raise ValueError()
        for day, batch in state["batches"].items():
            if day != batch["date"] or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                raise ValueError()
            if type(batch["fresh"]) is not bool or not isinstance(batch["stage"], str):
                raise ValueError()
            validate_questions(batch["questions"])
        for key, delivery in state["deliveries"].items():
            if delivery["status"] not in ("pending", "sent", "failed", "uncertain", "cancelled"):
                raise ValueError()
            if delivery["subscriber"] not in state["subscribers"] or delivery["kind"] not in ("daily", "notification", "test"):
                raise ValueError()
            if delivery["kind"] == "daily" and delivery["date"] not in state["batches"]:
                raise ValueError()
            if not isinstance(delivery["message_id"], str) or not delivery["message_id"].startswith("<practice."):
                raise ValueError()
            if not isinstance(key, str):
                raise ValueError()
        for command in state["commands"].values():
            if command["subscriber"] not in state["subscribers"]:
                raise ValueError()
            date_time(command["received"])
        for notification in state["notifications"].values():
            if notification["subscriber"] not in state["subscribers"] or not isinstance(notification["body"], str):
                raise ValueError()
    except (KeyError, IndexError, TypeError, ValueError, AttributeError, MailerError):
        raise MailerError("Private mailer state is invalid; preserve it and restore or repair it before sending.") from None
    return state


def encode_rows(state):
    validate_state(state)
    meta = {k: state[k] for k in ("version", "created_at", "last_poll")}
    rows = [["meta", json.dumps(meta, separators=(",", ":"))]]
    for name in COLLECTIONS:
        for key, value in sorted(state[name].items()):
            data = json.dumps(value, separators=(",", ":"))
            if len(data) > 45000:
                raise MailerError("A state record exceeds the supported Sheet cell size.")
            rows.append([name + ":" + key, data])
    return rows


def decode_rows(rows):
    if not rows:
        raise MailerError("Mailer state is empty; initialize a new private Sheet explicitly.")
    state = {name: {} for name in COLLECTIONS}
    seen = set()
    try:
        for row in rows:
            if not row or all(not v for v in row):
                continue
            if len(row) != 2 or row[0] in seen:
                raise ValueError()
            key, data = row
            seen.add(key)
            value = json.loads(data)
            if key == "meta":
                if set(value) != {"version", "created_at", "last_poll"}:
                    raise ValueError()
                state.update(value)
            else:
                collection, identifier = key.split(":", 1)
                state[collection][identifier] = value
    except (ValueError, TypeError, KeyError, AttributeError):
        raise MailerError("Cannot decode private mailer state; no data was reset.") from None
    return validate_state(state)


class SheetStore:
    BASE = "https://sheets.googleapis.com/v4/spreadsheets"

    def __init__(self, google, sheet_id):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", sheet_id or ""):
            raise MailerError("Set MAILER_SHEET_ID to the private spreadsheet ID.")
        self.google = google
        self.url = self.BASE + "/" + sheet_id
        self.previous_rows = 0
        self.tab = None

    @classmethod
    def create(cls, google):
        result = google.call("Sheets create", "POST", cls.BASE, {
            "properties": {"title": "Interview mailer — private state"},
            "sheets": [{"properties": {"title": TAB, "gridProperties": {"rowCount": 1000, "columnCount": 2}}}]}, retry=False)
        return result["spreadsheetId"]

    def load(self):
        result = self.google.call("Sheets read", "GET", self.url + "/values/" + quote(TAB + "!A:B", safe=""))
        rows = result.get("values", [])
        self.previous_rows = len(rows)
        return decode_rows(rows)

    def save(self, state):
        rows = encode_rows(state)
        total = max(self.previous_rows, len(rows))
        if self.tab is None:
            metadata = self.google.call("Sheets metadata", "GET", self.url + "?fields=sheets.properties")
            self.tab = next((s["properties"] for s in metadata["sheets"] if s["properties"]["title"] == TAB), None)
        tab = self.tab
        if tab is None:
            raise MailerError("Private Sheet is missing its MailerState tab.")
        if total > tab["gridProperties"]["rowCount"]:
            self.google.call("Sheets resize", "POST", self.url + ":batchUpdate", {"requests": [{
                "updateSheetProperties": {"properties": {"sheetId": tab["sheetId"],
                    "gridProperties": {"rowCount": total + 1000}}, "fields": "gridProperties.rowCount"}}]})
            tab["gridProperties"]["rowCount"] = total + 1000
        # One atomic range replacement. RAW prevents formula interpretation of user/model text.
        payload = {"range": f"{TAB}!A1:B{total}", "majorDimension": "ROWS",
                   "values": rows + [["", ""] for _ in range(total - len(rows))]}
        self.google.call("Sheets write", "PUT", self.url + "/values/" + quote(payload["range"], safe="")
                         + "?valueInputOption=RAW", payload)
        self.previous_rows = len(rows)
