#!/usr/bin/env python3
"""Collect the TMDB data the /guides pages need and save it to guides_data.json.

  - Which licensed services stream each title in the Philippines (region PH, data by JustWatch).
  - "Similar shows" (TMDB recommendations) for the shows that have a "Dramas like ..." guide.

Run it on your Mac (it takes a few minutes):
  export TMDB_API_KEY="paste-your-key-here"
  python3 guides_data.py

Then run generate_site.py again. Titles already looked up are skipped; add --refresh to redo them.
"""

import argparse
import csv
import json
import re
import time
from pathlib import Path

import enrich_tmdb as tm  # reuses the key handling and TMDB request code

BASE_DIR = Path(__file__).resolve().parent
OUT = BASE_DIR / "guides_data.json"
REGION = "PH"
# Shows that get a "Dramas like ..." guide (slugs from catalog.csv).
SIMILAR_SEEDS = ["queen-of-tears", "squid-game-season-3", "alchemy-of-souls", "lovely-runner"]


def providers_for(where):
    names = []
    for bucket in ("flatrate", "free", "ads"):
        for p in where.get(bucket, []):
            name = re.sub(r"\s+(Standard|Basic)?\s*with Ads$", "", p.get("provider_name") or "")
            name = re.sub(r"\s+(Amazon|Apple TV|Roku Premium)\s+Channel$", "", name)
            if name and name not in names:
                names.append(name)
    return names


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    auth = tm.get_auth()

    with tm.CATALOG.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    data = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() and not args.refresh else {}
    data.setdefault("ph", {})
    data.setdefault("similar", {})

    by_id = {}
    for r in rows:
        if r.get("tmdb_id") and ":" in r["tmdb_id"]:
            by_id.setdefault(r["tmdb_id"], []).append(r["slug"])

    todo = [tid for tid in by_id if tid not in data["ph"]]
    print(f"Looking up Philippines streaming for {len(todo)} title(s)...")
    for i, tid in enumerate(todo, start=1):
        media, num = tid.split(":", 1)
        res = tm.tmdb(f"/{media}/{num}/watch/providers", auth) or {}
        where = (res.get("results") or {}).get(REGION) or {}
        data["ph"][tid] = {"providers": providers_for(where), "link": where.get("link", "")}
        if i % 100 == 0:
            print(f"  {i}/{len(todo)}")
            OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(0.03)

    slug_to_id = {r["slug"]: r.get("tmdb_id", "") for r in rows}
    for seed in SIMILAR_SEEDS:
        tid = slug_to_id.get(seed, "")
        if not tid or (seed in data["similar"] and not args.refresh):
            continue
        media, num = tid.split(":", 1)
        ids = []
        for page in (1, 2):
            res = tm.tmdb(f"/{media}/{num}/recommendations", auth, page=page) or {}
            ids += [f'{r.get("media_type", media)}:{r["id"]}' for r in res.get("results", [])]
        # keep only titles that are in our catalog, in TMDB's order
        data["similar"][seed] = [by_id[i][0] for i in ids if i in by_id and i != tid]
        print(f"  {seed}: {len(data['similar'][seed])} similar titles in the catalog")

    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Saved {OUT.name}. Now run: python3 generate_site.py")


if __name__ == "__main__":
    main()
