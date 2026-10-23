"""Small REST adapters. Provider errors deliberately exclude response bodies."""
from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import os
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .domain import MailerError, ProviderError, address

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly",
          "https://www.googleapis.com/auth/gmail.send",
          "https://www.googleapis.com/auth/spreadsheets"]


class HTTPFailure(ProviderError):
    def __init__(self, service, status=None):
        self.status = status
        super().__init__(f"{service} request failed" + (f" (HTTP {status})." if status else " (network/response error)."))


class SendRejected(ProviderError):
    """A definite HTTP rejection: no delivery was accepted."""


def request_json(service, method, url, headers=None, payload=None, form=False, retry=True):
    body = None
    request_headers = dict(headers or {})
    if payload is not None:
        body = (urlencode(payload) if form else json.dumps(payload)).encode()
        request_headers["Content-Type"] = "application/x-www-form-urlencoded" if form else "application/json"
    attempts = 3 if retry else 1
    for attempt in range(attempts):
        try:
            req = Request(url, data=body, headers=request_headers, method=method)
            with urlopen(req, timeout=45) as response:
                raw = response.read(8_000_001)
                if len(raw) > 8_000_000:
                    raise ValueError()
                return json.loads(raw) if raw else {}
        except HTTPError as error:
            status = error.code
            retry_after = error.headers.get("Retry-After", "30") if error.headers else "30"
            error.close()
            if attempt + 1 < attempts and status in (429, 500, 502, 503, 504):
                # Sheets quotas refill each minute. Two 30-second waits allow a
                # full window to recover without an unbounded retry loop.
                delay = max(30, min(int(retry_after), 60)) if status == 429 and retry_after.isdigit() else 2 ** attempt
                time.sleep(delay)
                continue
            raise HTTPFailure(service, status) from None
        except (URLError, TimeoutError, socket.timeout, OSError, ValueError):
            if attempt + 1 < attempts:
                time.sleep(2 ** attempt)
                continue
            raise HTTPFailure(service) from None


class GoogleAPI:
    def __init__(self, credentials):
        try:
            required = ("client_id", "client_secret", "refresh_token")
            if not all(isinstance(credentials[k], str) and credentials[k] for k in required):
                raise ValueError()
            response = request_json("Google authorization", "POST", "https://oauth2.googleapis.com/token", payload={
                "grant_type": "refresh_token", **{k: credentials[k] for k in required}}, form=True)
            self.token = response["access_token"]
        except (KeyError, TypeError, ValueError):
            raise MailerError("Invalid Google OAuth credentials; run local OAuth setup.") from None

    @classmethod
    def from_environment(cls):
        try:
            credentials = json.loads(os.environ["MAILER_GOOGLE_CREDENTIALS"])
        except (KeyError, ValueError):
            raise MailerError("Set MAILER_GOOGLE_CREDENTIALS to the authorized-user OAuth JSON.") from None
        return cls(credentials)

    def call(self, service, method, url, payload=None, retry=True):
        if not url.startswith(("https://gmail.googleapis.com/", "https://sheets.googleapis.com/")):
            raise MailerError("Unsupported Google API endpoint.")
        return request_json(service, method, url, {"Authorization": "Bearer " + self.token}, payload, retry=retry)


class Gmail:
    BASE = "https://gmail.googleapis.com/gmail/v1/users/me"

    def __init__(self, google, sender):
        self.google = google
        self.sender = address(sender)
        if "+" in self.sender.split("@")[0] or len(self.sender.split("@")[0]) > 30:
            raise MailerError("Use a primary sending address with a local part of at most 30 characters.")
        profile = self.google.call("Gmail profile", "GET", self.BASE + "/profile")
        if profile.get("emailAddress", "").lower() != self.sender:
            raise MailerError("OAuth account does not match MAILER_SENDER.")

    def list_ids(self, query):
        page = None
        ids = []
        while True:
            params = {"q": query, "maxResults": 100}
            if page:
                params["pageToken"] = page
            result = self.google.call("Gmail list", "GET", self.BASE + "/messages?" + urlencode(params))
            ids.extend(m["id"] for m in result.get("messages", []))
            page = result.get("nextPageToken")
            if not page:
                return ids
            if len(ids) >= 10000:
                raise MailerError("Inbox scan exceeded the limit; inspect the dedicated inbox before retrying.")

    def incoming(self, since):
        # Includes read and archived messages. Do not rely on UNREAD as a processing flag.
        ids = self.list_ids(f"after:{int(since.timestamp()) - 1} -in:sent -in:drafts")
        messages = []
        try:
            for gmail_id in ids:
                data = self.google.call("Gmail read", "GET", self.BASE + "/messages/" + quote(gmail_id, safe="") + "?format=raw")
                raw = base64.urlsafe_b64decode(data["raw"] + "===")
                received = datetime.fromtimestamp(int(data["internalDate"]) / 1000, timezone.utc)
                messages.append({"id": gmail_id, "raw": raw, "received": received})
        except (KeyError, ValueError, TypeError):
            raise MailerError("Invalid Gmail message response; no daily mail was sent.") from None
        return sorted(messages, key=lambda item: (item["received"], item["id"]))

    def find_sent(self, rfc_message_id):
        ids = self.list_ids("in:sent rfc822msgid:" + rfc_message_id.strip("<>"))
        return ids[0] if ids else None

    def send(self, raw):
        try:
            # Never automatically retry this non-idempotent operation.
            result = self.google.call("Gmail send", "POST", self.BASE + "/messages/send",
                                      {"raw": base64.urlsafe_b64encode(raw).decode()}, retry=False)
        except HTTPFailure as error:
            if error.status and 400 <= error.status < 500 and error.status != 408:
                raise SendRejected("Gmail rejected a send; it can be retried at a later run.") from None
            raise
        if not isinstance(result.get("id"), str) or not result["id"]:
            raise ProviderError("Gmail send result is ambiguous; reconciliation is required.")
        return result["id"]


class Gemini:
    BASE = "https://generativelanguage.googleapis.com/v1beta/models/"

    def __init__(self, model, key=None, free_tier_confirmed=False):
        self.model = model
        self.key = key
        self.free_tier_confirmed = free_tier_confirmed

    @classmethod
    def from_environment(cls, model):
        return cls(model, os.environ.get("GEMINI_API_KEY"),
                   os.environ.get("MAILER_GEMINI_FREE_TIER_CONFIRMED", "").lower() == "true")

    def _headers(self):
        if not self.key or not self.free_tier_confirmed:
            raise MailerError("Gemini is disabled until a free-tier API project is confirmed and its key configured.")
        return {"x-goog-api-key": self.key}

    def check(self):
        data = request_json("Gemini model", "GET", self.BASE + quote(self.model, safe=""), self._headers())
        if "generateContent" not in data.get("supportedGenerationMethods", []):
            raise MailerError("Configured model does not support generateContent.")

    def generate_json(self, prompt, schema, max_tokens=8192):
        response = request_json("Gemini", "POST", self.BASE + quote(self.model, safe="") + ":generateContent",
                                self._headers(), {"contents": [{"parts": [{"text": prompt}]}],
                                "generationConfig": {"responseMimeType": "application/json",
                                                     "responseJsonSchema": schema,
                                                     "maxOutputTokens": max_tokens}}, retry=False)
        try:
            candidate = response["candidates"][0]
            if candidate.get("finishReason") != "STOP":
                raise ValueError()
            text = "".join(p.get("text", "") for p in candidate["content"]["parts"] if not p.get("thought"))
            return json.loads(text)
        except (KeyError, IndexError, TypeError, ValueError):
            raise MailerError("Gemini returned an incomplete or invalid structured response.") from None
