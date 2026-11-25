#!/usr/bin/env python3
"""DramaNet static site generator.

Reads catalog.csv (or content.csv) and template.html from this folder and writes a
ready-to-upload website into site_output/:
  - one page per title ({slug}.html) with the official trailer, if known, and
    where-to-watch links to licensed services
  - index.html: Netflix-style homepage (fading hero slideshow + scrolling rows)
  - explore.html: every title, with Type / Category / Region / Sort filters and search
  - privacy.html, terms.html, dmca.html, contact.html, 404.html
  - robots.txt and sitemap.xml (sitemap only once SITE_URL below is filled in)

Run it with:  python3 generate_site.py
"""

import csv
import html
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path
from urllib.parse import quote_plus

# ---------------------------------------------------------------------------
# Settings you can change
# ---------------------------------------------------------------------------
SITE_NAME = "DramaNet"
# Your live address once deployed, e.g. "https://dramanet.netlify.app" (no slash at the end).
# Leave it empty until you know it; the sitemap and canonical links need it.
SITE_URL = "https://dramanet.netlify.app"
# Google Search Console "HTML tag" code (just the content="..." part). See DEPLOY.md, step 3.
GOOGLE_VERIFICATION = ""
# Email shown on the Contact, Privacy and DMCA pages. Change this to your own address.
CONTACT_EMAIL = "contact@example.com"
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
TEMPLATE_FILE = BASE_DIR / "template.html"
CONTENT_FILES = [BASE_DIR / "catalog.csv", BASE_DIR / "content.csv"]
OUTPUT_DIR = BASE_DIR / "site_output"

REQUIRED_COLUMNS = ["title", "slug", "description", "cast", "genre", "year", "poster_url"]
FALLBACK_POSTER = "https://placehold.co/300x450/1f1f1f/e50914?text=No+Poster"
YOUTUBE_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")

# Search pages on licensed services. Used to turn a provider name into a link.
PROVIDER_SEARCH = {
    "netflix": "https://www.netflix.com/search?q={q}",
    "viki": "https://www.viki.com/search?q={q}",
    "crunchyroll": "https://www.crunchyroll.com/search?q={q}",
    "prime video": "https://www.primevideo.com/search/ref=atv_nb_sug?phrase={q}",
    "apple tv": "https://tv.apple.com/search?term={q}",
    "hulu": "https://www.hulu.com/search?q={q}",
    "youtube": "https://www.youtube.com/results?search_query={q}",
}
FALLBACK_SERVICES = ["Netflix", "Viki", "Prime Video"]


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def esc(value):
    return html.escape(value or "", quote=True)


def read_template(path):
    if not path.is_file():
        fail(f"Template file not found: {path}")
    return path.read_text(encoding="utf-8")


def read_content():
    path = next((p for p in CONTENT_FILES if p.is_file()), None)
    if path is None:
        fail("No catalog.csv or content.csv found next to this script.")
    print(f"Reading {path.name}")
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                fail(f"'{path.name}' is empty or has no header row.")
            headers = [name.strip().lower() for name in reader.fieldnames]
            missing = [col for col in REQUIRED_COLUMNS if col not in headers]
            if missing:
                fail(f"'{path.name}' is missing column(s): {', '.join(missing)}")
            reader.fieldnames = headers
            return [{k: (v or "").strip() for k, v in row.items() if k} for row in reader]
    except csv.Error as exc:
        fail(f"Malformed CSV in '{path.name}': {exc}")
    except (OSError, UnicodeDecodeError) as exc:
        fail(f"Could not read '{path.name}': {exc}")


def clean_slug(raw):
    slug = re.sub(r"[^a-z0-9-]+", "-", raw.lower()).strip("-")
    return re.sub(r"-{2,}", "-", slug)


def guess_type(row):
    """Use the 'type' column if filled (the TMDB script fills it); otherwise make a careful guess."""
    t = row.get("type", "").lower()
    if t in ("movie", "series"):
        return t
    text = f'{row.get("title", "")} {row.get("slug", "")}'.lower()
    if re.search(r"\b(season|episode|ep)\b|\bs\d+\b|\bpart[- ]?\d", text):
        return "series"
    if row.get("genre", "") in ("Reality", "Talk", "Soap"):
        return "series"
    if re.search(r"\b(movie|film)\b", text):
        return "movie"
    return ""


# ---------------------------------------------------------------------------
# Page pieces
# ---------------------------------------------------------------------------
def player_html(row):
    title = esc(row["title"])
    poster = esc(row.get("poster_url") or FALLBACK_POSTER)
    vid = row.get("trailer_youtube_id", "")
    if YOUTUBE_ID.match(vid):
        thumb = f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"
        return f"""      <div id="player" class="relative w-full aspect-video rounded-lg overflow-hidden bg-black shadow-2xl ring-1 ring-neutral-800 group">
        <img src="{thumb}" alt="" class="absolute inset-0 w-full h-full object-cover opacity-70" />
        <div class="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent"></div>
        <button id="playBtn" type="button" data-youtube="{vid}" class="absolute inset-0 flex items-center justify-center" aria-label="Play official trailer for {title}">
          <span class="w-16 h-16 sm:w-20 sm:h-20 rounded-full bg-brand/90 group-hover:bg-brand group-hover:scale-110 transition flex items-center justify-center shadow-lg shadow-brand/30">
            <svg class="w-8 h-8 sm:w-10 sm:h-10 text-white ml-1" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>
          </span>
        </button>
        <div class="absolute bottom-3 left-3 right-3 flex items-center justify-between text-xs text-neutral-300 pointer-events-none">
          <span class="px-2 py-0.5 rounded bg-black/60">Official trailer</span>
          <span class="px-2 py-0.5 rounded bg-black/60">{esc(row.get("year"))}</span>
        </div>
      </div>"""
    return f"""      <div id="player" class="relative w-full aspect-video rounded-lg overflow-hidden bg-black shadow-2xl ring-1 ring-neutral-800">
        <img src="{poster}"
             onerror="this.onerror=null;this.src='https://placehold.co/1280x720/111111/333333?text=%20';"
             alt="" class="absolute inset-0 w-full h-full object-cover opacity-40 blur-sm scale-110" />
        <div class="absolute inset-0 bg-gradient-to-t from-black/90 via-black/40 to-black/20"></div>
        <div class="absolute inset-0 flex flex-col items-center justify-center text-center px-6">
          <p class="text-base sm:text-lg font-semibold">Trailer coming soon</p>
          <p class="mt-1 text-xs sm:text-sm text-neutral-300">See where you can watch {title} legally below.</p>
          <a href="#where-to-watch" class="mt-4 inline-flex items-center gap-2 px-4 py-2 rounded bg-brand hover:bg-brand-dark text-sm font-semibold">Where to watch &darr;</a>
        </div>
      </div>"""


def provider_link(name, title, fallback):
    key = name.lower()
    for known, pattern in PROVIDER_SEARCH.items():
        if known in key:
            return pattern.format(q=quote_plus(title))
    return fallback


def watch_html(row):
    title = row["title"]
    justwatch = f"https://www.justwatch.com/us/search?q={quote_plus(title)}"
    link = row.get("watch_link") or justwatch
    providers = []
    for p in row.get("watch_providers", "").split(";"):
        # "Kocowa Amazon Channel" is the same show as "Kocowa"; list each service once.
        p = re.sub(r"\s+(Amazon|Apple TV|Roku Premium)\s+Channel$", "", p.strip())
        if p and p not in providers:
            providers.append(p)
    btn = ("inline-flex items-center px-3 py-2 rounded bg-neutral-800 hover:bg-neutral-700 "
           "text-sm font-medium text-white")
    if providers:
        intro = "Stream it on these licensed services:"
        buttons = [f'<a href="{esc(provider_link(p, title, link))}" target="_blank" rel="noopener nofollow" class="{btn}">{esc(p)}</a>'
                   for p in providers]
        note = ('<p class="mt-3 text-xs text-neutral-500">Availability can change by country. '
                f'<a href="{esc(link)}" target="_blank" rel="noopener nofollow" class="underline hover:text-neutral-300">See all options</a>. '
                'Streaming data by JustWatch via TMDB.</p>')
    else:
        intro = "Search for it on licensed services:"
        buttons = [f'<a href="{esc(provider_link(p, title, justwatch))}" target="_blank" rel="noopener nofollow" class="{btn}">Search {esc(p)}</a>'
                   for p in FALLBACK_SERVICES]
        buttons.append(f'<a href="{esc(justwatch)}" target="_blank" rel="noopener nofollow" class="{btn}">Check JustWatch</a>')
        note = '<p class="mt-3 text-xs text-neutral-500">We only link to official, licensed services.</p>'
    return f"""      <section id="where-to-watch" class="mt-4 p-4 rounded-lg bg-neutral-900 ring-1 ring-neutral-800" aria-labelledby="wtw-heading">
        <h2 id="wtw-heading" class="text-base sm:text-lg font-bold">Where to watch</h2>
        <p class="mt-1 text-sm text-neutral-400">{intro}</p>
        <div class="mt-3 flex flex-wrap gap-2">
          {" ".join(buttons)}
        </div>
        {note}
      </section>"""


def json_ld(row, kind, url):
    data = {
        "@context": "https://schema.org",
        "@type": "TVSeries" if kind == "series" else "Movie",
        "name": row["title"],
        "image": row.get("poster_url") or FALLBACK_POSTER,
    }
    if row.get("year"):
        data["dateCreated"] = row["year"]
    if row.get("description"):
        data["description"] = row["description"]
    if row.get("genre"):
        data["genre"] = row["genre"]
    if row.get("country"):
        data["countryOfOrigin"] = [{"@type": "Country", "name": c.strip()} for c in row["country"].split(",") if c.strip()]
    if row.get("cast"):
        data["actor"] = [{"@type": "Person", "name": n.strip()} for n in row["cast"].split(",") if n.strip()]
    vid = row.get("trailer_youtube_id", "")
    if YOUTUBE_ID.match(vid):
        data["trailer"] = {"@type": "VideoObject", "name": f'{row["title"]} - Official Trailer',
                           "embedUrl": f"https://www.youtube.com/embed/{vid}",
                           "thumbnailUrl": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg"}
    if url:
        data["url"] = url
    return json.dumps(data, ensure_ascii=False, indent=2).replace("</", "<\\/")


def render_page(template, row, kind):
    slug = row["_slug"]
    url = f"{SITE_URL}/{slug}.html" if SITE_URL else ""
    chip = "text-xs px-2.5 py-1 rounded-full bg-neutral-800 text-neutral-300"
    values = {
        "TITLE": esc(row["title"]),
        "DESCRIPTION": esc(row.get("description") or f'{row["title"]}: official trailer, cast and where to watch.'),
        "CAST": esc(row.get("cast")),
        "GENRE": esc(row.get("genre")),
        "YEAR": esc(row.get("year")),
        "POSTER_URL": esc(row.get("poster_url") or FALLBACK_POSTER),
        "DESCRIPTION_TEXT": esc(row.get("description")) or '<span class="text-neutral-500">Synopsis coming soon.</span>',
        "CAST_TEXT": esc(row.get("cast")) or '<span class="text-neutral-500">Cast details coming soon.</span>',
        "GENRE_HTML": f'<span class="{chip}">{esc(row["genre"])}</span>' if row.get("genre") else "",
        "TYPE_HTML": (f'<span class="px-1.5 border border-neutral-600 rounded text-xs">'
                      f'{esc(row.get("category")) or ("Series" if kind == "series" else "Movie")}</span>'
                      if (kind or row.get("category")) else ""),
        "COUNTRY_HTML": (f'<span class="inline-flex items-center gap-1"><svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a14 14 0 010 18M12 3a14 14 0 000 18"/></svg>{esc(row["country"])}</span>'
                         if row.get("country") else ""),
        "OG_TYPE": "video.tv_show" if kind == "series" else "video.movie",
        "CANONICAL_TAG": f'<link rel="canonical" href="{esc(url)}" />' if url else "",
        "OG_URL_TAG": f'<meta property="og:url" content="{esc(url)}" />' if url else "",
        "JSONLD": json_ld(row, kind, url),
        "PLAYER_HTML": player_html(row),
        "WATCH_HTML": watch_html(row),
    }
    # One pass, so text inside a description can never be mistaken for a placeholder.
    return re.sub(r"\{\{([A-Z_]+)\}\}", lambda m: values.get(m.group(1), m.group(0)), template)


def wide_image(row, size="w780"):
    """Landscape backdrop from TMDB if we have one, else the poster."""
    b = row.get("backdrop_url", "")
    if b.startswith("http"):
        return b.replace("/w780/", f"/{size}/"), True
    return row.get("poster_url") or FALLBACK_POSTER, False


def popularity(row):
    try:
        return float(row.get("popularity") or 0)
    except ValueError:
        return 0.0


def year_of(row):
    y = row.get("year", "")
    return int(y) if y.isdigit() else 0


def row_card(row):
    """Wide landscape card used in homepage rows."""
    slug = row["_slug"]
    title = esc(row.get("title") or slug)
    img, is_wide = wide_image(row)
    fit = "object-cover" if is_wide else "object-cover object-[50%_20%]"
    label = row.get("category") or ("Series" if row.get("_kind") == "series" else "Movie" if row.get("_kind") else "")
    badge = (f'<span class="absolute top-2 left-2 text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded bg-black/70 backdrop-blur">{esc(label)}</span>'
             if label else "")
    year = (f'<span class="absolute bottom-2 right-2 text-[11px] font-semibold px-1.5 py-0.5 rounded bg-black/70">{esc(row["year"])}</span>'
            if row.get("year") else "")
    trailer = ('<span class="absolute bottom-2 left-2 inline-flex items-center gap-1 text-[11px] font-semibold px-1.5 py-0.5 rounded bg-red-600/90">'
               '<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>Trailer</span>'
               if YOUTUBE_ID.match(row.get("trailer_youtube_id", "")) else "")
    return f"""          <a href="{slug}.html" class="snap-start shrink-0 w-[72vw] sm:w-[44vw] md:w-[31vw] lg:w-[23.5vw] xl:w-[19vw] 2xl:w-[300px] group">
            <div class="relative aspect-video rounded-md overflow-hidden bg-zinc-800 ring-1 ring-white/5 group-hover:ring-2 group-hover:ring-red-600 transition">
              <img src="{esc(img)}" alt="{title}" loading="lazy" onerror="this.onerror=null;this.src='{FALLBACK_POSTER}';" class="w-full h-full {fit} group-hover:scale-105 transition duration-500">
              <div class="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent"></div>
              {badge}{trailer}{year}
            </div>
            <h3 class="mt-2 text-sm font-semibold text-zinc-100 truncate group-hover:text-white">{title}</h3>
          </a>"""


def seo_head(title, description, path, image="", og_type="website"):
    """Canonical link plus Open Graph and Twitter tags. Canonical/og:url need SITE_URL."""
    url = f"{SITE_URL}/{path}" if SITE_URL else ""
    tags = []
    if url:
        tags.append(f'<link rel="canonical" href="{esc(url)}">')
        tags.append(f'<meta property="og:url" content="{esc(url)}">')
    if GOOGLE_VERIFICATION and path == "":
        tags.append(f'<meta name="google-site-verification" content="{esc(GOOGLE_VERIFICATION)}">')
    tags += [
        f'<meta property="og:site_name" content="{esc(SITE_NAME)}">',
        f'<meta property="og:type" content="{og_type}">',
        f'<meta property="og:title" content="{title}">',
        f'<meta property="og:description" content="{esc(description)}">',
        f'<meta name="twitter:card" content="{"summary_large_image" if image else "summary"}">',
        f'<meta name="twitter:title" content="{title}">',
        f'<meta name="twitter:description" content="{esc(description)}">',
    ]
    if image:
        tags.append(f'<meta property="og:image" content="{esc(image)}">')
        tags.append(f'<meta name="twitter:image" content="{esc(image)}">')
    return "\n  ".join(tags)


def shell(title, body, description="", overlay=False, active="", root="", path="", image="", extra_head=""):
    """Page wrapper for the homepage, Explore, guides and info pages.
    root is "../" for pages inside a subfolder (guides/), path is the page's address for canonical links."""
    def link(name, href, key, extra=""):
        on = "text-white font-semibold" if key == active else "text-zinc-300 hover:text-white"
        return f'<a href="{root}{href}" class="{on} transition {extra}">{name}</a>'
    header_bg = "bg-gradient-to-b from-black/90 to-transparent" if overlay else "bg-black/95 border-b border-white/10"
    return f"""<!DOCTYPE html>
<html lang="en" class="bg-black">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{esc(description)}">
  <meta name="theme-color" content="#000000">
  {seo_head(title, description, path, image)}
  {extra_head}
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    .no-scrollbar::-webkit-scrollbar {{ display:none; }}
    .no-scrollbar {{ -ms-overflow-style:none; scrollbar-width:none; }}
    .line-clamp-3 {{ display:-webkit-box; -webkit-line-clamp:3; -webkit-box-orient:vertical; overflow:hidden; }}
  </style>
</head>
<body class="bg-black text-zinc-100 min-h-screen flex flex-col">
  <header id="site-header" class="{'fixed' if overlay else 'sticky'} top-0 inset-x-0 z-50 transition-colors duration-300 {header_bg}">
    <div class="max-w-[1800px] mx-auto px-4 sm:px-8 h-16 flex items-center gap-4 sm:gap-8">
      <a href="{root}index.html" class="text-xl sm:text-2xl font-black tracking-tight shrink-0">Drama<span class="text-red-600">Net</span></a>
      <nav class="flex items-center gap-3 sm:gap-6 text-sm" aria-label="Main navigation">
        {link("Home", "index.html", "home", "hidden sm:inline")}
        {link("Explore", "explore.html", "explore")}
        {link("Movies", "explore.html?type=movie", "movie")}
        {link("Series", "explore.html?type=series", "series")}
        {link("Guides", "guides/index.html", "guides", "hidden md:inline")}
      </nav>
      <form action="{root}explore.html" method="get" class="ml-auto" role="search">
        <label class="relative flex items-center">
          <span class="sr-only">Search</span>
          <svg class="absolute left-2.5 w-4 h-4 text-zinc-400 pointer-events-none" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path stroke-linecap="round" d="M20 20l-3.5-3.5"/></svg>
          <input name="q" type="search" placeholder="Search" autocomplete="off"
                 class="w-9 focus:w-44 sm:w-48 sm:focus:w-64 transition-all pl-8 pr-2 py-1.5 rounded bg-black/50 ring-1 ring-white/20 focus:ring-white/60 focus:outline-none text-sm placeholder:text-zinc-400">
        </label>
      </form>
    </div>
  </header>
{body}
  <footer class="mt-auto border-t border-white/10 py-8 px-4 text-center text-xs text-zinc-500 space-y-2">
    <nav class="flex justify-center gap-4" aria-label="Footer">
      <a href="{root}guides/index.html" class="hover:text-zinc-300">Guides</a>
      <a href="{root}dmca.html" class="hover:text-zinc-300">DMCA</a>
      <a href="{root}privacy.html" class="hover:text-zinc-300">Privacy</a>
      <a href="{root}terms.html" class="hover:text-zinc-300">Terms</a>
      <a href="{root}contact.html" class="hover:text-zinc-300">Contact</a>
    </nav>
    <p>&copy; {date.today().year} {SITE_NAME}. We don't host any videos. Trailers play from YouTube; title data and images from TMDB.</p>
  </footer>
{HEADER_SCRIPT if overlay else ""}
  <!-- ============================================================
       MONETAG / PROPELLERADS — GLOBAL SCRIPTS (homepage, Explore, info pages)
       Paste your Monetag / PropellerAds code below
       ============================================================ -->
  <script type="text/javascript">
    /* PASTE MONETAG / PROPELLERADS CODE HERE */
  </script>
  <!-- ============ END MONETAG / PROPELLERADS ============ -->
</body>
</html>
"""


HEADER_SCRIPT = """
  <script>
    (function () {
      var h = document.getElementById('site-header');
      function onScroll() {
        var solid = window.scrollY > 40;
        h.classList.toggle('bg-black', solid);
        h.classList.toggle('bg-gradient-to-b', !solid);
      }
      window.addEventListener('scroll', onScroll, { passive: true });
      onScroll();
    })();
  </script>"""


HOME_SCRIPT = """
  <script>
    (function () {
      // ---- Hero slideshow: crossfade, arrows, dots, swipe, autoplay ----
      var slides = Array.prototype.slice.call(document.querySelectorAll('.hero-slide'));
      var dots = Array.prototype.slice.call(document.querySelectorAll('.hero-dot'));
      var hero = document.getElementById('hero');
      var current = 0, timer = null, DELAY = 7000;
      function show(i) {
        if (!slides.length) return;
        current = (i + slides.length) % slides.length;
        slides.forEach(function (s, n) {
          var on = n === current;
          s.classList.toggle('opacity-100', on);
          s.classList.toggle('opacity-0', !on);
          s.classList.toggle('pointer-events-none', !on);
          s.setAttribute('aria-hidden', String(!on));
          var img = s.querySelector('img');
          if (img) img.classList.toggle('scale-105', !on);
        });
        dots.forEach(function (d, n) {
          d.classList.toggle('bg-white', n === current);
          d.classList.toggle('w-6', n === current);
          d.classList.toggle('bg-white/40', n !== current);
          d.setAttribute('aria-current', n === current ? 'true' : 'false');
        });
      }
      function play() { stop(); if (slides.length > 1) timer = setInterval(function () { show(current + 1); }, DELAY); }
      function stop() { if (timer) clearInterval(timer); timer = null; }
      if (hero) {
        document.getElementById('hero-prev').addEventListener('click', function () { show(current - 1); play(); });
        document.getElementById('hero-next').addEventListener('click', function () { show(current + 1); play(); });
        dots.forEach(function (d, n) { d.addEventListener('click', function () { show(n); play(); }); });
        hero.addEventListener('mouseenter', stop);
        hero.addEventListener('mouseleave', play);
        var startX = null;
        hero.addEventListener('touchstart', function (e) { startX = e.touches[0].clientX; }, { passive: true });
        hero.addEventListener('touchend', function (e) {
          if (startX === null) return;
          var dx = e.changedTouches[0].clientX - startX;
          if (Math.abs(dx) > 40) { show(current + (dx < 0 ? 1 : -1)); play(); }
          startX = null;
        });
        document.addEventListener('visibilitychange', function () { document.hidden ? stop() : play(); });
        show(0); play();
      }

      // ---- Row arrows ----
      document.querySelectorAll('[data-row]').forEach(function (row) {
        var track = row.querySelector('.row-track');
        row.querySelectorAll('.row-btn').forEach(function (btn) {
          btn.addEventListener('click', function () {
            var dir = btn.dataset.dir === 'next' ? 1 : -1;
            track.scrollBy({ left: dir * track.clientWidth * 0.9, behavior: 'smooth' });
          });
        });
      });
    })();
  </script>"""


def hero_slide(row, index):
    img, _ = wide_image(row, "w1280")
    title = esc(row["title"])
    meta = " &middot; ".join(esc(p) for p in (row.get("year"), (row.get("country") or "").split(",")[0], row.get("genre")) if p)
    desc = row.get("description") or ""
    desc_html = f'<p class="mt-4 max-w-xl text-sm sm:text-base text-zinc-200 line-clamp-3 drop-shadow">{esc(desc)}</p>' if desc else ""
    has_trailer = YOUTUBE_ID.match(row.get("trailer_youtube_id", ""))
    play_btn = (f'<a href="{row["_slug"]}.html#player" tabindex="{0 if index == 0 else -1}" class="inline-flex items-center gap-2 px-5 sm:px-7 py-2.5 rounded bg-white text-black font-bold text-sm sm:text-base hover:bg-white/80 transition">'
                '<svg class="w-5 h-5" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>Play Trailer</a>') if has_trailer else ""
    chip = (f'<span class="inline-block mb-3 text-[11px] font-bold uppercase tracking-widest px-2 py-1 rounded bg-red-600">{esc(row["category"])}</span>'
            if row.get("category") else "")
    return f"""      <div class="hero-slide absolute inset-0 transition-opacity duration-1000 ease-in-out {'opacity-100' if index == 0 else 'opacity-0 pointer-events-none'}" aria-hidden="{'false' if index == 0 else 'true'}" role="group" aria-roledescription="slide" aria-label="{index + 1}">
        <img src="{esc(img)}" alt="" {'fetchpriority="high"' if index == 0 else 'loading="lazy"'} class="absolute inset-0 w-full h-full object-cover object-[50%_25%] transition-transform duration-[7000ms] ease-out {'' if index == 0 else 'scale-105'}">
        <div class="absolute inset-0 bg-gradient-to-r from-black via-black/60 sm:via-black/40 to-transparent"></div>
        <div class="absolute inset-x-0 bottom-0 h-2/3 bg-gradient-to-t from-black via-black/50 to-transparent"></div>
        <div class="absolute inset-x-0 bottom-0 px-4 sm:px-8 lg:px-12 pb-16 sm:pb-24 max-w-[1800px] mx-auto">
          {chip}
          <h2 class="text-3xl sm:text-5xl lg:text-6xl font-black tracking-tight leading-none max-w-3xl drop-shadow-lg">{title}</h2>
          <p class="mt-3 text-sm sm:text-base text-zinc-300 font-medium">{meta}</p>
          {desc_html}
          <div class="mt-6 flex flex-wrap gap-3">
            {play_btn}
            <a href="{row["_slug"]}.html" tabindex="{0 if index == 0 else -1}" class="inline-flex items-center gap-2 px-5 sm:px-7 py-2.5 rounded bg-zinc-500/50 backdrop-blur text-white font-bold text-sm sm:text-base hover:bg-zinc-500/70 transition">
              <svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path stroke-linecap="round" d="M12 11v5M12 8h.01"/></svg>More Info</a>
          </div>
        </div>
      </div>"""


def build_hero(featured):
    if not featured:
        return ""
    slides = "\n".join(hero_slide(r, i) for i, r in enumerate(featured))
    dots = "".join(f'<button type="button" class="hero-dot h-1.5 w-1.5 rounded-full bg-white/40 transition-all" aria-label="Show slide {i + 1}"></button>'
                   for i in range(len(featured)))
    arrow = ('<button id="hero-{id}" type="button" aria-label="{label}" class="hidden sm:flex absolute top-1/2 -translate-y-1/2 {side} z-10 w-11 h-11 '
             'items-center justify-center rounded-full bg-black/40 hover:bg-black/70 ring-1 ring-white/20 transition">'
             '<svg class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="{d}"/></svg></button>')
    return f"""  <section id="hero" class="relative w-full h-[78vh] min-h-[460px] max-h-[860px] overflow-hidden bg-black" aria-roledescription="carousel" aria-label="Featured titles">
{slides}
    {arrow.format(id="prev", label="Previous", side="left-4", d="M15 5l-7 7 7 7")}
    {arrow.format(id="next", label="Next", side="right-4", d="M9 5l7 7-7 7")}
    <div class="absolute bottom-6 sm:bottom-10 right-4 sm:right-8 lg:right-12 z-10 flex items-center gap-2">{dots}</div>
  </section>"""


def build_row(name, rows, link):
    cards = "\n".join(row_card(r) for r in rows)
    chevron = ('<button type="button" data-dir="{dir}" aria-label="{label}" class="row-btn hidden md:flex absolute {side} top-0 bottom-8 z-10 w-12 items-center justify-center '
               'bg-black/60 opacity-0 group-hover/row:opacity-100 hover:bg-black/80 transition">'
               '<svg class="w-7 h-7" fill="none" stroke="currentColor" stroke-width="2.5" viewBox="0 0 24 24" aria-hidden="true"><path stroke-linecap="round" stroke-linejoin="round" d="{d}"/></svg></button>')
    return f"""    <section class="mt-8 sm:mt-10" data-row>
      <div class="px-4 sm:px-8 lg:px-12 flex items-baseline gap-3">
        <h2 class="text-lg sm:text-2xl font-bold">{esc(name)}</h2>
        <a href="{esc(link)}" class="text-sm font-semibold text-zinc-400 hover:text-white transition">See all &rsaquo;</a>
      </div>
      <div class="relative group/row mt-3">
        {chevron.format(dir="prev", label="Scroll left", side="left-0", d="M15 5l-7 7 7 7")}
        <div class="row-track flex gap-3 overflow-x-auto no-scrollbar snap-x scroll-px-4 sm:scroll-px-8 lg:scroll-px-12 px-4 sm:px-8 lg:px-12 pb-2">
{cards}
        </div>
        {chevron.format(dir="next", label="Scroll right", side="right-0", d="M9 5l7 7-7 7")}
      </div>
    </section>"""


ROW_SIZE = 20


def guides_row(cards):
    """Homepage row linking to the guides."""
    items = "\n".join(f"""          <a href="{path}" class="snap-start shrink-0 w-[72vw] sm:w-[44vw] md:w-[31vw] lg:w-[23.5vw] xl:w-[19vw] 2xl:w-[300px] group">
            <div class="relative aspect-video rounded-md overflow-hidden bg-zinc-800 ring-1 ring-white/5 group-hover:ring-2 group-hover:ring-red-600 transition">
              {f'<img src="{esc(img)}" alt="" loading="lazy" class="w-full h-full object-cover group-hover:scale-105 transition duration-500">' if img else ''}
              <div class="absolute inset-0 bg-gradient-to-t from-black via-black/40 to-transparent"></div>
              <span class="absolute top-2 left-2 text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded bg-red-600">Guide</span>
              <h3 class="absolute bottom-2 left-3 right-3 text-sm sm:text-base font-bold leading-snug">{h1}</h3>
            </div>
          </a>""" for path, h1, desc, img in cards)
    return f"""    <section class="mt-8 sm:mt-10">
      <div class="px-4 sm:px-8 lg:px-12 flex items-baseline gap-3">
        <h2 class="text-lg sm:text-2xl font-bold">Guides: Where to Watch &amp; What&rsquo;s Next</h2>
        <a href="guides/index.html" class="text-sm font-semibold text-zinc-400 hover:text-white transition">See all &rsaquo;</a>
      </div>
      <div class="row-track flex gap-3 overflow-x-auto no-scrollbar snap-x px-4 sm:px-8 lg:px-12 pb-2 mt-3">
{items}
      </div>
    </section>"""


def build_home(rows, guide_cards=()):
    by_pop = sorted(rows, key=popularity, reverse=True)
    # Hero and "Trending Now" focus on Asian titles; Western shows get their own row.
    asian = [r for r in by_pop if r.get("category") not in ("Western", "Other", "Variety", "")]
    newest_year = max((year_of(r) for r in rows), default=0)
    recent = [r for r in (asian or by_pop) if year_of(r) >= newest_year - 1]

    # Hero: popular recent titles that have a wide image (and ideally a trailer).
    wide = [r for r in recent if wide_image(r)[1]]
    featured = [r for r in wide if YOUTUBE_ID.match(r.get("trailer_youtube_id", ""))][:6] or wide[:6]
    if not featured:
        featured = [r for r in by_pop if wide_image(r)[1]][:6]
    featured_ids = {r["_slug"] for r in featured}

    def cat(*names):
        return [r for r in by_pop if r.get("category") in names]

    sections = [
        ("Trending Now", asian or by_pop, "explore.html?sort=popular"),
        ("New Releases", [r for r in recent if r["_slug"] not in featured_ids] or recent, "explore.html?sort=newest"),
        ("Top K-Dramas", cat("K-Drama"), "explore.html?cat=K-Drama"),
        ("Top C-Dramas", cat("C-Drama"), "explore.html?cat=C-Drama"),
        ("Korean Movies", cat("K-Movie"), "explore.html?cat=K-Movie"),
        ("Anime", cat("Anime", "Animation"), "explore.html?cat=Anime"),
        ("Thai Dramas", cat("Thai Drama"), "explore.html?cat=Thai+Drama"),
        ("Korean Variety Shows", cat("K-Variety"), "explore.html?cat=K-Variety"),
        ("Turkish Dramas", cat("Turkish Drama"), "explore.html?cat=Turkish+Drama"),
        ("Hollywood &amp; Western", cat("Western"), "explore.html?cat=Western"),
    ]
    blocks = [build_row(name, items[:ROW_SIZE], link) for name, items, link in sections if len(items) >= 4]
    if guide_cards:
        blocks.insert(min(4, len(blocks)), guides_row(guide_cards))
    # Put one ad slot between the 2nd and 3rd rows.
    if len(blocks) > 2:
        blocks.insert(2, '    <!-- AD_SLOT_HOME_MID -->')
    hero = build_hero(featured)
    body = f"""
  <main class="flex-1 {'' if hero else 'pt-16'}">
{hero}
    <div class="relative z-10 {'-mt-10 sm:-mt-16' if hero else ''} pb-12">
    <!-- AD_SLOT_TOP -->
{chr(10).join(blocks)}
    </div>
  </main>
{HOME_SCRIPT}
"""
    return shell(f"{SITE_NAME} - Trailers, Cast &amp; Where to Watch K-Dramas, C-Dramas, Anime &amp; More",
                 body, "Browse K-dramas, C-dramas, anime and movies: official trailers, cast and where to watch them legally.",
                 overlay=bool(hero), active="home", path="",
                 image=wide_image(featured[0], "w1280")[0] if featured else "")


EXPLORE_SCRIPT = """
  <script>
    (function () {
      var DATA = JSON.parse(document.getElementById('catalog-data').textContent);
      var PAGE = 48, shown = PAGE;
      var params = new URLSearchParams(location.search);
      var state = {
        type: params.get('type') || '',
        cat: params.get('cat') || '',
        country: params.get('country') || '',
        sort: params.get('sort') || 'popular',
        q: params.get('q') || ''
      };
      var grid = document.getElementById('grid');
      var count = document.getElementById('count');
      var heading = document.getElementById('heading');
      var more = document.getElementById('load-more');
      var empty = document.getElementById('empty');
      var input = document.getElementById('q');
      input.value = state.q;

      function tally(key, split) {
        var c = {};
        DATA.forEach(function (d) {
          (split ? (d[key] || '').split(',') : [d[key]]).forEach(function (v) {
            v = (v || '').trim(); if (v) c[v] = (c[v] || 0) + 1;
          });
        });
        return Object.keys(c).sort(function (a, b) { return c[b] - c[a]; });
      }
      var groups = {
        type: [['', 'All'], ['series', 'Series'], ['movie', 'Movies']],
        cat: [['', 'All Categories']].concat(tally('c').map(function (v) { return [v, v]; })),
        country: [['', 'All Regions']].concat(tally('n', true).slice(0, 14).map(function (v) { return [v, v]; })),
        sort: [['popular', 'Popular'], ['newest', 'Newest'], ['az', 'A\\u2013Z']]
      };
      Object.keys(groups).forEach(function (key) {
        var box = document.querySelector('[data-pills="' + key + '"]');
        groups[key].forEach(function (pair) {
          var b = document.createElement('button');
          b.type = 'button';
          b.className = 'pill shrink-0 px-3.5 py-1.5 rounded-full text-sm font-medium ring-1 transition';
          b.dataset.key = key; b.dataset.val = pair[0];
          b.textContent = pair[1];
          b.addEventListener('click', function () { state[key] = pair[0]; update(true); });
          box.appendChild(b);
        });
      });

      function card(d) {
        var label = d.c || (d.k === 'series' ? 'Series' : d.k === 'movie' ? 'Movie' : '');
        var a = document.createElement('a');
        a.href = d.s + '.html';
        a.className = 'group block';
        a.innerHTML =
          '<div class="relative aspect-video rounded-md overflow-hidden bg-zinc-800 ring-1 ring-white/5 group-hover:ring-2 group-hover:ring-red-600 transition">' +
            '<img loading="lazy" alt="" class="w-full h-full object-cover ' + (d.w ? '' : 'object-[50%_20%]') + ' group-hover:scale-105 transition duration-500">' +
            '<div class="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent"></div>' +
            (label ? '<span class="lbl absolute top-2 left-2 text-[10px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded bg-black/70"></span>' : '') +
            (d.v ? '<span class="absolute bottom-2 left-2 text-[11px] font-semibold px-1.5 py-0.5 rounded bg-red-600/90">&#9654; Trailer</span>' : '') +
            (d.y ? '<span class="yr absolute bottom-2 right-2 text-[11px] font-semibold px-1.5 py-0.5 rounded bg-black/70"></span>' : '') +
          '</div>' +
          '<h3 class="mt-2 text-sm font-semibold truncate"></h3>' +
          '<p class="text-xs text-zinc-500 truncate"></p>';
        var img = a.querySelector('img');
        img.src = d.b; img.alt = d.t;
        img.onerror = function () { this.onerror = null; this.src = '""" + FALLBACK_POSTER + """'; };
        if (label) a.querySelector('.lbl').textContent = label;
        if (d.y) a.querySelector('.yr').textContent = d.y;
        a.querySelector('h3').textContent = d.t;
        a.querySelector('p').textContent = [d.n.split(',')[0], d.g].filter(Boolean).join(' \\u00b7 ');
        return a;
      }

      function update(reset) {
        if (reset) shown = PAGE;
        var words = state.q.toLowerCase().trim().split(/\\s+/).filter(Boolean);
        var list = DATA.filter(function (d) {
          if (state.type && d.k !== state.type) return false;
          if (state.cat && d.c !== state.cat && !(state.cat === 'Anime' && d.c === 'Animation')) return false;
          if (state.country && (',' + d.n.replace(/,\\s*/g, ',') + ',').indexOf(',' + state.country + ',') === -1) return false;
          return words.every(function (w) { return d.q.indexOf(w) !== -1; });
        });
        list.sort(state.sort === 'newest' ? function (a, b) { return (b.y || 0) - (a.y || 0) || b.p - a.p; }
                : state.sort === 'az' ? function (a, b) { return a.t.localeCompare(b.t); }
                : function (a, b) { return b.p - a.p; });
        grid.innerHTML = '';
        var frag = document.createDocumentFragment();
        list.slice(0, shown).forEach(function (d) { frag.appendChild(card(d)); });
        grid.appendChild(frag);
        count.textContent = list.length + (list.length === 1 ? ' title' : ' titles');
        more.hidden = list.length <= shown;
        empty.hidden = list.length > 0;
        var parts = [state.cat, state.country, state.type === 'movie' ? 'Movies' : state.type === 'series' ? 'Series' : ''].filter(Boolean);
        heading.textContent = state.q ? 'Results for \\u201c' + state.q.trim() + '\\u201d' : (parts.join(' \\u00b7 ') || 'Explore');
        document.querySelectorAll('.pill').forEach(function (b) {
          var on = state[b.dataset.key] === b.dataset.val;
          b.classList.toggle('bg-white', on); b.classList.toggle('text-black', on); b.classList.toggle('ring-white', on);
          b.classList.toggle('bg-zinc-900', !on); b.classList.toggle('text-zinc-200', !on); b.classList.toggle('ring-white/15', !on);
          b.classList.toggle('hover:bg-zinc-800', !on);
        });
        var p = new URLSearchParams();
        Object.keys(state).forEach(function (k) { if (state[k] && !(k === 'sort' && state[k] === 'popular')) p.set(k, state[k]); });
        history.replaceState(null, '', location.pathname + (p.toString() ? '?' + p : ''));
        document.querySelectorAll('header nav a').forEach(function (a) {
          var key = a.getAttribute('href');
          var on = (key === 'explore.html' && !state.type) || key === 'explore.html?type=' + state.type;
          a.classList.toggle('text-white', on); a.classList.toggle('font-semibold', on); a.classList.toggle('text-zinc-300', !on);
        });
      }

      var t;
      input.addEventListener('input', function () { clearTimeout(t); t = setTimeout(function () { state.q = input.value; update(true); }, 150); });
      more.addEventListener('click', function () { shown += PAGE; update(false); });
      update(true);
    })();
  </script>"""


def build_explore(rows):
    data = []
    for r in rows:
        img, is_wide = wide_image(r)
        data.append({
            "s": r["_slug"], "t": r.get("title", ""), "y": year_of(r) or "", "c": r.get("category", ""),
            "n": r.get("country", ""), "g": r.get("genre", ""), "k": r.get("_kind", ""), "p": round(popularity(r), 1),
            "b": img, "w": 1 if is_wide else 0, "v": 1 if YOUTUBE_ID.match(r.get("trailer_youtube_id", "")) else 0,
            "q": " ".join([r.get("title", ""), r.get("cast", ""), r.get("genre", ""), r.get("country", ""),
                           r.get("category", ""), r.get("year", "")]).lower(),
        })
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    pills = lambda key, label: (f'<div class="flex items-center gap-2 overflow-x-auto no-scrollbar sm:flex-wrap -mx-4 px-4 sm:mx-0 sm:px-0" '
                                f'role="group" aria-label="{label}" data-pills="{key}"></div>')
    body = f"""
  <main class="flex-1 w-full max-w-[1800px] mx-auto px-4 sm:px-8 lg:px-12 py-6">
    <!-- AD_SLOT_TOP -->
    <div class="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3">
      <div>
        <h1 id="heading" class="text-2xl sm:text-3xl font-bold">Explore</h1>
        <p id="count" class="text-sm text-zinc-400 mt-1"></p>
      </div>
      <label class="relative w-full sm:w-80">
        <span class="sr-only">Search titles</span>
        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path stroke-linecap="round" d="M20 20l-3.5-3.5"/></svg>
        <input id="q" type="search" placeholder="Search titles, cast, genre, country..." autocomplete="off"
               class="w-full pl-9 pr-3 py-2 rounded-md bg-zinc-900 ring-1 ring-white/10 focus:ring-red-600 focus:outline-none text-sm placeholder:text-zinc-500">
      </label>
    </div>
    <div class="mt-5 space-y-2.5">
      {pills("type", "Type")}
      {pills("cat", "Category")}
      {pills("country", "Region")}
      {pills("sort", "Sort by")}
    </div>
    <div id="grid" class="mt-6 grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-5 gap-x-3 gap-y-5"></div>
    <p id="empty" hidden class="py-16 text-center text-zinc-400">No titles match these filters.</p>
    <div class="mt-8 flex justify-center">
      <button id="load-more" type="button" hidden class="px-6 py-2 rounded bg-zinc-800 hover:bg-zinc-700 text-sm font-medium">Load more</button>
    </div>
  </main>
  <script id="catalog-data" type="application/json">{blob}</script>
{EXPLORE_SCRIPT}
"""
    return shell(f"Explore | {SITE_NAME}", body, "Filter K-dramas, C-dramas, anime and movies by type, category and country.",
                 active="explore", path="explore.html")


def info_page(title, paragraphs, path=""):
    inner = "\n".join(f"      <p>{p}</p>" for p in paragraphs)
    body = f"""
  <main class="flex-1 max-w-3xl w-full mx-auto px-4 py-10">
    <h1 class="text-2xl sm:text-3xl font-bold mb-6">{title}</h1>
    <div class="space-y-4 text-sm sm:text-base text-zinc-300 leading-relaxed">
{inner}
    </div>
  </main>
"""
    return shell(f"{title} | {SITE_NAME}", body, path=path)


def write_info_pages():
    mail = f'<a class="underline" href="mailto:{esc(CONTACT_EMAIL)}">{esc(CONTACT_EMAIL)}</a>'
    pages = {
        "privacy.html": ("Privacy Policy", [
            f"{SITE_NAME} does not ask you to create an account and does not collect personal information directly.",
            "We show ads from third-party ad networks. These networks, and YouTube when you play a trailer, may use cookies "
            "or similar technology to show and measure ads. You can limit this in your browser's privacy settings.",
            f"Questions about privacy: {mail}.",
        ]),
        "terms.html": ("Terms of Use", [
            f"{SITE_NAME} is a guide to movies and series. We do not host, upload or stream any films or episodes.",
            "Trailers are embedded from the official YouTube channels that published them. "
            "\"Where to watch\" links send you to licensed services, whose own terms apply.",
            "Title information comes from TMDB. This product uses the TMDB API but is not endorsed or certified by TMDB.",
        ]),
        "dmca.html": ("DMCA / Copyright", [
            f"{SITE_NAME} does not host video files. If you believe something on this site infringes your rights, "
            f"email {mail} with the page address and details of the work, and we will review and remove it promptly.",
        ]),
        "contact.html": ("Contact", [f"Email us at {mail}."]),
        "404.html": ("Page not found", ['That page doesn\'t exist. <a class="underline" href="index.html">Go back to the homepage</a>.']),
    }
    for name, (title, paras) in pages.items():
        (OUTPUT_DIR / name).write_text(info_page(title, paras, "" if name == "404.html" else name), encoding="utf-8")


def write_seo_files(slugs, extra_paths=()):
    robots = "User-agent: *\nAllow: /\n"
    if SITE_URL:
        robots += f"Sitemap: {SITE_URL}/sitemap.xml\n"
        urls = [f"{SITE_URL}/", f"{SITE_URL}/explore.html"] + [f"{SITE_URL}/{p}" for p in extra_paths] + [f"{SITE_URL}/{s}.html" for s in slugs]
        body = "\n".join(f"  <url><loc>{esc(u)}</loc></url>" for u in urls)
        (OUTPUT_DIR / "sitemap.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{body}\n</urlset>\n', encoding="utf-8")
    (OUTPUT_DIR / "robots.txt").write_text(robots, encoding="utf-8")
    (OUTPUT_DIR / ".nojekyll").write_text("", encoding="utf-8")  # GitHub Pages: serve files as-is


def main():
    template = read_template(TEMPLATE_FILE)
    rows = read_content()

    for token in ("{{PLAYER_HTML}}", "{{WATCH_HTML}}", "{{TITLE}}"):
        if token not in template:
            print(f"WARNING: template.html has no {token} placeholder.")

    # Start from a clean folder so deleted titles don't linger online.
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR, ignore_errors=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUTPUT_DIR.glob("*.html"):
        old.unlink(missing_ok=True)

    reserved = {"index", "explore", "privacy", "terms", "dmca", "contact", "404"}
    kept, used = [], set()
    skipped = 0
    for line_no, row in enumerate(rows, start=2):
        slug = clean_slug(row.get("slug") or row.get("title", ""))
        if not slug or not row.get("title"):
            print(f"SKIP line {line_no}: no title or slug.")
            skipped += 1
            continue
        if slug in reserved:
            slug = f"{slug}-title"
        if slug in used:
            print(f"SKIP line {line_no}: duplicate slug '{slug}'.")
            skipped += 1
            continue
        used.add(slug)
        row["_slug"] = slug
        kept.append(row)

    stats = {"movie": 0, "series": 0, "": 0, "trailer": 0}
    written = []
    for row in kept:
        kind = guess_type(row)
        row["_kind"] = kind
        try:
            (OUTPUT_DIR / f'{row["_slug"]}.html').write_text(render_page(template, row, kind), encoding="utf-8")
        except OSError as exc:
            print(f'SKIP {row["_slug"]}: could not write ({exc}).')
            skipped += 1
            continue
        stats[kind] += 1
        if YOUTUBE_ID.match(row.get("trailer_youtube_id", "")):
            stats["trailer"] += 1
        written.append(row)

    import guides  # guides.py, next to this script
    guide_paths, guide_cards = guides.build(sys.modules[__name__], written)
    (OUTPUT_DIR / "index.html").write_text(build_home(written, guide_cards), encoding="utf-8")
    (OUTPUT_DIR / "explore.html").write_text(build_explore(written), encoding="utf-8")
    write_info_pages()
    write_seo_files([r["_slug"] for r in written], guide_paths)
    print(f"  Guides: {len(guide_paths) - 1} guide page(s) in site_output/guides/")

    print(f"Done: {len(written)} title page(s) written, {skipped} skipped.")
    print(f"  Movies: {stats['movie']}, Series: {stats['series']}, type unknown: {stats['']}, "
          f"with official trailer: {stats['trailer']}")
    if stats[""] or not stats["trailer"]:
        print("  Tip: run enrich_tmdb.py to sort the rest into Movies/Series and add trailers.")
    if not SITE_URL:
        print("  Tip: set SITE_URL at the top of this file after deploying, then run again for the sitemap.")
    if CONTACT_EMAIL == "contact@example.com":
        print("  Tip: change CONTACT_EMAIL at the top of this file to your own email.")
    print(f"Upload this folder: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
