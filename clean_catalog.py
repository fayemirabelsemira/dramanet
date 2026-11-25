#!/usr/bin/env python3
"""Tidy catalog.csv before building the site.

What it does:
  1. Makes a dated backup in backups/ first.
  2. Merges near-duplicate rows (for example "strong-girl-nam-soon" and
     "strong-girl-namsoon"). The row with more filled-in details is kept, and any
     blank fields in it are filled from the row that is removed.
  3. Adds the extra columns the site uses (type, tmdb_id, trailer_youtube_id,
     watch_providers, watch_link, popularity) if they are missing.
  4. Writes catalog_review.txt listing rows that share a poster with a different
     title. Those usually mean the metadata was matched to the wrong show, so
     check them by hand.

Run it with:  python3 clean_catalog.py
"""

import csv
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CATALOG = BASE_DIR / "catalog.csv"
REVIEW_FILE = BASE_DIR / "catalog_review.txt"

BASE_COLUMNS = ["title", "slug", "description", "cast", "genre", "year", "poster_url"]
EXTRA_COLUMNS = ["type", "tmdb_id", "trailer_youtube_id", "watch_providers", "watch_link", "popularity", "country", "category", "backdrop_url"]

# Pairs that are the same show under two names. Left side is removed and merged
# into the right side. Add more lines here if you spot others.
ALIASES = {
    "bon-appetit": "bon-appetit-your-majesty",
}


def squash(text):
    """'Strong Girl Nam-soon' and 'strong-girl-namsoon' both become 'stronggirlnamsoon'."""
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def richness(row):
    filled = sum(1 for col in BASE_COLUMNS + EXTRA_COLUMNS if row.get(col, "").strip())
    if "placehold.co" in row.get("poster_url", ""):
        filled -= 1
    return (filled, len(row.get("description", "")))


def merge(keep, drop):
    for col, value in drop.items():
        if value and not keep.get(col, "").strip():
            keep[col] = value
    if "placehold.co" in keep.get("poster_url", "") and "placehold.co" not in drop.get("poster_url", "placehold.co"):
        keep["poster_url"] = drop["poster_url"]


def base_name(slug):
    """'taxi-driver-season-2' -> 'taxi-driver'; used to tell seasons apart from mismatches."""
    return re.split(r"-(?:season|part|s)?-?\d", slug, maxsplit=1)[0]


def main():
    if not CATALOG.is_file():
        sys.exit(f"ERROR: {CATALOG.name} not found next to this script.")

    with CATALOG.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [f.strip().lower() for f in reader.fieldnames or []]
        reader.fieldnames = fieldnames
        rows = [{k: (v or "").strip() for k, v in r.items() if k} for r in reader]

    backup_dir = BASE_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / f"catalog-{datetime.now():%Y%m%d-%H%M%S}.csv"
    shutil.copy2(CATALOG, backup)
    print(f"Backup saved: backups/{backup.name}")

    for col in EXTRA_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)

    # Group rows that are the same title spelled differently.
    by_key = {}
    removed = []
    result = []
    slug_to_row = {}
    for row in rows:
        keys = {squash(row.get("slug")), squash(row.get("title"))} - {""}
        match = next((by_key[k] for k in keys if k in by_key), None)
        if match is None:
            for k in keys:
                by_key[k] = row
            result.append(row)
            slug_to_row[row["slug"]] = row
            continue
        keep, drop = (match, row) if richness(match) >= richness(row) else (row, match)
        merge(keep, drop)
        if keep is row:  # swap the kept row into the earlier position
            result[result.index(match)] = row
            slug_to_row.pop(match["slug"], None)
            slug_to_row[row["slug"]] = row
        for k in keys | {squash(match.get("slug")), squash(match.get("title"))}:
            by_key[k] = keep
        removed.append((drop["slug"], keep["slug"]))

    for old, new in ALIASES.items():
        if old in slug_to_row and new in slug_to_row:
            merge(slug_to_row[new], slug_to_row[old])
            result.remove(slug_to_row.pop(old))
            removed.append((old, new))

    with CATALOG.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in result:
            writer.writerow({col: row.get(col, "") for col in fieldnames})

    # Rows sharing one poster but with different base titles are probably mismatched.
    by_poster = defaultdict(list)
    for row in result:
        if row.get("poster_url") and "placehold.co" not in row["poster_url"]:
            by_poster[row["poster_url"]].append(row)
    review = []
    for group in by_poster.values():
        if len({base_name(r["slug"]) for r in group}) > 1:
            review.append(", ".join(f'{r["title"]} ({r["slug"]})' for r in group))

    with REVIEW_FILE.open("w", encoding="utf-8") as handle:
        handle.write("Merged duplicates (removed -> kept):\n")
        for old, new in removed:
            handle.write(f"  {old} -> {new}\n")
        handle.write("\nPlease check these: they share one poster but have different titles,\n"
                     "so one of them may have the wrong poster, cast or year.\n")
        for line in review:
            handle.write(f"  {line}\n")

    print(f"Rows before: {len(rows)}, after: {len(result)} ({len(removed)} duplicate(s) merged).")
    print(f"{len(review)} poster group(s) to check by hand, listed in {REVIEW_FILE.name}.")


if __name__ == "__main__":
    main()
