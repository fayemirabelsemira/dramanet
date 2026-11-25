"""Builds the /guides section of DramaNet (called by generate_site.py).

Every guide is built from real data:
  - catalog.csv (your titles and your own descriptions),
  - guides_data.json (Philippines streaming availability and TMDB "similar" titles; made by guides_data.py).
No TMDB summaries are copied. If guides_data.json is missing, only the guides that don't need it are built.

To add your own "Dramas like ..." guide: add an entry to SIMILAR_INTROS below and the slug to
SIMILAR_SEEDS in guides_data.py, then run guides_data.py and generate_site.py again.
"""

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_FILE = BASE_DIR / "guides_data.json"
MONTH = date.today().strftime("%B %Y")

# Hand-written intros for the "Dramas like ..." guides. Keep them factual.
SIMILAR_INTROS = {
    "queen-of-tears": (
        "K-Dramas Like Queen of Tears",
        "Queen of Tears (tvN, 2024) mixes a marriage on the edge of divorce, a chaebol family at war with itself and a "
        "health scare that changes everything, and it swings from big laughs to real heartbreak. If you finished it "
        "and want more romance with that mix of comedy and melodrama, start with these.",
    ),
    "squid-game-season-3": (
        "Shows Like Squid Game",
        "Squid Game (Netflix, 2021 to 2025) drops hundreds of people in deep debt into deadly versions of children's "
        "games, with a huge cash prize for the last one standing. If you want more survival stakes, dark social "
        "commentary and tense games, these are the next ones to try.",
    ),
    "alchemy-of-souls": (
        "K-Dramas Like Alchemy of Souls",
        "Alchemy of Souls (tvN, 2022) is a fantasy set in the made-up kingdom of Daeho, where young mages train in "
        "secret and a forbidden spell lets a soul move into another body. If you loved its magic, sword fights and "
        "slow-burn romance, these picks are a good next watch.",
    ),
    "lovely-runner": (
        "K-Dramas Like Lovely Runner",
        "Lovely Runner (tvN, 2024) follows a devoted fan who is sent back in time to save the singer she adores, and "
        "turns into a sweet, funny, time-twisting love story. If you want more feel-good romance with a fantasy hook, "
        "here is where to go next.",
    ),
}

CARD_LIMIT = 12


# ---------------------------------------------------------------------------
# Small building blocks
# ---------------------------------------------------------------------------
def load_data():
    if DATA_FILE.is_file():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            pass
    return {"ph": {}, "similar": {}}


def ph_info(data, row):
    return data.get("ph", {}).get(row.get("tmdb_id", ""), {})


def plural(label):
    return label if label.lower() in ("anime", "animation", "k-variety", "variety") else label + "s"


def facts(g, row):
    parts = [row.get("year"), row.get("category") or row.get("country"), row.get("genre")]
    return " &middot; ".join(g.esc(p) for p in parts if p)


def entry(g, row, data, number=None, show_ph=True):
    """One title in a list guide: wide image, title, facts, description and where to watch in the PH."""
    img, wide = g.wide_image(row)
    slug = row["_slug"]
    desc = row.get("description")
    cast = row.get("cast")
    lines = []
    if desc:
        lines.append(f'<p class="mt-2 text-sm text-zinc-300 leading-relaxed">{g.esc(desc)}</p>')
    if cast:
        lines.append(f'<p class="mt-2 text-xs text-zinc-400"><span class="text-zinc-500">Starring:</span> {g.esc(cast)}</p>')
    if show_ph:
        prov = ph_info(data, row).get("providers") or []
        if prov:
            lines.append('<p class="mt-2 text-xs text-zinc-400"><span class="text-zinc-500">Streaming in the Philippines:</span> '
                         f'{g.esc(", ".join(prov))}</p>')
    trailer = g.YOUTUBE_ID.match(row.get("trailer_youtube_id", ""))
    num = f'<span class="text-pink-500 font-black mr-2">{number}.</span>' if number else ""
    return f"""      <li class="flex flex-col sm:flex-row gap-4 py-6 border-b border-white/10">
        <a href="../{slug}.html" class="shrink-0 sm:w-64">
          <div class="relative aspect-video rounded-md overflow-hidden bg-zinc-800 ring-1 ring-white/10">
            <img src="{g.esc(img)}" alt="{g.esc(row['title'])}" loading="lazy" class="w-full h-full object-cover {'' if wide else 'object-[50%_20%]'}">
          </div>
        </a>
        <div class="min-w-0">
          <h2 class="text-lg sm:text-xl font-bold">{num}<a href="../{slug}.html" class="hover:text-pink-500">{g.esc(row['title'])}</a></h2>
          <p class="mt-1 text-xs text-zinc-400">{facts(g, row)}</p>
          {"".join(lines)}
          <a href="../{slug}.html" class="mt-3 inline-flex text-sm font-semibold text-pink-500 hover:text-pink-400">{'Watch the trailer and see where to stream' if trailer else 'See cast and where to stream'} &rsaquo;</a>
        </div>
      </li>"""


def article(g, *, path, title, h1, description, intro_html, content_html, image="", schema=None):
    ld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": h1,
        "description": description,
        "dateModified": date.today().isoformat(),
        "publisher": {"@type": "Organization", "name": g.SITE_NAME},
    }
    if image:
        ld["image"] = image
    if g.SITE_URL:
        ld["mainEntityOfPage"] = f"{g.SITE_URL}/{path}"
    blocks = [ld] + ([schema] if schema else [])
    head = "\n  ".join('<script type="application/ld+json">' + json.dumps(b, ensure_ascii=False).replace("</", "<\\/") + "</script>"
                        for b in blocks)
    body = f"""
  <main class="flex-1 w-full max-w-3xl mx-auto px-4 py-8 sm:py-12">
    <nav class="text-xs text-zinc-500 mb-4" aria-label="Breadcrumb"><a href="../index.html" class="hover:text-zinc-300">Home</a> &rsaquo; <a href="index.html" class="hover:text-zinc-300">Guides</a></nav>
    <h1 class="text-3xl sm:text-4xl font-black tracking-tight leading-tight">{h1}</h1>
    <p class="mt-2 text-xs text-zinc-500">Updated {MONTH}</p>
    <div class="mt-6 space-y-4 text-zinc-300 leading-relaxed">
{intro_html}
    </div>
    <!-- AD_SLOT_GUIDE_TOP -->
{content_html}
    <p class="mt-10 text-xs text-zinc-500 leading-relaxed">Streaming availability changes often and can differ by plan. Availability data by JustWatch via TMDB, checked {MONTH}.
    {g.SITE_NAME} doesn't host any videos; we link to official trailers and licensed services only.</p>
    <p class="mt-6"><a href="index.html" class="text-sm font-semibold text-zinc-300 hover:text-white">&larr; All guides</a></p>
  </main>
"""
    return g.shell(f"{title} | {g.SITE_NAME}", body, description, root="../", path=path, image=image,
                   extra_head=head, active="guides")


# ---------------------------------------------------------------------------
# The guides
# ---------------------------------------------------------------------------
def where_to_watch_ph(g, row, data, related):
    info = ph_info(data, row)
    prov = info.get("providers") or []
    title = row["title"]
    slug = row["_slug"]
    kind = "series" if row.get("_kind") == "series" else "movie"
    services = ", ".join(prov[:-1]) + f" and {prov[-1]}" if len(prov) > 1 else prov[0]
    btn = "inline-flex items-center px-4 py-2 rounded bg-zinc-800 hover:bg-zinc-700 text-sm font-semibold"
    buttons = " ".join(f'<a href="{g.esc(g.provider_link(p, title, info.get("link") or "#"))}" target="_blank" rel="noopener nofollow" class="{btn}">{g.esc(p)}</a>'
                       for p in prov)
    fact_rows = [("Year", row.get("year")), ("Country", row.get("country")), ("Type", row.get("category") or kind.title()),
                 ("Genre", row.get("genre")), ("Starring", row.get("cast"))]
    table = "\n".join(f'<tr class="border-b border-white/10"><th class="py-2 pr-4 text-left font-medium text-zinc-500 w-28">{k}</th><td class="py-2">{g.esc(v)}</td></tr>'
                      for k, v in fact_rows if v)
    about = (f'<h2 class="mt-10 text-xl font-bold">What is {g.esc(title)} about?</h2>'
             f'<p class="mt-3 text-zinc-300 leading-relaxed">{g.esc(row["description"])}</p>') if row.get("description") else ""
    trailer = g.YOUTUBE_ID.match(row.get("trailer_youtube_id", ""))
    more = "\n".join(entry(g, r, data) for r in related[:4])
    content = f"""
    <section class="mt-8 p-5 rounded-lg bg-zinc-900 ring-1 ring-white/10">
      <h2 class="text-lg font-bold">Streaming in the Philippines</h2>
      <div class="mt-3 flex flex-wrap gap-2">{buttons}</div>
      <p class="mt-3 text-xs text-zinc-500">Buttons open each service's own search. You'll need an account with that service.</p>
    </section>
    <table class="mt-8 w-full text-sm">{table}</table>
    {about}
    <h2 class="mt-10 text-xl font-bold">How to watch {g.esc(title)} in the Philippines</h2>
    <ol class="mt-3 list-decimal pl-5 space-y-2 text-zinc-300">
      <li>Pick one of the services above ({g.esc(services)}) and sign in, or create an account.</li>
      <li>Search for <strong>{g.esc(title)}</strong> in the app or on the website.</li>
      <li>Check the plan you're on: some services include it in every plan, others only in certain plans or with ads.</li>
    </ol>
    <p class="mt-6"><a href="../{slug}.html" class="inline-flex items-center gap-2 px-5 py-2.5 rounded bg-white text-black font-bold text-sm hover:bg-white/80">{'&#9654; Watch the official trailer' if trailer else 'See the full title page'}</a></p>
    {f'<h2 class="mt-12 text-xl font-bold">More popular {g.esc(plural(row.get("category") or "title"))} to watch next</h2><ul>{more}</ul>' if more else ''}"""
    intro = (f'      <p><strong>Short answer:</strong> as of {MONTH}, {g.esc(title)} ({g.esc(row.get("year"))}) is streaming in the '
             f'Philippines on <strong>{g.esc(services)}</strong>.</p>\n'
             f'      <p>Below you\'ll find links to each service, quick facts about the {kind}, and a few similar titles to watch next.</p>')
    h1 = f"Where to Watch {g.esc(title)} in the Philippines"
    path = f"guides/where-to-watch-{slug}-philippines.html"
    desc = f"Where to stream {title} legally in the Philippines ({MONTH}): {services}. Plus cast, trailer and similar shows."
    return path, h1, desc, article(g, path=path, title=f"Where to Watch {g.esc(title)} in the Philippines ({MONTH})", h1=h1,
                                   description=desc, intro_html=intro, content_html=content, image=g.wide_image(row, "w1280")[0])


def similar_list(g, seed_row, picks, data, heading, intro_text):
    items = "\n".join(entry(g, r, data, i) for i, r in enumerate(picks, start=1))
    intro = (f'      <p>{g.esc(intro_text)}</p>\n'
             f'      <p>This list comes from TMDB\'s recommendations, which are based on what viewers who rated '
             f'<a class="underline" href="../{seed_row["_slug"]}.html">{g.esc(seed_row["title"])}</a> also watched. '
             f'We kept only the titles you can look up on {g.SITE_NAME}, in order.</p>')
    path = f"guides/{seed_row['_slug'].replace('-season-3', '')}-similar-shows.html"
    desc = f"{len(picks)} picks for fans of {seed_row['title']}, with trailers, cast and where to watch them legally."
    schema = {"@context": "https://schema.org", "@type": "ItemList",
              "itemListElement": [{"@type": "ListItem", "position": i, "name": r["title"],
                                   **({"url": f'{g.SITE_URL}/{r["_slug"]}.html'} if g.SITE_URL else {})}
                                  for i, r in enumerate(picks, start=1)]}
    return path, heading, desc, article(g, path=path, title=heading, h1=heading, description=desc, intro_html=intro,
                                        content_html=f'<ul class="mt-6">{items}</ul>',
                                        image=g.wide_image(picks[0], "w1280")[0], schema=schema)


def new_with_trailers(g, picks, data, year, label):
    items = "\n".join(entry(g, r, data, i) for i, r in enumerate(picks, start=1))
    intro = (f'      <p>These are the most popular {label}s from {year} in the {g.SITE_NAME} catalog that already have an '
             f'official trailer, ranked by how many people are looking at them on TMDB right now.</p>\n'
             '      <p>Tap any title to watch the trailer and see which licensed services carry it.</p>')
    path = f"guides/new-{label.lower().replace(' ', '-')}s-{year}-trailers.html"
    h1 = f"New {label}s of {year}: Official Trailers"
    desc = f"The {len(picks)} most popular {label}s of {year} with official trailers, plus cast and where to stream them."
    return path, h1, desc, article(g, path=path, title=h1, h1=h1, description=desc, intro_html=intro,
                                   content_html=f'<ul class="mt-6">{items}</ul>', image=g.wide_image(picks[0], "w1280")[0])


def service_comparison(g, rows, data):
    def counts(category):
        seen, c, total = set(), Counter(), 0
        for r in rows:
            tid = r.get("tmdb_id")
            if r.get("category") != category or not tid or tid in seen or tid not in data.get("ph", {}):
                continue
            seen.add(tid)
            total += 1
            for p in data["ph"][tid].get("providers", []):
                c[p] += 1
        return total, c

    sections, top_names = [], []
    for category in ("K-Drama", "C-Drama", "Anime"):
        total, c = counts(category)
        if total < 10 or not c:
            continue
        top = c.most_common(8)
        top_names.append((category, top[0][0], top[0][1], total))
        tbl = "\n".join(f'<tr class="border-b border-white/10"><td class="py-2 pr-4">{g.esc(name)}</td>'
                        f'<td class="py-2 pr-4 text-right font-semibold">{n}</td>'
                        f'<td class="py-2 text-right text-zinc-400">{round(100 * n / total)}%</td></tr>' for name, n in top)
        sections.append(f"""
    <h2 class="mt-10 text-xl font-bold">{g.esc(plural(category))} ({total} titles checked)</h2>
    <table class="mt-3 w-full text-sm">
      <thead><tr class="border-b border-white/20 text-zinc-500"><th class="py-2 text-left font-medium">Service</th><th class="py-2 text-right font-medium">Titles</th><th class="py-2 text-right font-medium">Share</th></tr></thead>
      <tbody>{tbl}</tbody>
    </table>""")
    if not sections:
        return None
    summary = " ".join(f'For {g.esc(plural(cat))}, <strong>{g.esc(name)}</strong> carries the most: {n} of the {total} we checked.'
                       for cat, name, n, total in top_names)
    intro = (f'      <p>Which subscription should you get if you mainly watch Asian dramas in the Philippines? We checked '
             f'every title in the {g.SITE_NAME} catalog against Philippines streaming data in {MONTH} and counted which '
             f'services carry them.</p>\n      <p>{summary}</p>\n'
             '      <p>A title can be on more than one service, so the shares add up to more than 100%. These counts cover '
             f'our catalog, not each service\'s full library.</p>')
    path = "guides/best-streaming-service-kdramas-philippines.html"
    h1 = "Best Streaming Service for K-Dramas in the Philippines"
    desc = f"Which service has the most K-dramas, C-dramas and anime in the Philippines? Counts from {MONTH}."
    return path, h1, desc, article(g, path=path, title=f"{h1} ({MONTH})", h1=h1, description=desc,
                                   intro_html=intro, content_html="".join(sections))


# ---------------------------------------------------------------------------
def hub(g, guides):
    cards = "\n".join(f"""      <a href="{path.split('/', 1)[1]}" class="group block rounded-lg overflow-hidden bg-zinc-900 ring-1 ring-white/10 hover:ring-pink-600 transition">
        {f'<div class="aspect-video bg-zinc-800 overflow-hidden"><img src="{g.esc(img)}" alt="" loading="lazy" class="w-full h-full object-cover group-hover:scale-105 transition duration-500"></div>' if img else ''}
        <div class="p-4"><h2 class="font-bold group-hover:text-pink-500">{h1}</h2><p class="mt-1 text-sm text-zinc-400">{g.esc(desc)}</p></div>
      </a>""" for path, h1, desc, img in guides)
    body = f"""
  <main class="flex-1 w-full max-w-6xl mx-auto px-4 sm:px-8 py-8 sm:py-12">
    <h1 class="text-3xl sm:text-4xl font-black tracking-tight">Guides</h1>
    <p class="mt-2 text-zinc-400">Where to watch, what to watch next, and which service is worth it.</p>
    <div class="mt-8 grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
{cards}
    </div>
  </main>
"""
    return g.shell(f"Guides: Where to Watch and What to Watch Next | {g.SITE_NAME}", body,
                   "Guides to where to stream K-dramas, C-dramas and anime legally, and what to watch next.",
                   root="../", path="guides/index.html", active="guides")


def build(g, rows):
    """Write every guide plus guides/index.html. Returns (paths for the sitemap, cards for the homepage)."""
    data = load_data()
    out = g.OUTPUT_DIR / "guides"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.html"):
        old.unlink(missing_ok=True)
    by_slug = {r["_slug"]: r for r in rows}
    by_pop = sorted(rows, key=g.popularity, reverse=True)
    made = []  # (path, h1, description, image)

    def save(result, image=""):
        if not result:
            return
        path, h1, desc, page = result
        (g.OUTPUT_DIR / path).write_text(page, encoding="utf-8")
        made.append((path, h1, desc, image))

    # 1) Where to watch in the Philippines: the 5 most popular dramas that have your description and PH data.
    picks, seen = [], set()
    for r in by_pop:
        # skip "Season 2/3" rows: their year is the show's first year, which reads oddly in a headline
        if r.get("category") in ("K-Drama", "C-Drama") and r.get("description") and ph_info(data, r).get("providers") \
                and not re.search(r"season|part|-\d+$", r["_slug"]) \
                and r.get("tmdb_id") not in seen:
            picks.append(r)
            seen.add(r.get("tmdb_id"))
        if len(picks) == 5:
            break
    for r in picks:
        related = [x for x in by_pop if x.get("category") == r.get("category") and x.get("tmdb_id") != r.get("tmdb_id")
                   and x.get("description")][:4]
        save(where_to_watch_ph(g, r, data, related), g.wide_image(r)[0])

    # 2) "Dramas like ..." from TMDB recommendations.
    for seed, (heading, intro) in SIMILAR_INTROS.items():
        seed_row = by_slug.get(seed)
        slugs = [s for s in data.get("similar", {}).get(seed, []) if s in by_slug]
        if seed_row and len(slugs) >= 5:
            picks = [by_slug[s] for s in slugs[:CARD_LIMIT]]
            save(similar_list(g, seed_row, picks, data, heading, intro), g.wide_image(picks[0])[0])

    # 3) New K-dramas of the newest year with official trailers.
    years = sorted({g.year_of(r) for r in rows if r.get("category") == "K-Drama"}, reverse=True)
    for year in years[:1]:
        picks = [r for r in by_pop if r.get("category") == "K-Drama" and g.year_of(r) == year
                 and g.YOUTUBE_ID.match(r.get("trailer_youtube_id", ""))][:15]
        if len(picks) >= 5:
            save(new_with_trailers(g, picks, data, year, "K-Drama"), g.wide_image(picks[0])[0])

    # 4) Which service has the most K-dramas in the Philippines.
    save(service_comparison(g, rows, data))

    (out / "index.html").write_text(hub(g, made), encoding="utf-8")
    return ["guides/index.html"] + [m[0] for m in made], made
