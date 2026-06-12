import contextlib
import datetime
import json
import os
import sqlite3

DB_PATH = os.environ.get("DB_PATH", "/data/jobs.db")

STATUSES = (None, "saved", "hidden")

SETTINGS_KEY = "settings_override"


def _conn():
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _cutoff_iso(hours):
    dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=hours)
    return dt.isoformat()


def init():
    with contextlib.closing(_conn()) as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS jobs (
                refnr        TEXT PRIMARY KEY,
                title        TEXT,
                employer     TEXT,
                ort          TEXT,
                plz          TEXT,
                distance     REAL,
                published    TEXT,
                entry_date   TEXT,
                external_url TEXT,
                search_name  TEXT,
                first_seen   TEXT,
                last_seen    TEXT
            )"""
        )
        c.execute(
            "CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT)"
        )
        cols = [r[1] for r in c.execute("PRAGMA table_info(jobs)").fetchall()]
        if "status" not in cols:
            c.execute("ALTER TABLE jobs ADD COLUMN status TEXT")
        c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_first_seen ON jobs(first_seen)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_search_name ON jobs(search_name)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        c.commit()


def upsert(jobs):
    """Insert new jobs, refresh last_seen + volatile fields on known ones.

    Returns the number of genuinely new postings (by refnr)."""
    ts = now_iso()
    new = 0
    with contextlib.closing(_conn()) as c:
        for j in jobs:
            if not j.get("refnr"):
                continue
            row = c.execute(
                "SELECT 1 FROM jobs WHERE refnr=?", (j["refnr"],)
            ).fetchone()
            if row:
                c.execute(
                    """UPDATE jobs SET last_seen=?, distance=?, title=?, employer=?,
                       ort=?, plz=?, published=?, entry_date=?, external_url=?
                       WHERE refnr=?""",
                    (ts, j["distance"], j["title"], j["employer"], j["ort"],
                     j["plz"], j["published"], j["entry_date"],
                     j["external_url"], j["refnr"]),
                )
            else:
                new += 1
                c.execute(
                    """INSERT INTO jobs (refnr, title, employer, ort, plz, distance,
                       published, entry_date, external_url, search_name,
                       first_seen, last_seen)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (j["refnr"], j["title"], j["employer"], j["ort"], j["plz"],
                     j["distance"], j["published"], j["entry_date"],
                     j["external_url"], j["search_name"], ts, ts),
                )
        c.commit()
    return new


def fetch(bucket, new_window_hours, q=None, search_name=None, limit=100, offset=0):
    cutoff = _cutoff_iso(new_window_hours)
    where, params = [], []
    if bucket == "saved":
        where.append("status = 'saved'")
    elif bucket == "hidden":
        where.append("status = 'hidden'")
    else:
        where.append("(status IS NULL OR status != 'hidden')")
        if bucket == "new":
            where.append("first_seen >= ?")
            params.append(cutoff)
        else:
            where.append("first_seen < ?")
            params.append(cutoff)
    if q:
        where.append("(title LIKE ? OR employer LIKE ? OR ort LIKE ?)")
        params += [f"%{q}%"] * 3
    if search_name:
        where.append("search_name = ?")
        params.append(search_name)
    sql = ("SELECT * FROM jobs WHERE " + " AND ".join(where) +
           " ORDER BY first_seen DESC LIMIT ? OFFSET ?")
    params += [limit, offset]
    with contextlib.closing(_conn()) as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def stats(new_window_hours):
    cutoff = _cutoff_iso(new_window_hours)
    with contextlib.closing(_conn()) as c:
        total = c.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        new = c.execute(
            "SELECT COUNT(*) FROM jobs WHERE first_seen >= ? "
            "AND (status IS NULL OR status != 'hidden')", (cutoff,)
        ).fetchone()[0]
        saved = c.execute(
            "SELECT COUNT(*) FROM jobs WHERE status = 'saved'"
        ).fetchone()[0]
    return {"total": total, "new": new, "saved": saved}


def prune(prune_after_days):
    cutoff = _cutoff_iso(prune_after_days * 24)
    with contextlib.closing(_conn()) as c:
        cur = c.execute(
            "DELETE FROM jobs WHERE last_seen < ? AND (status IS NULL OR status != 'saved')",
            (cutoff,),
        )
        c.commit()
        return cur.rowcount


def set_status(refnr, status):
    """Mark a job as saved/hidden, or clear it (status=None). Returns True if found."""
    if status not in STATUSES:
        raise ValueError(f"invalid status: {status!r}")
    with contextlib.closing(_conn()) as c:
        cur = c.execute("UPDATE jobs SET status=? WHERE refnr=?", (status, refnr))
        c.commit()
        return cur.rowcount > 0


def meta_set(key, value):
    with contextlib.closing(_conn()) as c:
        c.execute(
            "INSERT INTO meta(key,value) VALUES(?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        c.commit()


def meta_get(key, default=None):
    with contextlib.closing(_conn()) as c:
        row = c.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else default


def get_settings_override():
    """Return persisted job-search settings that override the add-on config."""
    raw = meta_get(SETTINGS_KEY)
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except ValueError:
        return {}


def set_settings_override(settings):
    meta_set(SETTINGS_KEY, json.dumps(settings))


def clear_settings_override():
    with contextlib.closing(_conn()) as c:
        c.execute("DELETE FROM meta WHERE key=?", (SETTINGS_KEY,))
        c.commit()

