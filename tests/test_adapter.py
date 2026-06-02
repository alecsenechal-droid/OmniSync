from omnisync.scraper import scrape_omnivox


def test_scrape_dry_run_returns_demo_events():
    events, _, _ = scrape_omnivox(dry_run=True)
    assert len(events) == 2
    kinds = {e.kind for e in events}
    assert kinds == {"assignment", "exam"}
