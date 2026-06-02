from omnisync.scraper.models import SchoolEvent


def test_school_event_uid():
    event = SchoolEvent(uid="abc", title="Test", kind="exam", course_code="XXX", date_iso="2026-01-01")
    assert event.uid == "abc"
