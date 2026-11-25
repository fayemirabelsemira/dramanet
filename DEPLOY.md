# StreamHub: how to update and publish your site

Everything happens in **Terminal** on your Mac (press ⌘ + Space, type *Terminal*, press Enter).
Copy each grey line, paste it into Terminal, and press Enter.

## 1. Build the site

```bash
cd ~/Desktop/streaming_project
python3 generate_site.py
```

This creates a folder called **site_output** inside your project folder. That folder *is* your website.

Before you publish the first time, open `generate_site.py` in TextEdit and change
`CONTACT_EMAIL = "contact@example.com"` to your own email (it appears on the Contact, Privacy and DMCA pages).

To preview it, double-click `site_output/index.html` in Finder.

## 2. Publish it (pick one)

### Option A: Netlify (easiest, no account setup beyond sign-up)

1. Go to <https://app.netlify.com/drop> and sign up or log in (free).
2. Drag the **site_output** folder from Finder onto that page.
3. Wait about a minute. Netlify gives you a link like `https://something-random.netlify.app`.
4. To rename it: **Site configuration → Change site name**.
5. To update the site later: build again (step 1), open your site in Netlify,
   go to **Deploys**, and drag the new **site_output** folder onto the drop area there.

### Option B: GitHub Pages

1. Create a new **public** repository on <https://github.com/new>, for example `streamhub`.
2. On the new repository page, click **uploading an existing file**.
3. Open **site_output** in Finder, select everything inside it (⌘ + A), and drag it onto the page.
   (Upload the files *inside* the folder, not the folder itself.) Click **Commit changes**.
4. Go to **Settings → Pages**. Under *Branch*, pick **main** and **/(root)**, then **Save**.
5. After a minute or two your site is at `https://YOUR-USERNAME.github.io/streamhub/`.

Note: the browser upload takes up to 100 files at a time, and your site has about 1,500 pages,
so Netlify (Option A) is much easier for this site.

## 3. After the first publish: get found on Google

1. Open `generate_site.py` in TextEdit and set `SITE_URL` to your live address, with no slash at the end,
   for example `SITE_URL = "https://streamhub-aye.netlify.app"`.
2. Build again (step 1) and upload again. This turns on `sitemap.xml`, canonical links and share links
   (the preview card people see on Facebook, Messenger and X).
3. Go to <https://search.google.com/search-console> and sign in with your Google account.
4. Click **Add property**, choose **URL prefix**, and paste your site address.
5. Choose the **HTML tag** check. Google shows a line like
   `<meta name="google-site-verification" content="abc123..." />`. Copy only the code between the quotes after `content=`.
6. Open `generate_site.py`, paste it into `GOOGLE_VERIFICATION = ""` near the top, then build and upload again.
7. Back in Search Console, click **Verify**.
8. In the left menu open **Sitemaps**, type `sitemap.xml`, and click **Submit**.
9. Give it a few days. **Pages** shows what Google has indexed, and **Performance** shows the searches people find you with.

## 4. Adding your ad code

- **On each title page:** paste your Monetag/PropellerAds code into `template.html`
  at the comments marked `AD SLOT 1` to `AD SLOT 7`, or into the
  `PASTE MONETAG / PROPELLERADS CODE HERE` script near the bottom.
- **On the homepage:** in `generate_site.py`, find `PASTE MONETAG / PROPELLERADS CODE HERE`
  (and the `<!-- AD_SLOT_TOP -->` and `<!-- AD_SLOT_HOME_MID -->` comments). The same script tag also
  covers the Explore page.
- **On the guide pages:** the same global script covers them; `<!-- AD_SLOT_GUIDE_TOP -->` marks a spot under each intro (in `guides.py`).
- Then build again (step 1) and upload again.

## 5. Updating titles

- **Add or edit titles:** edit `catalog.csv` (Numbers or Excel both work; save as CSV).
- **Tidy duplicates:** `python3 clean_catalog.py` (makes a backup in `backups/` first).
- **Fill in missing cast, genre, Movies/Series, trailers and where-to-watch from TMDB:**

  ```bash
  export TMDB_API_KEY="paste-your-key-here"
  python3 enrich_tmdb.py
  ```

  It only fills blanks and never overwrites what you typed. Titles it couldn't match safely
  are listed in `tmdb_unmatched.txt`.

- **Refresh the guides' Philippines streaming data and "similar shows"** (do this every month or two):

  ```bash
  export TMDB_API_KEY="paste-your-key-here"
  python3 guides_data.py
  ```

Then build again (step 1) and upload again.
