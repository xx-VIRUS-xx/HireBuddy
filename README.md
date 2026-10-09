# HireBuddy

A personal job-search assistant prototype with two independent parts: a local dashboard for browsing and saving target companies, and a Python pipeline that pulls open roles from public job-board APIs (Greenhouse, Lever, Ashby) and ranks them against a keyword profile.

> **Status: early prototype.** The dashboard shows hard-coded sample companies, and the ingestion pipeline is not connected to it. Message generation, email sending and tracking from the original plan are not built.

System design: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Original plan: [docs/PLAN.md](docs/PLAN.md).

## Problem it addresses

A targeted job search means checking many company career pages, deciding which roles fit, and tracking who you have contacted. This project aims to do the discovery and ranking part automatically and keep the shortlist in one place, leaving every outreach decision to a human.

## What works today

| Part | Where | What it does |
|---|---|---|
| Dashboard | `index.html`, `app.js`, `styles.css`, served by `server.js` | LinkedIn profile URL and preference form, company cards with a remote/growth filter, save-for-later, all kept in browser `localStorage`. The six company cards and their "match" percentages are fixed sample data, not computed, and "Refresh" only re-renders them |
| Browser session helper | `server.js` | A button opens Chromium with a persistent profile (`.linkedin-chromium-profile/`) so you can log in to LinkedIn yourself once. It does not automate login, scrape pages or send messages |
| Job ingestion | `ingestion/ingest.py` | Reads open roles for the companies in `ingestion/companies.yaml` from the Greenhouse, Lever and Ashby public APIs, scores each, and writes `ingestion/openings.csv` sorted by score |
| Scoring | `ingestion/scorer.py`, `ingestion/profile_keywords.py` | Keyword score: +3 per title keyword found, +2 per stack keyword found, +5 if the location hints at remote, -10 per anti-keyword |

## Setup and run

Dashboard (developed on Node.js 24):

```bash
npm install
npm run install-browser     # downloads Chromium for Playwright
npm run dev                 # http://127.0.0.1:8000
```

Ingestion (developed on Python 3.12):

```bash
cd ingestion
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 ingest.py           # writes openings.csv next to the script
```

Edit `ingestion/companies.yaml` to choose companies (the board slug used by each provider) and `ingestion/profile_keywords.py` to describe the roles and stack you want.

## Tests

```bash
npm test                                   # 5 Node tests for the server
pip install -r ingestion/requirements.txt pytest
python3 -m pytest                          # 11 tests for the scorer and ingestion
```

The server tests start the real server on a free port and check which files it serves and that it listens on loopback only. The ingestion tests use fake HTTP responses, so nothing touches the network.

## Privacy

`.linkedin-chromium-profile/` holds a logged-in browser session (cookies). It is git-ignored; never share or commit it. Personal documents (resume PDF), outreach drafts and the generated job data are also git-ignored.

## Limitations and next steps

- The dashboard data is static; connecting it to `openings.csv` and computing real match scores is the obvious next step.
- Scoring is plain keyword counting. The plan's embedding-based matching, deduplication across runs, freshness and seniority signals are not implemented.
- Ingestion fetch errors are swallowed (a failing board just returns no jobs), so check the printed counts.
- `profile_keywords.py` and the seed company list are tuned to one person's profile.
- Playwright is launched with `--disable-blink-features=AutomationControlled`, which hides automation signals from sites. Review that choice against the terms of any site you use it on.
- `POST /api/linkedin/connect` has no origin check, so any web page open on the same machine could trigger it. Keep the server running only when you use it.
- Phases 3 to 5 of the plan (message generation, email sending and reply tracking, LinkedIn contact import) are not built.
- No LICENSE has been chosen.
