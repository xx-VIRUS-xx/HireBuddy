import csv

import pytest

import ingest
from scorer import score_posting


class FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status_code = status

    def json(self):
        return self._payload


def fake_get(payload, status=200):
    return lambda *args, **kwargs: FakeResponse(payload, status)


# --- scorer -----------------------------------------------------------------

def test_score_combines_title_stack_and_remote_signals():
    result = score_posting("Backend Engineer", "We use Python and FastAPI.", "Remote")
    # 1 title keyword (x3) + 2 stack keywords (x2 each) + remote bonus (5)
    assert result["score"] == 3 + 4 + 5
    assert result["stack_matches"] == ["python", "fastapi"]
    assert result["remote_ok"] is True


def test_anti_keywords_push_the_score_down():
    plain = score_posting("Engineer", "Build things.", "Berlin")
    java = score_posting("Java Developer", "Build things.", "Berlin")
    assert java["score"] == plain["score"] - 10


def test_remote_hint_is_read_from_location_only():
    assert score_posting("Engineer", "remote friendly", "Berlin")["remote_ok"] is False
    assert score_posting("Engineer", "", "India")["remote_ok"] is True


# --- fetchers -----------------------------------------------------------------

def test_greenhouse_jobs_are_normalised_and_html_stripped(monkeypatch):
    monkeypatch.setattr(ingest.requests, "get", fake_get({"jobs": [{
        "title": "Platform Engineer",
        "location": {"name": "Remote"},
        "absolute_url": "https://example.com/1",
        "content": "<p>Python <b>services</b></p>",
    }]}))
    job = ingest.fetch_greenhouse("acme")[0]
    assert (job["source"], job["company"], job["title"], job["location"], job["url"]) == (
        "greenhouse", "acme", "Platform Engineer", "Remote", "https://example.com/1")
    assert "<" not in job["description"]
    assert "Python" in job["description"] and "services" in job["description"]


def test_lever_jobs_are_normalised(monkeypatch):
    monkeypatch.setattr(ingest.requests, "get", fake_get([{
        "text": "Search Engineer",
        "categories": {"location": "Anywhere"},
        "hostedUrl": "https://example.com/2",
        "descriptionPlain": "Elasticsearch",
    }]))
    job = ingest.fetch_lever("acme")[0]
    assert (job["source"], job["title"], job["location"], job["url"]) == (
        "lever", "Search Engineer", "Anywhere", "https://example.com/2")


def test_ashby_jobs_are_normalised(monkeypatch):
    monkeypatch.setattr(ingest.requests, "get", fake_get({"jobs": [{
        "title": "ML Platform Engineer",
        "location": "India",
        "jobUrl": "https://example.com/3",
        "descriptionPlain": "Kubernetes",
    }]}))
    job = ingest.fetch_ashby("acme")[0]
    assert (job["source"], job["title"], job["description"]) == ("ashby", "ML Platform Engineer", "Kubernetes")


@pytest.mark.parametrize("fetch", [ingest.fetch_greenhouse, ingest.fetch_lever, ingest.fetch_ashby])
def test_fetchers_return_empty_on_http_error_or_network_failure(monkeypatch, fetch):
    monkeypatch.setattr(ingest.requests, "get", fake_get({}, status=404))
    assert fetch("acme") == []

    def boom(*args, **kwargs):
        raise ingest.requests.RequestException("down")

    monkeypatch.setattr(ingest.requests, "get", boom)
    assert fetch("acme") == []


# --- pipeline -------------------------------------------------------------------

def test_linkedin_scraper_is_gone():
    assert not hasattr(ingest, "fetch_linkedin_public")


def test_main_writes_postings_sorted_by_score(tmp_path, monkeypatch):
    companies = tmp_path / "companies.yaml"
    companies.write_text("greenhouse:\n  - acme\nlever: []\nashby: []\n")
    out = tmp_path / "openings.csv"
    monkeypatch.setattr(ingest, "COMPANIES_FILE", companies)
    monkeypatch.setattr(ingest, "OUT_CSV", out)
    monkeypatch.setattr(ingest.time, "sleep", lambda s: None)
    monkeypatch.setattr(ingest, "fetch_greenhouse", lambda slug: [
        {"source": "greenhouse", "company": slug, "title": "Java Developer", "location": "Berlin", "url": "u1", "description": ""},
        {"source": "greenhouse", "company": slug, "title": "Backend Engineer", "location": "Remote", "url": "u2", "description": "python"},
    ])

    ingest.main()

    rows = list(csv.DictReader(out.open()))
    assert [r["title"] for r in rows] == ["Backend Engineer", "Java Developer"]
    assert int(rows[0]["score"]) > int(rows[1]["score"])
    assert rows[0]["remote_ok"] == "True"
