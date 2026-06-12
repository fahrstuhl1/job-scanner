import os
import sys

import pytest

APP_DIR = os.path.join(os.path.dirname(__file__), "..", "app")
sys.path.insert(0, os.path.abspath(APP_DIR))

import db  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "jobs.db"))
    db.init()
