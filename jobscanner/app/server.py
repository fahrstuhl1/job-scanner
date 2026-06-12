import os
import threading

from flask import Flask, jsonify, request, send_from_directory

import db

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")


class State:
    def __init__(self):
        self.opts = {}
        self.scanning = False
        self.scan_event = threading.Event()


def create_app(state):
    app = Flask(__name__, static_folder=None)

    @app.get("/")
    def index():
        return send_from_directory(WEB_DIR, "index.html")

    @app.get("/api/jobs")
    def jobs():
        bucket = request.args.get("bucket", "new")
        if bucket not in ("new", "archive"):
            bucket = "new"
        q = request.args.get("q") or None
        search_name = request.args.get("search") or None
        win = int(state.opts.get("new_window_hours", 24))
        return jsonify(db.fetch(bucket, win, q, search_name))

    @app.get("/api/stats")
    def stats():
        win = int(state.opts.get("new_window_hours", 24))
        payload = db.stats(win)
        payload.update({
            "scanning": state.scanning,
            "last_scan": db.meta_get("last_scan"),
            "wo": state.opts.get("wo"),
            "umkreis": state.opts.get("umkreis"),
            "new_window_hours": win,
            "searches": [s.get("name") for s in state.opts.get("searches", [])],
        })
        return jsonify(payload)

    @app.post("/api/scan")
    def scan_now():
        state.scan_event.set()
        return jsonify({"ok": True})

    return app
