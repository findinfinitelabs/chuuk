"""
A polite page fetcher for wol.jw.org used at request time: one request at a
time, spaced out, with every page kept in the ``wol_pages`` collection so
nothing is fetched twice. Index pages (publication and library listings) are
kept for a week since they change; articles are kept for good.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta, timezone

import requests

log = logging.getLogger(__name__)
COLLECTION = "wol_pages"
_DISK_CACHE = Path(__file__).resolve().parent.parent.parent / "data" / "wol_cache"
_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
_MIN_INTERVAL = 2.5
_lock = threading.Lock()
_last = 0.0


class PageFetcher:
    def __init__(self, db, timeout: int = 30):
        self.col = db[COLLECTION] if db is not None else None
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": _UA, "Accept-Language": "en-US,en;q=0.9"})

    def get(self, url: str) -> str | None:
        index_page = "/wol/d/" not in url and "/wol/b/" not in url
        if self.col is not None:
            try:
                doc = self.col.find_one({"url": url}, {"html": 1, "fetched_at": 1})
            except Exception:
                doc = None
            if doc and doc.get("html"):
                fresh = not index_page or (doc.get("fetched_at") and doc["fetched_at"].replace(tzinfo=timezone.utc) > datetime.now(timezone.utc) - timedelta(days=7))
                if fresh:
                    return doc["html"]
        # Pages the harvest scripts already hold on disk (development machine only).
        disk = _DISK_CACHE / f"{hashlib.sha1(url.encode('utf-8')).hexdigest()}.html"
        if disk.exists():
            return disk.read_text(encoding="utf-8")
        global _last
        with _lock:
            wait = _MIN_INTERVAL - (time.monotonic() - _last)
            if wait > 0:
                time.sleep(wait)
            _last = time.monotonic()
        try:
            r = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as e:
            log.warning("wol.jw.org fetch failed: %s (%s)", url, e)
            return None
        if r.status_code != 200 or len(r.text) < 500:
            # An empty 202 is wol.jw.org declining automated requests for a while.
            log.warning("wol.jw.org answered %s with %s bytes for %s", r.status_code, len(r.text), url)
            return None
        log.info("wol.jw.org page fetched: %s (%s bytes)", url, len(r.text))
        if self.col is not None:
            try:
                self.col.update_one({"url": url}, {"$set": {"url": url, "html": r.text, "fetched_at": datetime.now(timezone.utc)}}, upsert=True)
            except Exception as e:
                log.warning("could not cache wol.jw.org page %s: %s", url, e)
        return r.text
