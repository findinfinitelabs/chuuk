#!/usr/bin/env python3
"""
Harvest a year of a wol.jw.org publication into Chuukese/English sentence
pairs for training.

Walks the Chuukese library index (publication → year → issues → articles),
fetches every article in Chuukese and in English, pairs paragraphs by their
shared ids and sentences by position, and writes the pairs to the phrases
collection (where the pair collector and both retraining scripts read them)
and to a JSON snapshot under training_data/.

Every request lands on wol.jw.org, so this script is deliberately slow:
one request at a time, a pause of several seconds with jitter between
requests, every page cached on disk so a re-run costs nothing, a hard cap on
requests per run, and long back-offs on any error response. A year of the
Watchtower and the meeting workbook is roughly 300 requests, about 40 minutes.

    .venv/bin/python scripts/harvest_wol_pairs.py --pub mwb --year 2025
    .venv/bin/python scripts/harvest_wol_pairs.py --pub watchtower --year 2025 --editions study
    .venv/bin/python scripts/harvest_wol_pairs.py --pub both --year 2025 --dry-run   # no database writes

Re-running is safe: pairs upsert on a deterministic id, and cached pages
are reused.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.core import wol_harvest as wh  # noqa: E402
from src.core.wol_search import WOL_BASE  # noqa: E402

CACHE_DIR = PROJECT_ROOT / "data" / "wol_cache"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def log(msg: str) -> None:
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


class PoliteFetcher:
    """One request at a time, spaced out, cached, backing off on trouble.

    `min_interval` seconds plus up to `jitter` seconds of random delay
    between requests. A 429 or 5xx waits `backoff` seconds (doubling) and
    retries up to three times; after `max_failures` consecutive failures the
    run stops rather than keep hammering a struggling server.
    """

    def __init__(self, min_interval: float, jitter: float, max_requests: int, backoff: float = 120.0, max_failures: int = 3):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"})
        self.min_interval = min_interval
        self.jitter = jitter
        self.max_requests = max_requests
        self.backoff = backoff
        self.max_failures = max_failures
        self.requests_made = 0
        self.cache_hits = 0
        self.failures = 0
        self._last = 0.0

    def _cache_path(self, url: str) -> Path:
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()
        return CACHE_DIR / f"{digest}.html"

    def get(self, url: str, timeout: int = 45) -> str | None:
        path = self._cache_path(url)
        if path.exists():
            self.cache_hits += 1
            return path.read_text(encoding="utf-8")
        if self.requests_made >= self.max_requests:
            raise RuntimeError(f"Request cap of {self.max_requests} reached; rerun to continue (cached pages are kept)")

        wait = self.min_interval + random.uniform(0, self.jitter) - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)

        delay = self.backoff
        for attempt in range(3):
            self._last = time.monotonic()
            self.requests_made += 1
            try:
                resp = self.session.get(url, timeout=timeout)
            except requests.RequestException as e:
                log(f"   network error on {url}: {e}; waiting {delay:.0f}s")
                time.sleep(delay)
                delay *= 2
                continue
            if resp.status_code == 404:
                self.failures = 0
                return None
            if resp.status_code == 429 or resp.status_code >= 500:
                retry_after = resp.headers.get("Retry-After")
                pause = max(delay, float(retry_after)) if retry_after and retry_after.isdigit() else delay
                log(f"   HTTP {resp.status_code} on {url}; backing off {pause:.0f}s")
                time.sleep(pause)
                delay *= 2
                continue
            resp.raise_for_status()
            self.failures = 0
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            path.write_text(resp.text, encoding="utf-8")
            return resp.text

        self.failures += 1
        if self.failures >= self.max_failures:
            raise RuntimeError("Too many consecutive failures; stopping so wol.jw.org is not hammered")
        return None


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover(fetcher: PoliteFetcher, publication: str, year: int, editions: list[str]) -> list[tuple[str, str, str]]:
    """(doc_id, issue label, title) for every article of the publication year."""
    slug = wh.PUBLICATIONS[publication]["slug"]
    index_html = fetcher.get(WOL_BASE + f"{wh.CHK_LIBRARY}/{slug}")
    if not index_html:
        raise RuntimeError(f"Could not read the {publication} index")
    year_href = wh.year_link(index_html, publication, year)
    if not year_href:
        raise RuntimeError(f"No {publication} {year} in the Chuukese library index")
    log(f"{publication} {year}: {year_href}")

    year_html = fetcher.get(WOL_BASE + requests.utils.quote(year_href))
    if not year_html:
        raise RuntimeError("Could not read the year page")

    # The Watchtower year page lists editions; the workbook year page lists issues.
    issue_pages: list[tuple[str, str]] = []
    if publication == "watchtower":
        for name in editions:
            edition_slug = wh.WATCHTOWER_EDITIONS[name]
            href = f"{year_href}/{edition_slug}"
            html = fetcher.get(WOL_BASE + requests.utils.quote(href))
            if not html:
                log(f"   no {name} edition page for {year}")
                continue
            issue_pages += [(h, f"{name} {t}") for h, t in wh.child_links(html, href)]
    else:
        issue_pages = wh.child_links(year_html, year_href)
    log(f"   {len(issue_pages)} issue pages")

    docs: list[tuple[str, str, str]] = []
    seen = set()
    for href, label in issue_pages:
        html = fetcher.get(WOL_BASE + requests.utils.quote(href))
        if not html:
            continue
        for doc_id, title in wh.doc_links(html):
            if doc_id in seen:
                continue
            seen.add(doc_id)
            docs.append((doc_id, label, title))
    log(f"   {len(docs)} articles")
    return docs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="Harvest Chuukese/English sentence pairs from a wol.jw.org publication year")
    ap.add_argument("--pub", choices=["watchtower", "mwb", "both"], default="both")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--editions", default="study,public", help="Watchtower editions: study, public (comma-separated)")
    ap.add_argument("--min-interval", type=float, default=5.0, help="Seconds between requests (default 5)")
    ap.add_argument("--jitter", type=float, default=3.0, help="Extra random seconds between requests (default up to 3)")
    ap.add_argument("--max-requests", type=int, default=400, help="Hard cap on live requests per run (default 400)")
    ap.add_argument("--limit-docs", type=int, default=0, help="Only process the first N articles (0 = all)")
    ap.add_argument("--dry-run", action="store_true", help="Do not write to the database")
    ap.add_argument("--no-db", action="store_true", help="Same as --dry-run")
    args = ap.parse_args()

    publications = ["watchtower", "mwb"] if args.pub == "both" else [args.pub]
    editions = [e.strip() for e in args.editions.split(",") if e.strip()]
    write_db = not (args.dry_run or args.no_db)

    collection = None
    if write_db:
        from src.database.dictionary_db import DictionaryDB

        db = DictionaryDB()
        if not db.client:
            log("❌ No database connection. Use --dry-run to only write the JSON snapshot.")
            return 1
        collection = db.phrases_collection

    fetcher = PoliteFetcher(args.min_interval, args.jitter, args.max_requests)
    totals = {"docs": 0, "pairs": 0, "sentence": 0, "paragraph": 0, "inserted": 0, "updated": 0, "missing_en": 0}

    try:
        for publication in publications:
            docs = discover(fetcher, publication, args.year, editions)
            if args.limit_docs:
                docs = docs[: args.limit_docs]
            snapshot: list[dict] = []
            # A dry run keeps its own snapshot, so it never makes a real run
            # skip articles that were never written to the database.
            suffix = ".dryrun.json" if not write_db else ".json"
            out_path = PROJECT_ROOT / "training_data" / f"wol_harvest_{wh.PUBLICATIONS[publication]['code']}_{args.year}{suffix}"
            if out_path.exists():
                with open(out_path, encoding="utf-8") as f:
                    snapshot = json.load(f)
            done_docs = {p["doc_id"] for p in snapshot}

            for n, (doc_id, label, title) in enumerate(docs, 1):
                if doc_id in done_docs:
                    continue
                chk_html = fetcher.get(wh.doc_url(doc_id, "chk"))
                eng_html = fetcher.get(wh.doc_url(doc_id, "en"))
                if not chk_html or not eng_html:
                    totals["missing_en"] += 1
                    log(f"   [{n}/{len(docs)}] {doc_id} {title[:50]}: missing an edition, skipped")
                    continue
                chk_doc = wh.parse_document(chk_html)
                eng_doc = wh.parse_document(eng_html)
                pairs = wh.pair_documents(doc_id, chk_doc, eng_doc)
                totals["docs"] += 1
                totals["pairs"] += len(pairs)
                for p in pairs:
                    totals[p["type"]] += 1

                now = datetime.now(timezone.utc)
                records = [wh.pair_record(p, publication, args.year, chk_doc, eng_doc, now) for p in pairs]
                if collection is not None:
                    for rec in records:
                        rec_id = rec.pop("_id")
                        res = collection.update_one(
                            {"_id": rec_id},
                            {"$set": rec, "$setOnInsert": {"date_added": now, "created_date": now}},
                            upsert=True,
                        )
                        if res.upserted_id is not None:
                            totals["inserted"] += 1
                        else:
                            totals["updated"] += 1
                        rec["_id"] = rec_id
                for rec in records:
                    row = {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in rec.items()}
                    row["chuukese"] = row.pop("chuukese_sentence")
                    row["english"] = row["english_translation"]
                    snapshot.append(row)
                out_path.parent.mkdir(parents=True, exist_ok=True)
                with open(out_path, "w", encoding="utf-8") as f:
                    json.dump(snapshot, f, ensure_ascii=False, indent=1)

                log(f"   [{n}/{len(docs)}] {label} · {title[:45]}: {len(pairs)} pairs "
                    f"({fetcher.requests_made} live requests, {fetcher.cache_hits} cached)")
            log(f"{publication} {args.year}: snapshot {out_path} ({len(snapshot)} pairs)")
    except RuntimeError as e:
        log(f"⏹  {e}")
    except KeyboardInterrupt:
        log("⏹  Interrupted; cached pages and written pairs are kept")

    log("")
    log(f"Articles paired : {totals['docs']}  (skipped, missing an edition: {totals['missing_en']})")
    log(f"Pairs           : {totals['pairs']}  ({totals['sentence']} sentences, {totals['paragraph']} paragraphs)")
    if write_db:
        log(f"Database        : {totals['inserted']} inserted, {totals['updated']} updated")
    log(f"Live requests   : {fetcher.requests_made}  (cache hits: {fetcher.cache_hits})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
