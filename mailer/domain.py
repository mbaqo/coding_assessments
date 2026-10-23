"""Pure configuration, curriculum, message rendering, and reply parsing."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses
from html import escape
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import secrets
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
UTC = timezone.utc


class MailerError(Exception):
    """A safe-to-display error: never include provider bodies or personal data."""


class ProviderError(MailerError):
    pass


@dataclass(frozen=True)
class Config:
    timezone: str = "America/Los_Angeles"
    send_time: str = "08:15"
    days_per_stage: int = 14
    max_subscribers: int = 25
    model: str = "gemini-3.1-flash-lite"

    @classmethod
    def read(cls, filename=None):
        try:
            data = json.loads(Path(filename).read_text()) if filename else {}
            config = cls(**data)
            ZoneInfo(config.timezone)
            if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", config.send_time):
                raise ValueError()
            if type(config.days_per_stage) is not int or not 1 <= config.days_per_stage <= 365:
                raise ValueError()
            if type(config.max_subscribers) is not int or not 1 <= config.max_subscribers <= 100:
                raise ValueError()
            if not re.fullmatch(r"gemini-[a-z0-9.-]+", config.model):
                raise ValueError()
            return config
        except (OSError, ValueError, TypeError, KeyError):
            raise MailerError("Invalid mailer configuration; check timezone, send time, limits, and model.") from None


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat()


def date_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("Timezone required")
    return parsed.astimezone(UTC)


def address(value: str) -> str:
    """Require an ordinary bare address, never a header or display-name fragment."""
    if not isinstance(value, str) or len(value) > 254 or not re.fullmatch(
        r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}", value
    ):
        raise MailerError("Supply a valid bare email address.")
    return value.lower()


def new_state(now: datetime) -> dict:
    return {"version": 1, "created_at": iso(now), "last_poll": iso(now),
            "subscribers": {}, "batches": {}, "deliveries": {}, "commands": {}, "notifications": {}}


def add_subscriber(state, email, now, maximum=25, reenroll=False):
    email = address(email)
    existing = next((s for s in state["subscribers"].values() if s["email"] == email), None)
    if existing:
        if not reenroll or existing["status"] != "stopped":
            raise MailerError("Address already enrolled; stopped subscribers require explicit reenrollment.")
        subscriber = existing
    else:
        if reenroll:
            raise MailerError("Reenrollment requires an existing stopped subscriber.")
        subscriber = {"id": secrets.token_hex(8), "email": email}
    live = sum(s["status"] != "stopped" for s in state["subscribers"].values())
    if live >= maximum:
        raise MailerError("Configured subscriber limit reached.")
    subscriber.update(status="active", pause_until=None, token=secrets.token_hex(12), enrolled_at=iso(now))
    subscriber.pop("last_command", None)
    state["subscribers"][subscriber["id"]] = subscriber
    return subscriber


STAGES = [
    ("Foundations", "arrays, strings, hash sets/maps, two pointers, stacks"),
    ("Core patterns", "sliding windows, prefix sums, binary search, intervals, sorting, linked lists"),
    ("Trees and search", "trees, heaps, BFS, DFS, graphs, recursion, backtracking"),
    ("Advanced patterns", "dynamic programming, greedy algorithms, tries, union-find, shortest paths"),
    ("Mixed practice", "mixed patterns, timed reasoning, parsing, debugging, follow-up constraints"),
]


def syllabus(state, config):
    delivered = {d["date"] for d in state["deliveries"].values() if d["status"] == "sent" and d["kind"] == "daily"}
    fresh = sum(b["fresh"] and day in delivered for day, b in state["batches"].items())
    index = min(fresh // config.days_per_stage, len(STAGES) - 1)
    name, topics = STAGES[index]
    mediums = 0 if index == 0 else 2 if index == 1 else 3
    return {"stage": name, "topics": topics, "batch_number": fresh + 1,
            "easy": 5 - mediums, "medium": mediums}


def fingerprint(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


QUESTION_KEYS = {"title", "difficulty", "topics", "target_minutes", "prompt", "constraints", "examples"}


def validate_questions(questions, recent=(), expected=None):
    """Structural checks complement model review; neither proves correctness."""
    def require(condition):
        if not condition:
            raise ValueError()

    try:
        require(isinstance(questions, list) and len(questions) == 5)
        seen = set()
        old = {fingerprint(q["title"]) for q in recent}
        old_prompts = {fingerprint(q["prompt"]) for q in recent}
        for q in questions:
            require(isinstance(q, dict) and set(q) == QUESTION_KEYS)
            require(all(isinstance(q[k], str) and q[k].strip() for k in ("title", "prompt", "constraints")))
            require(len(q["title"]) <= 120 and len(q["prompt"]) <= 3500 and len(q["constraints"]) <= 1500)
            require(q["difficulty"] in ("easy", "medium"))
            require(isinstance(q["topics"], list) and 1 <= len(q["topics"]) <= 5)
            require(all(isinstance(t, str) and re.fullmatch(r"[a-z]+(?:-[a-z]+)*", t) for t in q["topics"]))
            require(isinstance(q["target_minutes"], list) and len(q["target_minutes"]) == 2)
            low, high = q["target_minutes"]
            require(type(low) is int and type(high) is int and 1 <= low <= high <= 120)
            require(isinstance(q["examples"], list) and 1 <= len(q["examples"]) <= 4)
            for example in q["examples"]:
                require(isinstance(example, dict) and set(example) == {"input", "output"})
                require(all(isinstance(v, str) and 0 < len(v) <= 1000 for v in example.values()))
            title = fingerprint(q["title"])
            require(title and title not in seen and title not in old)
            require(fingerprint(q["prompt"]) not in old_prompts)
            seen.add(title)
            require(not re.search(r"(?im)^\s*(?:#{1,6}\s*)?(?:solution|reference solution|answer)\s*:", q["prompt"]))
        require(len(json.dumps(questions)) < 38000)
        if expected:
            require(sum(q["difficulty"] == "medium" for q in questions) == expected["medium"])
    except (TypeError, KeyError, ValueError):
        raise MailerError("Question batch failed validation.") from None
    return questions


def fallback_questions():
    """Read prompts only; never import learner solutions or reference answers."""
    from practice import read_prompt
    directory = ROOT / "days" / "day_01"
    catalog = json.loads((directory / "catalog.json").read_text())
    return [{"title": q["title"], "difficulty": q["difficulty"], "topics": q["topics"],
             "target_minutes": q["target_minutes"], "prompt": read_prompt(directory / q["file"]),
             "constraints": "See the contract in the prompt.",
             "examples": [{"input": "See prompt examples.", "output": "See prompt examples."}]}
            for q in catalog]


HELP = ("Reply with a command on the FIRST nonempty line:\n"
        "PAUSE — pause until RESUME\nPAUSE 7 — pause for seven days (1–365 supported)\n"
        "RESUME — resume a paused subscription\nSTOP or UNSUBSCRIBE — stop indefinitely\n"
        "HELP — show these instructions\n\n"
        "Replies are checked at scheduled runs, normally 08:15 and 08:45 America/Los_Angeles.\n"
        "No answers are required. Answers and learning progress are not tracked.\n"
        "After STOP, ask the organizer to explicitly enroll you again.")


def help_text(config):
    # The retry schedule lives in cron-job.org; do not promise an unconfigured time.
    return HELP.replace("normally 08:15 and 08:45 America/Los_Angeles",
                        "starting at {} {} each day".format(config.send_time, config.timezone))


def render_batch(batch, config):
    label = "Daily practice" if batch["fresh"] else "Review practice — saved questions"
    lines = [f"{label} · {batch['date']}", f"Focus: {batch['stage']}",
             "Five questions to practice at your own pace"]
    if not batch["fresh"]:
        lines.append("Today's new batch was unavailable. These are saved review questions and may repeat earlier emails.")
    for index, q in enumerate(batch["questions"], 1):
        lines.extend(["", f"{index}. {q['title']}",
                      f"{q['difficulty'].title()} | {', '.join(q['topics'])} | {q['target_minutes'][0]}–{q['target_minutes'][1]} min",
                      q["prompt"], "Constraints: " + q["constraints"], "Examples:"])
        lines.extend(f"  Input: {e['input']}\n  Output: {e['output']}" for e in q["examples"])
    lines.extend(["",
                  "", "--- Email preferences ---", help_text(config)])
    return "\n\n".join(lines)


def reply_address(sender, subscriber):
    local, domain = address(sender).split("@")
    return f"{local}+practice-{subscriber['token']}@{domain}"


def message_id(key, sender):
    digest = hashlib.sha256((sender + ":" + key).encode()).hexdigest()
    return f"<practice.{digest}@{sender.split('@')[1]}>"


def make_email(sender, subscriber, key, subject, body):
    msg = EmailMessage(policy=policy.SMTP)
    msg["From"] = address(sender)
    msg["To"] = subscriber["email"]
    msg["Reply-To"] = reply_address(sender, subscriber)
    msg["Subject"] = subject
    msg["Message-ID"] = message_id(key, sender)
    msg["Auto-Submitted"] = "auto-generated"
    msg.set_content(body)
    # Escape all model text; no external assets, executable HTML, or tracking pixels.
    msg.add_alternative("<html><body><pre style=\"white-space:pre-wrap;font-family:system-ui,sans-serif\">"
                        + escape(body) + "</pre></body></html>", subtype="html")
    return msg.as_bytes()


class ReplyHTML(HTMLParser):
    """Conservative visible text extraction; drop quotes, scripts, and styles."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        hidden = tag in ("blockquote", "script", "style", "head") or any(
            name in ("class", "id") and re.search(r"quote|signature", value or "", re.I) for name, value in attrs)
        if tag not in ("br", "hr", "img", "meta", "link", "input"):
            self.stack.append((tag, hidden or bool(self.stack and self.stack[-1][1])))
        if tag in ("br", "p", "div", "li", "tr"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i:]
                break
        if tag in ("p", "div", "li", "tr"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.stack or not self.stack[-1][1]:
            self.parts.append(data)


def parse_reply(raw, sender, subscribers):
    """Return (subscriber ID, command, days), or None. Never use an LLM here."""
    if len(raw) > 300_000:
        return None
    try:
        msg = BytesParser(policy=policy.default).parsebytes(raw)
        auto = str(msg.get("Auto-Submitted", "no")).lower()
        if auto != "no" or str(msg.get("Precedence", "")).lower() in ("bulk", "list", "junk"):
            return None
        if msg.get("List-Id") or msg.get_content_type() == "multipart/report":
            return None
        senders = getaddresses(msg.get_all("From", []))
        if len(senders) != 1:
            return None
        from_address = address(senders[0][1])
        recipients = {a.lower() for _, a in getaddresses(msg.get_all("To", []) + msg.get_all("Cc", []))}
        subscriber = next((s for s in subscribers.values() if s["email"] == from_address
                           and reply_address(sender, s) in recipients), None)
        if not subscriber:
            return None
        part = msg.get_body(preferencelist=("plain", "html"))
        if part is None or part.get_content_disposition() == "attachment":
            return None
        body = part.get_content()
        if part.get_content_type() == "text/html":
            parser = ReplyHTML()
            parser.feed(body)
            body = "".join(parser.parts)
        first = next((line.strip() for line in body.splitlines() if line.strip()), "")
        match = re.fullmatch(r"(PAUSE)(?:\s+([0-9]{1,3}))?|RESUME|STOP|UNSUBSCRIBE|HELP", first, re.I)
        if not match:
            return None
        words = first.upper().split()
        days = int(words[1]) if len(words) > 1 else None
        if days is not None and not 1 <= days <= 365:
            return subscriber["id"], "HELP", None
        return subscriber["id"], words[0], days
    except (ValueError, TypeError, LookupError, UnicodeError, MailerError):
        return None


def apply_command(subscriber, command, days, received):
    if command in ("STOP", "UNSUBSCRIBE"):
        subscriber.update(status="stopped", pause_until=None)
    elif command == "PAUSE" and subscriber["status"] != "stopped":
        subscriber.update(status="paused", pause_until=iso(received + timedelta(days=days)) if days else None)
    elif command == "RESUME" and subscriber["status"] == "paused":
        subscriber.update(status="active", pause_until=None)


def expire_pauses(state, now):
    for subscriber in state["subscribers"].values():
        if subscriber["status"] == "paused" and subscriber["pause_until"] and date_time(subscriber["pause_until"]) <= now:
            subscriber.update(status="active", pause_until=None)
