import json
import os

DEFAULTS = {
    "wo": "Nienhagen",
    "umkreis": 50,
    "searches": [
        {"name": "Teamleiter IT-Infrastruktur", "query": "Teamleiter IT Infrastruktur"},
    ],
    "angebotsart": 1,
    "include_zeitarbeit": False,
    "include_pav": False,
    "poll_interval_minutes": 60,
    "new_window_hours": 24,
    "prune_after_days": 45,
    "initial_scan_days": 30,
    "log_level": "info",
}


def load():
    """Load add-on options from /data/options.json, fall back to defaults."""
    path = os.environ.get("OPTIONS_PATH", "/data/options.json")
    opts = dict(DEFAULTS)
    try:
        with open(path, encoding="utf-8") as f:
            user = json.load(f)
        opts.update({k: v for k, v in user.items() if v is not None})
    except FileNotFoundError:
        pass
    except (ValueError, OSError):
        pass

    # normalise searches: allow plain strings too
    norm = []
    for s in opts.get("searches") or []:
        if isinstance(s, str):
            norm.append({"name": s, "query": s})
        elif isinstance(s, dict) and (s.get("query") or s.get("name")):
            norm.append({"name": s.get("name") or s.get("query"),
                         "query": s.get("query") or s.get("name")})
    opts["searches"] = norm or DEFAULTS["searches"]
    return opts
