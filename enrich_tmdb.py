#!/usr/bin/env python3
"""Fill in missing details in catalog.csv from TMDB (themoviedb.org).

It fills, only where the field is blank:
  cast (top 3), genre, year, poster, country of origin, and type (movie or series).
It also records, from TMDB:
  - the official YouTube trailer (only videos TMDB marks as official),
  - which licensed services stream the title in your region (data from JustWatch),
  - a popularity score, used for the Trending tab.

It never overwrites something you typed yourself. Descriptions are left alone
unless you add --overviews (that copies TMDB's own summary text, credited to TMDB).

How to run (on your Mac, in Terminal):
  export TMDB_API_KEY="paste-your-key-here"
  python3 enrich_tmdb.py

Options:
  --limit 50       only process the first 50 rows that still need work (good for a test)
  --region GB      which country's streaming services to look up (default US)
  --refresh        look rows up again even if they were done before
  --overviews      also fill blank descriptions with TMDB's summary

Progress is saved every 25 rows, so you can stop with Ctrl+C and run it again later.
Titles it could not match safely are written to tmdb_unmatched.txt.
"""

import argparse
import csv
import difflib
import json
import os
import re
import shutil
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
CATALOG = BASE_DIR / "catalog.csv"
UNMATCHED = BASE_DIR / "tmdb_unmatched.txt"
API = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w342"
BACKDROP = "https://image.tmdb.org/t/p/w780"
EXTRA_COLUMNS = ["type", "tmdb_id", "trailer_youtube_id", "watch_providers", "watch_link", "popularity", "country", "category", "backdrop_url"]

COUNTRY_NAMES = {
    "KR": "South Korea", "KP": "North Korea", "JP": "Japan", "CN": "China", "TW": "Taiwan",
    "HK": "Hong Kong", "TH": "Thailand", "PH": "Philippines", "VN": "Vietnam", "ID": "Indonesia",
    "MY": "Malaysia", "SG": "Singapore", "IN": "India", "TR": "Turkey", "US": "United States",
    "GB": "United Kingdom", "CA": "Canada", "AU": "Australia", "FR": "France", "DE": "Germany",
    "ES": "Spain", "IT": "Italy", "MX": "Mexico", "BR": "Brazil", "AR": "Argentina", "CO": "Colombia",
}

def pick_category(codes, genres, media):
    """K-Drama, C-Drama, Anime, ... from origin country + TMDB genres."""
    codes = set(codes or [])
    genres = set(genres or [])
    series = media == "tv"
    if "Animation" in genres:
        return "Anime" if "JP" in codes else "Animation"
    variety = bool(genres & {"Reality", "Talk"})
    if "KR" in codes:
        return "K-Variety" if variety else ("K-Drama" if series else "K-Movie")
    if codes & {"CN", "TW", "HK"}:
        return "C-Drama" if series else "C-Movie"
    if "JP" in codes:
        return "J-Drama" if series else "J-Movie"
    if "TH" in codes:
        return "Thai Drama" if series else "Thai Movie"
    if "PH" in codes:
        return "Filipino" if series else "Filipino Movie"
    if "TR" in codes:
        return "Turkish Drama" if series else "Turkish Movie"
    if variety:
        return "Variety"
    return "Western" if codes & {"US", "GB", "CA", "AU"} else "Other"


GENRE_RENAMES = {
    "Action & Adventure": "Action",
    "Sci-Fi & Fantasy": "Fantasy",
    "Science Fiction": "Sci-Fi",
    "War & Politics": "War",
    "TV Movie": "Drama",
}


def get_auth():
    key = os.environ.get("TMDB_API_KEY", "").strip()
    if not key:
        sys.exit(
            "ERROR: no TMDB key found.\n"
            "Get a free key at https://www.themoviedb.org/settings/api, then run:\n"
            '  export TMDB_API_KEY="your-key"\n'
            "  python3 enrich_tmdb.py"
        )
    # Long keys starting with eyJ are "Read Access Tokens"; short ones are v3 API keys.
    return ("bearer", key) if key.startswith("eyJ") else ("param", key)


def tmdb(path, auth, **params):
    kind, key = auth
    if kind == "param":
        params["api_key"] = key
    url = f"{API}{path}?{urllib.parse.urlencode(params)}"
    headers = {"Accept": "application/json", "User-Agent": "catalog-enricher/1.0"}
    if kind == "bearer":
        headers["Authorization"] = f"Bearer {key}"
    for attempt in range(5):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=20) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                sys.exit("ERROR: TMDB says the key is not valid (401). Check TMDB_API_KEY.")
            if exc.code == 404:
                return None
            if exc.code == 429:
                time.sleep(2 + attempt * 2)
                continue
            time.sleep(1 + attempt)
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1 + attempt)
    print(f"  ! gave up on {path}")
    return None


def search_query(title):
    """'Squid Game Season 2' -> 'Squid Game'; 'Taxi Driver - Season 3' -> 'Taxi Driver'."""
    q = re.sub(r"\s*[-:]?\s*\b(season|part|s)\s*\d+.*$", "", title, flags=re.I)
    q = re.sub(r"\s*\(.*?\)\s*", " ", q)
    return q.strip() or title


def norm(text):
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def pick_match(results, query, year):
    """Return the safest TMDB match, or None. Requires a close name, and the year when we know it."""
    best, best_score = None, 0.0
    for res in results or []:
        if res.get("media_type") not in ("tv", "movie"):
            continue
        names = [res.get("name"), res.get("title"), res.get("original_name"), res.get("original_title")]
        sim = max(difflib.SequenceMatcher(None, norm(query), norm(n)).ratio() for n in names if n) if any(names) else 0
        date = res.get("first_air_date") or res.get("release_date") or ""
        res_year = date[:4]
        if year and res_year and abs(int(year) - int(res_year)) > 1:
            continue
        if not year and sim < 0.999:
            continue  # without a year, only accept an exact name match
        score = sim + (0.2 if year and res_year == year else 0)
        if sim >= 0.6 and score > best_score:
            best, best_score = res, score
    return best


def pick_trailer(videos):
    vids = [v for v in (videos or {}).get("results", [])
            if v.get("site") == "YouTube" and v.get("official") and v.get("type") in ("Trailer", "Teaser")]
    vids.sort(key=lambda v: (v.get("type") != "Trailer", v.get("published_at") or ""))
    return vids[0]["key"] if vids else ""


def needs_work(row, refresh):
    if refresh or not row.get("tmdb_id") or not row.get("country") or not row.get("category") or not row.get("backdrop_url"):
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--region", default=os.environ.get("TMDB_REGION", "US"))
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--overviews", action="store_true")
    args = parser.parse_args()
    auth = get_auth()
    region = args.region.upper()

    with CATALOG.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fieldnames = [f.strip().lower() for f in reader.fieldnames or []]
        reader.fieldnames = fieldnames
        rows = [{k: (v or "").strip() for k, v in r.items() if k} for r in reader]
    for col in EXTRA_COLUMNS:
        if col not in fieldnames:
            fieldnames.append(col)

    backup_dir = BASE_DIR / "backups"
    backup_dir.mkdir(exist_ok=True)
    shutil.copy2(CATALOG, backup_dir / f"catalog-before-tmdb-{datetime.now():%Y%m%d-%H%M%S}.csv")

    def save():
        tmp = CATALOG.with_suffix(".tmp")
        with tmp.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in rows:
                writer.writerow({c: r.get(c, "") for c in fieldnames})
        tmp.replace(CATALOG)

    todo = [r for r in rows if needs_work(r, args.refresh)]
    if args.limit:
        todo = todo[: args.limit]
    print(f"{len(todo)} title(s) to look up (region {region}).")
    unmatched, done = [], 0

    try:
        for i, row in enumerate(todo, start=1):
            title = row.get("title", "")
            media, tmdb_id = None, None
            if row.get("tmdb_id") and ":" in row["tmdb_id"]:
                media, tmdb_id = row["tmdb_id"].split(":", 1)
            else:
                query = search_query(title)
                found = tmdb("/search/multi", auth, query=query, include_adult="false")
                match = pick_match((found or {}).get("results"), query, row.get("year", "")[:4])
                if not match:
                    unmatched.append(f'{row.get("slug")}\t{title}')
                    print(f"[{i}/{len(todo)}] no safe match: {title}")
                    continue
                media, tmdb_id = match["media_type"], str(match["id"])

            info = tmdb(f"/{media}/{tmdb_id}", auth, append_to_response="credits,videos,watch/providers")
            if not info:
                unmatched.append(f'{row.get("slug")}\t{title}')
                continue

            row["tmdb_id"] = f"{media}:{tmdb_id}"
            row["type"] = row.get("type") or ("series" if media == "tv" else "movie")
            if not row.get("cast"):
                names = [c["name"] for c in (info.get("credits") or {}).get("cast", [])[:3]]
                row["cast"] = ", ".join(names)
            if not row.get("genre") and info.get("genres"):
                g = info["genres"][0]["name"]
                row["genre"] = GENRE_RENAMES.get(g, g)
            if not row.get("year"):
                row["year"] = (info.get("first_air_date") or info.get("release_date") or "")[:4]
            if (not row.get("poster_url") or "placehold.co" in row["poster_url"]) and info.get("poster_path"):
                row["poster_url"] = IMG + info["poster_path"]
            if args.overviews and not row.get("description") and info.get("overview"):
                row["description"] = info["overview"].strip()

            trailer = ""
            season = re.search(r"\b(?:season|part|s)\s*(\d+)", title, flags=re.I)
            if media == "tv" and season and int(season.group(1)) > 1:
                trailer = pick_trailer(tmdb(f"/tv/{tmdb_id}/season/{int(season.group(1))}/videos", auth))
            trailer = trailer or pick_trailer(info.get("videos"))
            row["trailer_youtube_id"] = trailer or row.get("trailer_youtube_id", "")
            where = ((info.get("watch/providers") or {}).get("results") or {}).get(region) or {}
            providers = []
            for bucket in ("flatrate", "free", "ads"):
                for p in where.get(bucket, []):
                    name = re.sub(r"\s+(Standard|Basic)?\s*with Ads$", "", p.get("provider_name") or "")
                    if name and name not in providers:
                        providers.append(name)
            row["watch_providers"] = ";".join(providers)
            row["watch_link"] = where.get("link", "")
            row["popularity"] = f'{info.get("popularity", 0):.1f}'
            if not row.get("country"):
                codes = info.get("origin_country") or [c.get("iso_3166_1") for c in info.get("production_countries", [])]
                names = []
                for code in codes or []:
                    name = COUNTRY_NAMES.get(code, code)
                    if name and name not in names:
                        names.append(name)
                row["country"] = ", ".join(names[:2])
            if not row.get("backdrop_url"):
                # "none" = TMDB has no wide image, so we don't keep asking
                row["backdrop_url"] = BACKDROP + info["backdrop_path"] if info.get("backdrop_path") else "none"
            if not row.get("category"):
                codes = info.get("origin_country") or [c.get("iso_3166_1") for c in info.get("production_countries", [])]
                row["category"] = pick_category(codes, [g.get("name") for g in info.get("genres", [])], media)
            done += 1
            print(f"[{i}/{len(todo)}] {title}: {row['type']}"
                  f"{', trailer' if row['trailer_youtube_id'] else ''}"
                  f"{', ' + ', '.join(providers) if providers else ''}")
            if i % 25 == 0:
                save()
            time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nStopped. Saving what was done so far...")
    save()
    if unmatched:
        UNMATCHED.write_text("slug\ttitle\n" + "\n".join(unmatched) + "\n", encoding="utf-8")
    print(f"Done: {done} updated, {len(unmatched)} not matched"
          f"{' (see ' + UNMATCHED.name + ')' if unmatched else ''}.")


if __name__ == "__main__":
    main()
