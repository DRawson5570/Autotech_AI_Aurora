import json
import types

import pytest

import scripts.scrape_and_ingest as ssi


class DummyResponse:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self._body = body or {"status": True, "collection_name": "col-1"}

    def json(self):
        return self._body


def test_process_url_success(monkeypatch):
    calls = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        calls['url'] = url
        calls['json'] = json
        calls['headers'] = headers
        return DummyResponse(200, {"status": True, "collection_name": "col-1"})

    monkeypatch.setattr("requests.post", fake_post)

    ok, info = ssi.process_url("http://localhost:3000", "token", "https://example.com", "mycol")
    assert ok is True
    assert info == "col-1"
    assert calls['json']["url"] == "https://example.com"
    assert calls['json']["collection_name"] == "mycol"


def test_create_knowledge_and_ingest(monkeypatch):
    post_calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        post_calls.append((url, json))
        if url.endswith("/api/v1/knowledge/create"):
            return DummyResponse(200, {"id": "kb-1", "name": json.get("name")})
        elif url.endswith("/api/v1/retrieval/process/web"):
            return DummyResponse(200, {"status": True, "collection_name": json.get("collection_name")})
        return DummyResponse(400, {"status": False})

    monkeypatch.setattr("requests.post", fake_post)

    result = ssi.scrape_and_ingest(["https://example.com/page1"], base_url="http://localhost:3000", api_key="tok", create_knowledge_name="My KB", concurrency=1)
    assert result["successes"] == 1
    assert result["failures"] == 0
    assert result["collection_name"] == "kb-1"


def test_fetch_sitemap_urls(monkeypatch):
    xml = b"""<?xml version='1.0' encoding='utf-8'?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://a.example/page1</loc></url>
      <url><loc>https://a.example/page2</loc></url>
    </urlset>"""

    class DummyGet:
        def __init__(self, content):
            self.content = content
            self.status_code = 200

        def raise_for_status(self):
            return None

    def fake_get(url, timeout=None):
        return DummyGet(xml)

    monkeypatch.setattr("requests.get", fake_get)

    urls = ssi.fetch_sitemap_urls("https://a.example/sitemap.xml")
    assert urls == ["https://a.example/page1", "https://a.example/page2"]


def test_process_url_retries(monkeypatch):
    calls = {"count": 0}

    def fake_post(url, json=None, headers=None, timeout=None):
        calls["count"] += 1
        if calls["count"] < 3:
            raise Exception("temporary network error")
        return DummyResponse(200, {"status": True, "collection_name": "col-x"})

    monkeypatch.setattr("requests.post", fake_post)

    ok, info = ssi.process_url("http://localhost:3000", "tok", "https://a.example/", "col", retries=3, backoff_factor=0)
    assert ok is True
    assert info == "col-x"
    assert calls["count"] == 3


def test_crawl_and_ingest(monkeypatch):
    # Set up sample pages within a.example domain
    pages = {
        "https://a.example/": '<a href="/page1">p1</a><a href="https://b.example/x">ext</a>',
        "https://a.example/page1": '<a href="/page2">p2</a>',
        "https://a.example/page2": '<a href="/page3">p3</a>',
    }

    class DummyGet:
        def __init__(self, text):
            self.text = text
            self.status_code = 200

        def raise_for_status(self):
            return None

    def fake_get(url, timeout=None):
        # return page content for known pages
        text = pages.get(url, "")
        return DummyGet(text)

    processed = []

    def fake_process_url(base_url, api_key, url_to_process, collection_name, timeout=60, retries=ssi.DEFAULT_RETRIES, backoff_factor=ssi.DEFAULT_BACKOFF):
        processed.append(url_to_process)
        return True, "ok"

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("scripts.scrape_and_ingest.process_url", fake_process_url)

    summary = ssi.scrape_and_ingest(["https://a.example/"], crawl=True, max_depth=1, concurrency=1)

    # depth=1 -> should process root and page1 (links at depth 1), not page2
    assert "https://a.example/" in processed
    assert "https://a.example/page1" in processed
    assert "https://a.example/page2" not in processed
    assert summary["successes"] == 2
    assert summary["failures"] == 0


def test_domain_delay_respects_politeness(monkeypatch):
    # Two quick consecutive fetches to same domain should trigger a sleep when domain_delay > 0
    class DummyGet:
        def __init__(self, text=""):
            self.text = text
            self.status_code = 200
        def raise_for_status(self):
            return None

    def fake_get(url, timeout=None):
        return DummyGet("html")

    slept = []

    def fake_sleep(s):
        slept.append(s)

    monkeypatch.setattr("requests.get", fake_get)
    monkeypatch.setattr("time.sleep", fake_sleep)

    # Ensure domain tracking is empty
    ssi._DOMAIN_NEXT_ALLOWED.clear()

    # First fetch should set next_allowed; second fetch should cause a sleep call
    ssi._fetch_with_retries("https://a.example/", timeout=1, domain_delay=0.05)
    ssi._fetch_with_retries("https://a.example/page1", timeout=1, domain_delay=0.05)

    assert len(slept) >= 1
    assert any(s > 0 for s in slept)


def test_resume_file_skips_processed_urls(tmp_path, monkeypatch):
    resume_file = tmp_path / "resume.txt"
    # Write a URL that has already been processed
    resume_file.write_text("https://a.example/page1\n")

    processed = []

    def fake_process_url(base_url, api_key, url_to_process, collection_name, timeout=60, retries=ssi.DEFAULT_RETRIES, backoff_factor=ssi.DEFAULT_BACKOFF):
        processed.append(url_to_process)
        return True, "ok"

    monkeypatch.setattr("scripts.scrape_and_ingest.process_url", fake_process_url)

    summary = ssi.scrape_and_ingest(["https://a.example/page1", "https://a.example/page2"], crawl=False, concurrency=1, resume_file=str(resume_file))

    # page1 should be skipped; only page2 processed
    assert "https://a.example/page1" not in processed
    assert "https://a.example/page2" in processed
    assert summary["successes"] == 1
    # resume file should now contain page2 appended
    contents = resume_file.read_text().splitlines()
    assert "https://a.example/page1" in contents
    assert "https://a.example/page2" in contents
