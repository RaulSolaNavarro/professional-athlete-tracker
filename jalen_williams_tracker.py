"""
Jalen Williams Injury Tracker
==============================
Monitors the web for Jalen Williams injury/return updates
and sends an SMS alert via Twilio when new news is detected.

Designed to run on GitHub Actions. Credentials are read from
environment variables (GitHub Secrets) — never hardcoded.

Dependencies:
  pip install requests twilio feedparser
"""

import os
import json
import hashlib
import logging
import feedparser
from datetime import datetime
from twilio.rest import Client

# ─────────────────────────────────────────────
# CREDENTIALS — read from environment variables
# (Set these as GitHub Secrets, not hardcoded)
# ─────────────────────────────────────────────
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM_NUMBER = os.environ["TWILIO_FROM_NUMBER"]
ALERT_TO_NUMBER    = os.environ["ALERT_TO_NUMBER"]

# ─────────────────────────────────────────────
# SETTINGS
# ─────────────────────────────────────────────
PLAYER_NAME = "Jalen Williams"
SEARCH_KEYWORDS = [
    "injury", "return", "out", "questionable", "day-to-day",
    "doubtful", "activated", "cleared", "available", "ruled out"
]
STATE_FILE = "jw_tracker_state.json"

# ─────────────────────────────────────────────
# LOGGING
# ─────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# RSS FEEDS TO MONITOR
# ─────────────────────────────────────────────
FEEDS = [
    "https://news.google.com/rss/search?q=Jalen+Williams+injury+OKC&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=Jalen+Williams+Thunder+return&hl=en-US&gl=US&ceid=US:en",
    "https://www.espn.com/espn/rss/nba/news",
]

# ─────────────────────────────────────────────
# STATE MANAGEMENT
# ─────────────────────────────────────────────

def load_state() -> set:
    """Load previously seen article IDs from disk."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            return set(data.get("seen_ids", []))
    return set()


def save_state(seen_ids: set):
    """Persist seen article IDs to disk."""
    with open(STATE_FILE, "w") as f:
        json.dump(
            {"seen_ids": list(seen_ids), "updated": datetime.now().isoformat()},
            f, indent=2
        )


def article_id(entry) -> str:
    """Generate a stable unique ID for a feed entry."""
    raw = (entry.get("link", "") + entry.get("title", "")).encode()
    return hashlib.md5(raw).hexdigest()

# ─────────────────────────────────────────────
# RELEVANCE CHECK
# ─────────────────────────────────────────────

def is_relevant(entry) -> bool:
    """
    Returns True if the article mentions Jalen Williams AND
    at least one injury/return-related keyword.
    """
    player = PLAYER_NAME.lower()
    keywords = [k.lower() for k in SEARCH_KEYWORDS]

    text = (
        entry.get("title", "") + " " +
        entry.get("summary", "") + " " +
        entry.get("link", "")
    ).lower()

    return player in text and any(kw in text for kw in keywords)

# ─────────────────────────────────────────────
# SMS NOTIFICATION
# ─────────────────────────────────────────────

def send_sms(title: str, link: str, source: str):
    """Send an SMS alert via Twilio."""
    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    body = (
        f"🏀 Jalen Williams Update\n"
        f"{title}\n"
        f"Source: {source}\n"
        f"{link}"
    )

    message = client.messages.create(
        body=body,
        from_=TWILIO_FROM_NUMBER,
        to=ALERT_TO_NUMBER
    )
    log.info(f"SMS sent! SID: {message.sid}")

# ─────────────────────────────────────────────
# MAIN CHECK LOGIC
# ─────────────────────────────────────────────

def check_for_updates():
    log.info("Checking for Jalen Williams injury updates...")
    seen_ids = load_state()
    new_articles = []

    for feed_url in FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                aid = article_id(entry)
                if aid in seen_ids:
                    continue

                if is_relevant(entry):
                    new_articles.append({
                        "id":     aid,
                        "title":  entry.get("title", "No title"),
                        "link":   entry.get("link", ""),
                        "source": feed.feed.get("title", feed_url),
                    })

                seen_ids.add(aid)

        except Exception as e:
            log.error(f"Error fetching feed {feed_url}: {e}")

    if new_articles:
        log.info(f"Found {len(new_articles)} new relevant article(s). Sending SMS...")
        for article in new_articles:
            try:
                send_sms(article["title"], article["link"], article["source"])
            except Exception as e:
                log.error(f"Failed to send SMS: {e}")
    else:
        log.info("No new updates found.")

    save_state(seen_ids)


if __name__ == "__main__":
    check_for_updates()
