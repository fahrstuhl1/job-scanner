import contextlib
import datetime
import sqlite3

import pytest

import db


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "jobs.db"))
    db.init()


def _job(refnr, **overrides):
    job = {
        "refnr": refnr,
        "title": f"Job {refnr}",
        "employer": "ACME",
        "ort": "Rostock",
        "plz": "18055",
        "distance": 10.0,
        "published": "2026-06-01",
        "entry_date": "2026-07-01",
        "external_url": f"https://example.com/{refnr}",
        "search_name": "Test",
    }
    job.update(overrides)
    return job


def _backdate(refnr, hours):
    iso = (datetime.datetime.now(datetime.timezone.utc)
           - datetime.timedelta(hours=hours)).isoformat()
    with contextlib.closing(sqlite3.connect(db.DB_PATH)) as c:
        c.execute("UPDATE jobs SET first_seen=?, last_seen=? WHERE refnr=?",
                  (iso, iso, refnr))
        c.commit()


def test_upsert_inserts_new_jobs_and_counts_them():
    new = db.upsert([_job("1"), _job("2")])
    assert new == 2
    assert db.stats(24)["total"] == 2


def test_upsert_updates_existing_job_without_counting_as_new():
    db.upsert([_job("1", title="Old Title")])
    new = db.upsert([_job("1", title="New Title")])
    assert new == 0
    rows = db.fetch("new", 24)
    assert rows[0]["title"] == "New Title"


def test_fetch_new_vs_archive_buckets():
    db.upsert([_job("recent"), _job("old")])
    _backdate("old", hours=48)

    new_jobs = db.fetch("new", 24)
    archive_jobs = db.fetch("archive", 24)
    assert [j["refnr"] for j in new_jobs] == ["recent"]
    assert [j["refnr"] for j in archive_jobs] == ["old"]


def test_fetch_filters_by_query_and_search_name():
    db.upsert([
        _job("1", title="Systemadministrator", search_name="Admin"),
        _job("2", title="Vertriebsleiter", search_name="Sales"),
    ])
    assert [j["refnr"] for j in db.fetch("new", 24, q="System")] == ["1"]
    assert [j["refnr"] for j in db.fetch("new", 24, search_name="Sales")] == ["2"]


def test_fetch_respects_limit_and_offset():
    db.upsert([_job(str(i)) for i in range(5)])
    page1 = db.fetch("new", 24, limit=2, offset=0)
    page2 = db.fetch("new", 24, limit=2, offset=2)
    assert len(page1) == 2
    assert len(page2) == 2
    assert {j["refnr"] for j in page1} & {j["refnr"] for j in page2} == set()


def test_set_status_saved_and_hidden():
    db.upsert([_job("1"), _job("2")])
    assert db.set_status("1", "saved") is True
    assert db.set_status("2", "hidden") is True
    assert db.set_status("missing", "saved") is False

    saved = db.fetch("saved", 24)
    hidden = db.fetch("hidden", 24)
    assert [j["refnr"] for j in saved] == ["1"]
    assert [j["refnr"] for j in hidden] == ["2"]


def test_hidden_jobs_excluded_from_new_and_archive():
    db.upsert([_job("1"), _job("2")])
    db.set_status("2", "hidden")
    new_jobs = db.fetch("new", 24)
    assert [j["refnr"] for j in new_jobs] == ["1"]


def test_set_status_rejects_invalid_value():
    db.upsert([_job("1")])
    with pytest.raises(ValueError):
        db.set_status("1", "bogus")


def test_stats_counts_new_total_and_saved():
    db.upsert([_job("1"), _job("2"), _job("3")])
    _backdate("3", hours=48)
    db.set_status("2", "saved")

    s = db.stats(24)
    assert s["total"] == 3
    assert s["new"] == 2  # "3" is older than the window
    assert s["saved"] == 1


def test_prune_removes_stale_jobs_but_keeps_saved():
    db.upsert([_job("1"), _job("2")])
    db.set_status("2", "saved")
    _backdate("1", hours=24 * 100)
    _backdate("2", hours=24 * 100)

    removed = db.prune(45)
    assert removed == 1
    remaining = {j["refnr"] for j in db.fetch("saved", 24)}
    assert remaining == {"2"}
