"""iCal feed fetcher and parser."""
import re
import json
import requests
import recurring_ical_events
from datetime import date, datetime, timezone
from icalendar import Calendar
from pathlib import Path

FEEDS_FILE = Path(__file__).parent.parent / "ical_feeds.json"

MEET_PATTERNS = [
    r'https?://meet\.google\.com/\S+',
    r'https?://[a-z0-9.-]+\.zoom\.us/[jw]/\S+',
    r'https?://teams\.microsoft\.com/\S+',
    r'https?://whereby\.com/\S+',
    r'https?://[a-z0-9.-]+\.webex\.com/\S+',
]
_MEET_RE = re.compile('|'.join(MEET_PATTERNS), re.IGNORECASE)


# ── Feed store ─────────────────────────────────────────────

def _load_feeds() -> list[dict]:
    if FEEDS_FILE.exists():
        try:
            return json.loads(FEEDS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def _save_feeds(feeds: list[dict]) -> None:
    FEEDS_FILE.write_text(json.dumps(feeds, ensure_ascii=False, indent=2), encoding="utf-8")


def list_feeds() -> list[dict]:
    return _load_feeds()


def add_feed(name: str, url: str, color: str = "#4285f4") -> dict:
    feeds = _load_feeds()
    feed = {"name": name, "url": url, "color": color, "enabled": True}
    feeds.append(feed)
    _save_feeds(feeds)
    return feed


def update_feed(idx: int, **kwargs) -> dict:
    feeds = _load_feeds()
    if idx < 0 or idx >= len(feeds):
        raise ValueError(f"Feed index {idx} out of range")
    feeds[idx].update({k: v for k, v in kwargs.items() if v is not None})
    _save_feeds(feeds)
    return feeds[idx]


def delete_feed(idx: int) -> None:
    feeds = _load_feeds()
    if idx < 0 or idx >= len(feeds):
        raise ValueError(f"Feed index {idx} out of range")
    feeds.pop(idx)
    _save_feeds(feeds)


# ── Parsing ────────────────────────────────────────────────

def _extract_meeting_link(text: str) -> str | None:
    if not text:
        return None
    m = _MEET_RE.search(str(text))
    return m.group(0).rstrip(r'\n ;,') if m else None


def _to_dt(val) -> datetime | None:
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)
    if isinstance(val, date):
        return datetime(val.year, val.month, val.day, tzinfo=timezone.utc)
    return None


def _event_to_dict(component, color: str, feed_name: str = "") -> dict:
    summary  = str(component.get("SUMMARY", "Sin título"))
    location = str(component.get("LOCATION", "") or "")
    desc     = str(component.get("DESCRIPTION", "") or "")
    url      = str(component.get("URL", "") or "")

    meet = (_extract_meeting_link(url)
            or _extract_meeting_link(location)
            or _extract_meeting_link(desc))

    start = _to_dt(component.get("DTSTART").dt if component.get("DTSTART") else None)
    end   = _to_dt(component.get("DTEND").dt   if component.get("DTEND")   else None)

    all_day = isinstance(component.get("DTSTART").dt, date) and \
              not isinstance(component.get("DTSTART").dt, datetime) \
              if component.get("DTSTART") else False

    return {
        "type":      "cal_event",
        "summary":   summary,
        "start":     start.isoformat() if start else None,
        "end":       end.isoformat()   if end   else None,
        "all_day":   all_day,
        "location":  location or None,
        "meet_url":  meet,
        "color":     color,
        "feed_name": feed_name,
    }


def fetch_events(start: date, end: date) -> list[dict]:
    """Return all calendar events across enabled feeds within [start, end]."""
    feeds  = _load_feeds()
    events = []

    for feed in feeds:
        if not feed.get("enabled", True):
            continue
        try:
            resp = requests.get(feed["url"], timeout=10)
            resp.raise_for_status()
            cal = Calendar.from_ical(resp.content)
            for component in recurring_ical_events.of(cal).between(start, end):
                if component.name == "VEVENT":
                    events.append(_event_to_dict(component, feed.get("color", "#4285f4"), feed.get("name", "")))
        except Exception as e:
            events.append({
                "type": "cal_error",
                "feed": feed["name"],
                "error": str(e),
            })

    events.sort(key=lambda e: e.get("start") or "")
    return events
