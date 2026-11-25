# StreamHub

A static guide site for K-dramas, C-dramas, anime and movies: official trailers, cast,
and where to watch each title on licensed services. No videos are hosted.

## Build

```bash
python3 generate_site.py
```

The finished website is written to `site_output/`. That is the folder to publish (see `DEPLOY.md`).

## Files

| File | What it does |
| --- | --- |
| `catalog.csv` | All titles and their details |
| `template.html` | Layout of each title page (keep the `AD SLOT` comments) |
| `generate_site.py` | Builds the site. Settings (`SITE_URL`, `CONTACT_EMAIL`, `GOOGLE_VERIFICATION`) are at the top |
| `guides.py` | Builds the `/guides` pages |
| `enrich_tmdb.py` | Fills missing details, trailers and where-to-watch from TMDB (needs `TMDB_API_KEY`) |
| `guides_data.py` | Refreshes Philippines streaming data and "similar shows" for the guides |
| `clean_catalog.py` | Merges duplicate titles |
| `DEPLOY.md` | Step-by-step publishing and Google Search Console guide |

The TMDB key is read from the `TMDB_API_KEY` environment variable and is never stored in this repository.

This product uses the TMDB API but is not endorsed or certified by TMDB. Streaming availability data by JustWatch.
