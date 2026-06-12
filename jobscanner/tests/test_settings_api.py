import config
import db
import server


def _make_client():
    state = server.State()
    state.opts = config.load()
    app = server.create_app(state)
    return state, app.test_client()


def test_get_settings_returns_current_subset():
    _, client = _make_client()
    body = client.get("/api/settings").get_json()
    assert set(body.keys()) == set(config.SETTINGS_FIELDS)
    assert body["wo"] == config.DEFAULTS["wo"]


def test_post_settings_updates_state_and_persists(fresh_db):
    state, client = _make_client()
    payload = {
        "wo": "Berlin", "umkreis": 30, "angebotsart": 1,
        "include_zeitarbeit": True, "include_pav": False,
        "exclude_terms": ["Praktikum", "  ", 5],
        "searches": [{"name": "Test", "query": "Python Entwickler", "exclude": ["Zeitarbeit"]}],
    }
    r = client.post("/api/settings", json=payload)
    assert r.status_code == 200
    body = r.get_json()
    assert body["ok"] is True
    assert body["settings"]["wo"] == "Berlin"
    assert body["settings"]["exclude_terms"] == ["Praktikum"]

    assert state.opts["wo"] == "Berlin"
    assert state.opts["umkreis"] == 30
    assert state.scan_event.is_set()

    override = db.get_settings_override()
    assert override["wo"] == "Berlin"
    assert override["searches"][0]["query"] == "Python Entwickler"


def test_post_settings_rejects_invalid_values(fresh_db):
    _, client = _make_client()
    base = {
        "wo": "Berlin", "umkreis": 30, "angebotsart": 1,
        "include_zeitarbeit": False, "include_pav": False,
        "exclude_terms": [], "searches": [{"name": "T", "query": "Q"}],
    }

    bad_umkreis = dict(base, umkreis=999)
    r = client.post("/api/settings", json=bad_umkreis)
    assert r.status_code == 400

    bad_wo = dict(base, wo="   ")
    r = client.post("/api/settings", json=bad_wo)
    assert r.status_code == 400

    bad_searches = dict(base, searches=[])
    r = client.post("/api/settings", json=bad_searches)
    assert r.status_code == 400


def test_delete_settings_resets_to_defaults(fresh_db):
    state, client = _make_client()
    client.post("/api/settings", json={
        "wo": "Berlin", "umkreis": 30, "angebotsart": 1,
        "include_zeitarbeit": False, "include_pav": False,
        "exclude_terms": [], "searches": [{"name": "T", "query": "Q"}],
    })
    assert db.get_settings_override()

    r = client.delete("/api/settings")
    assert r.status_code == 200
    assert db.get_settings_override() == {}
    assert state.opts["wo"] == config.DEFAULTS["wo"]
