"""
HireBuddy job ingestion.

Pulls open roles from public sources and scores them against profile_keywords.
Sources:
  - Greenhouse public API   (no auth)
  - Lever public API        (no auth)
  - Ashby public API        (no auth)
  - LinkedIn public job search pages (no auth, no login) — best-effort, HTML
    scraping of publicly served search results only. LinkedIn rate-limits and
    sometimes blocks scripted requests to these pages; treat failures here as
    expected and fall back to checking https://linkedin.com/jobs manually.

This script never logs into any site, stores no credentials, and does not
send any messages. It only reads public job listing data.
"""
import csv
import html
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

import requests
import yaml

from scorer import score_posting

ROOT = Path(__file__).parent
OUT_CSV = ROOT / "openings.csv"
COMPANIES_FILE = ROOT / "companies.yaml"

HEADERS = {"User-Agent": "HireBuddy-JobIngestion/1.0 (personal job search tool)"}
TIMEOUT = 15


def fetch_greenhouse(slug: str) -> list[dict]:
    url = f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs?content=true"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return []
        jobs = r.json().get("jobs", [])
    except requests.RequestException:
        return []

    out = []
    for j in jobs:
        content = re.sub("<[^>]+>", " ", j.get("content") or "")
        out.append({
            "source": "greenhouse",
            "company": slug,
            "title": j.get("title", ""),
            "location": (j.get("location") or {}).get("name", ""),
            "url": j.get("absolute_url", ""),
            "description": html.unescape(content)[:4000],
        })
    return out


def fetch_lever(slug: str) -> list[dict]:
    url = f"https://api.lever.co/v0/postings/{slug}?mode=json"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return []
        jobs = r.json()
    except requests.RequestException:
        return []

    out = []
    for j in jobs:
        desc = re.sub("<[^>]+>", " ", (j.get("descriptionPlain") or j.get("description") or ""))
        out.append({
            "source": "lever",
            "company": slug,
            "title": j.get("text", ""),
            "location": (j.get("categories") or {}).get("location", ""),
            "url": j.get("hostedUrl", ""),
            "description": html.unescape(desc)[:4000],
        })
    return out


def fetch_ashby(slug: str) -> list[dict]:
    url = f"https://api.ashbyhq.com/posting-api/job-board/{slug}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        if r.status_code != 200:
            return []
        jobs = r.json().get("jobs", [])
    except requests.RequestException:
        return []

    out = []
    for j in jobs:
        out.append({
            "source": "ashby",
            "company": slug,
            "title": j.get("title", ""),
            "location": j.get("location", ""),
            "url": j.get("jobUrl", ""),
            "description": (j.get("descriptionPlain") or "")[:4000],
        })
    return out


def fetch_linkedin_public(keywords: str, location: str = "India", max_results: int = 25) -> list[dict]:
    """
    Best-effort read of LinkedIn's public job search results page (no login,
    no auth cookie). LinkedIn frequently rate-limits/blocks non-browser
    requests to this endpoint — a failure or empty result here is expected
    and not a bug. Use https://linkedin.com/jobs manually as the reliable
    fallback; this is a bonus source, not the primary one.
    """
    url = (
        "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
        f"?keywords={quote_plus(keywords)}&location={quote_plus(location)}"
        f"&f_WT=2&start=0"  # f_WT=2 = remote
    )
    try:
        r = requests.get(url, headers={**HEADERS, "Accept": "text/html"}, timeout=TIMEOUT)
        if r.status_code != 200:
            print(f"  [linkedin] blocked or unavailable (status {r.status_code}) — skipping, check manually", file=sys.stderr)
            return []
    except requests.RequestException as e:
        print(f"  [linkedin] request failed ({e}) — skipping, check manually", file=sys.stderr)
        return []

    titles = re.findall(r'class="base-search-card__title">\s*([^<]+)', r.text)
    companies = re.findall(r'class="base-search-card__subtitle">\s*<a[^>]*>([^<]+)', r.text)
    locations = re.findall(r'class="job-search-card__location">\s*([^<]+)', r.text)
    links = re.findall(r'<a class="base-card__full-link" href="([^"?]+)', r.text)

    out = []
    for i in range(min(len(titles), max_results)):
        out.append({
            "source": "linkedin",
            "company": companies[i].strip() if i < len(companies) else "",
            "title": titles[i].strip(),
            "location": locations[i].strip() if i < len(locations) else "",
            "url": links[i] if i < len(links) else "",
            "description": "",  # full JD requires an extra fetch per posting; kept out to stay lightweight
        })
    return out


def main():
    companies = yaml.safe_load(COMPANIES_FILE.read_text())
    all_jobs: list[dict] = []

    for slug in companies.get("greenhouse", []):
        print(f"Fetching Greenhouse: {slug}")
        all_jobs.extend(fetch_greenhouse(slug))
        time.sleep(0.3)

    for slug in companies.get("lever", []):
        print(f"Fetching Lever: {slug}")
        all_jobs.extend(fetch_lever(slug))
        time.sleep(0.3)

    for slug in companies.get("ashby", []):
        print(f"Fetching Ashby: {slug}")
        all_jobs.extend(fetch_ashby(slug))
        time.sleep(0.3)

    for query in ["backend engineer", "AI infrastructure engineer", "search engineer"]:
        print(f"Fetching LinkedIn public search: {query}")
        all_jobs.extend(fetch_linkedin_public(query))
        time.sleep(1.0)

    scored = []
    for job in all_jobs:
        s = score_posting(job["title"], job.get("description", ""), job.get("location", ""))
        scored.append({**job, **s})

    scored.sort(key=lambda j: j["score"], reverse=True)

    with OUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "score", "title", "company", "location", "remote_ok",
            "stack_matches", "source", "url",
        ])
        writer.writeheader()
        for j in scored:
            writer.writerow({
                "score": j["score"],
                "title": j["title"],
                "company": j["company"],
                "location": j["location"],
                "remote_ok": j["remote_ok"],
                "stack_matches": "; ".join(j["stack_matches"]),
                "source": j["source"],
                "url": j["url"],
            })

    print(f"\nWrote {len(scored)} postings to {OUT_CSV}")
    print("Top 10:")
    for j in scored[:10]:
        print(f"  [{j['score']:>3}] {j['title'][:50]:<50} @ {j['company']:<20} ({j['source']})")


if __name__ == "__main__":
    main()
