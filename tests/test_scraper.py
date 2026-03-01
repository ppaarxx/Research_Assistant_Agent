import pytest

pytest.importorskip("bs4")
pytest.importorskip("asyncpg")

from app.agents.scraper import scrape_url


def test_scrape_url_handles_failure():
    result = scrape_url("https://invalid.localhost.this-should-fail")

    assert result["url"] == "https://invalid.localhost.this-should-fail"
    assert result["scrape_success"] is False
    assert result["word_count"] == 0
