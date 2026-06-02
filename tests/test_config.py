from omnisync.config import Settings


def test_default_sync_time():
    assert Settings().sync_time == "05:00"
