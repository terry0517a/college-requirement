from collegedata import db


def test_connect_enables_tcp_keepalives(monkeypatch):
    seen = {}
    monkeypatch.setattr(db.psycopg, "connect", lambda url, **kw: seen.update(url=url, **kw))
    db.connect("postgresql://h/d")
    assert seen == {"url": "postgresql://h/d", "keepalives": 1, "keepalives_idle": 30,
                    "keepalives_interval": 10, "keepalives_count": 5}
