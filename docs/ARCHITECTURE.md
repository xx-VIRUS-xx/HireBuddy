# Architecture

Two small programs that do not yet talk to each other: a local Node dashboard and a Python ingestion pipeline. The original design (see [PLAN.md](PLAN.md)) joins them through a profile store, a scorer, a contact store and a message generator; only the first parts exist.

## System context

```
 DASHBOARD (Node)                                  INGESTION (Python)

 Browser  <-- http://127.0.0.1:8000 -->  server.js   companies.yaml
   |  index.html, app.js, styles.css       |              |
   |  localStorage: URL, prefs, saved      | Playwright   v
   |                                       v          ingest.py --> Greenhouse API
   |  POST /api/linkedin/connect -->  Chromium           |     --> Lever API
   |                                  persistent         |     --> Ashby API
   |                                  profile            v
   |                                  (manual login)   scorer.py  <-- profile_keywords.py
   v                                                     |
 sample company cards (hard-coded)                       v
                                                    openings.csv (ranked)

                  (planned, not built)  profile store -> scorer -> contacts -> drafts -> email / manual LinkedIn queue
```

## Components

| Module | Responsibility |
|---|---|
| `server.js` | Minimal HTTP server using Node's `http`. Serves exactly three files (`/index.html`, `/app.js`, `/styles.css`) on 127.0.0.1, and exposes `POST /api/linkedin/connect`, which launches a persistent Playwright Chromium context in `.linkedin-chromium-profile/` and opens linkedin.com so the user can log in manually. Closes the context on SIGINT |
| `index.html`, `app.js`, `styles.css` | Single-page UI. State lives in `localStorage` (`hirebuddy-saved`, `hirebuddy-linkedin`, `hirebuddy-preferences`). Company cards come from an array in `app.js` |
| `ingestion/ingest.py` | Provider adapters (`fetch_greenhouse`, `fetch_lever`, `fetch_ashby`) normalise each provider's job format to `{source, company, title, location, url, description}`; `main` loops over `companies.yaml`, sleeps between calls, scores every posting, sorts, and writes the CSV |
| `ingestion/scorer.py` | `score_posting(title, description, location)` returns the score, the matched stack keywords and whether the location hints at remote work |
| `ingestion/profile_keywords.py` | The profile as keyword lists: title keywords, stack keywords, anti-keywords, remote hints |
| `ingestion/companies.yaml` | Seed list of provider board slugs |

## Key flows

**Ingestion run.** Read `companies.yaml` -> for each provider and slug fetch the public job board JSON (15 s timeout, 0.3 s pause) -> strip HTML (Greenhouse, Lever) and truncate descriptions to 4,000 characters -> score -> sort descending -> write `openings.csv`, then print the top ten.

**Browser session.** The dashboard button calls `POST /api/linkedin/connect` -> the server starts (or reuses) one persistent Chromium context -> opens LinkedIn -> returns a message telling the user whether to log in. Because the profile directory persists, later launches reuse the logged-in session.

## Key design decisions

- **Public job-board APIs as the source.** Greenhouse, Lever and Ashby expose unauthenticated JSON, so no scraping and no credentials are needed. A LinkedIn guest-page scraper that existed in an earlier version was removed.
- **Provider adapters with one normalised shape.** Adding a provider means one function that returns the same dictionary shape; scoring and output do not change.
- **Transparent scoring.** A weighted keyword count anyone can read and tune in `profile_keywords.py`, rather than an opaque model.
- **Human stays in the loop.** The browser helper only opens a session for manual use; nothing logs in, scrapes or sends messages on the user's behalf.
- **Local-only server with an allowlist.** The dashboard server binds to loopback and serves only its three front-end files, so project files such as the resume are never exposed.
- **Fail soft.** A provider error or timeout returns an empty list so one bad board does not stop the run.

## Known limitations

- The dashboard and the ingestion output are unconnected; the cards are static.
- No deduplication or state between runs, no freshness or seniority scoring, no embeddings.
- Errors from providers are silent.
- `POST /api/linkedin/connect` has no origin or CSRF protection.
- The Chromium launch uses `--disable-blink-features=AutomationControlled`.
- The profile directory contains live session cookies and must stay out of version control.
