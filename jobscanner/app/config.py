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
    "exclude_terms": [],
    "mqtt_enabled": False,
    "log_level": "info",
}

# subset of options that can be changed at runtime via /api/settings
SETTINGS_FIELDS = (
    "wo", "umkreis", "angebotsart", "include_zeitarbeit", "include_pav",
    "exclude_terms", "searches",
)


def normalize_searches(searches):
    """Allow plain strings too, with optional per-search exclude list."""
    norm = []
    for s in searches or []:
        if isinstance(s, str):
            norm.append({"name": s, "query": s, "exclude": []})
        elif isinstance(s, dict) and (s.get("query") or s.get("name")):
            norm.append({
                "name": s.get("name") or s.get("query"),
                "query": s.get("query") or s.get("name"),
                "exclude": [x for x in (s.get("exclude") or []) if isinstance(x, str)],
            })
    return norm


def normalize(opts):
    opts["searches"] = normalize_searches(opts.get("searches")) or DEFAULTS["searches"]
    opts["exclude_terms"] = [
        x for x in (opts.get("exclude_terms") or []) if isinstance(x, str)
    ]
    return opts


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

    return normalize(opts)
