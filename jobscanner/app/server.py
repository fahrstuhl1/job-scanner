import os
import threading

from flask import Flask, jsonify, request, send_from_directory

import config
import db

WEB_DIR = os.path.join(os.path.dirname(__file__), "web")


MAX_SCAN_DAYS = 90
MAX_LIMIT = 500


def _validate_settings(body):
    """Validate and normalise a /api/settings payload.

    Returns (cleaned, error). On success error is None and cleaned contains
    exactly config.SETTINGS_FIELDS."""
    cleaned = {}

    wo = body.get("wo")
    if not isinstance(wo, str) or not wo.strip():
        return None, "wo darf nicht leer sein"
    cleaned["wo"] = wo.strip()

    try:
        umkreis = int(body.get("umkreis"))
    except (TypeError, ValueError):
        return None, "umkreis muss eine Zahl sein"
    if not (1 <= umkreis <= 200):
        return None, "umkreis muss zwischen 1 und 200 liegen"
    cleaned["umkreis"] = umkreis

    try:
        angebotsart = int(body.get("angebotsart", 1))
    except (TypeError, ValueError):
        return None, "angebotsart muss eine Zahl sein"
    if not (1 <= angebotsart <= 99):
        return None, "angebotsart muss zwischen 1 und 99 liegen"
    cleaned["angebotsart"] = angebotsart

    cleaned["include_zeitarbeit"] = bool(body.get("include_zeitarbeit"))
    cleaned["include_pav"] = bool(body.get("include_pav"))

    exclude_terms = body.get("exclude_terms") or []
    if not isinstance(exclude_terms, list):
        return None, "exclude_terms muss eine Liste sein"
    cleaned["exclude_terms"] = [
        t.strip() for t in exclude_terms if isinstance(t, str) and t.strip()
    ]

    searches = config.normalize_searches(body.get("searches"))
    if not searches:
        return None, "mindestens ein Suchprofil mit Suchbegriff ist erforderlich"
    cleaned["searches"] = searches

    return cleaned, None


class State:
    def __init__(self):
        self.opts = {}
        self.scanning = False
        self.scan_event = threading.Event()
        self.pending_days = None


def create_app(state):
    app = Flask(__name__, static_folder=None)

    @app.get("/")
    def index():
        return send_from_directory(WEB_DIR, "index.html")

    @app.get("/api/jobs")
    def jobs():
        bucket = request.args.get("bucket", "new")
        if bucket not in ("new", "archive", "saved", "hidden"):
            bucket = "new"
        q = request.args.get("q") or None
        search_name = request.args.get("search") or None
        win = int(state.opts.get("new_window_hours", 24))
        try:
            limit = int(request.args.get("limit", 100))
        except ValueError:
            limit = 100
        try:
            offset = int(request.args.get("offset", 0))
        except ValueError:
            offset = 0
        limit = max(1, min(MAX_LIMIT, limit))
        offset = max(0, offset)
        return jsonify(db.fetch(bucket, win, q, search_name, limit, offset))

    @app.post("/api/jobs/<refnr>/status")
    def set_job_status(refnr):
        body = request.get_json(silent=True) or {}
        status = body.get("status")
        if status not in (None, "saved", "hidden"):
            return jsonify({"ok": False, "error": "ungueltiger status"}), 400
        if not db.set_status(refnr, status):
            return jsonify({"ok": False, "error": "nicht gefunden"}), 404
        return jsonify({"ok": True})

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

    @app.get("/api/settings")
    def get_settings():
        return jsonify({k: state.opts.get(k) for k in config.SETTINGS_FIELDS})

    @app.post("/api/settings")
    def update_settings():
        body = request.get_json(silent=True) or {}
        cleaned, error = _validate_settings(body)
        if error:
            return jsonify({"ok": False, "error": error}), 400
        state.opts.update(cleaned)
        db.set_settings_override(cleaned)
        # apply immediately with the new search profiles / location
        state.pending_days = None
        state.scan_event.set()
        return jsonify({"ok": True, "settings": cleaned})

    @app.delete("/api/settings")
    def reset_settings():
        db.clear_settings_override()
        opts = config.load()
        state.opts.update({k: opts.get(k) for k in config.SETTINGS_FIELDS})
        state.scan_event.set()
        return jsonify({"ok": True, "settings": {k: state.opts.get(k) for k in config.SETTINGS_FIELDS}})

    @app.post("/api/scan")
    def scan_now():
        body = request.get_json(silent=True) or {}
        days = body.get("days")
        if days is not None:
            try:
                days = int(days)
            except (TypeError, ValueError):
                return jsonify({"ok": False, "error": "days muss eine Zahl sein"}), 400
            if not (0 <= days <= MAX_SCAN_DAYS):
                return jsonify({
                    "ok": False,
                    "error": f"days muss zwischen 0 und {MAX_SCAN_DAYS} liegen",
                }), 400
            state.pending_days = days
        state.scan_event.set()
        return jsonify({"ok": True})

    return app
