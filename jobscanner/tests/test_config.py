import json

import config


def test_load_defaults_when_no_options_file(tmp_path, monkeypatch):
    monkeypatch.setenv("OPTIONS_PATH", str(tmp_path / "missing.json"))
    opts = config.load()
    assert opts["wo"] == config.DEFAULTS["wo"]
    assert opts["umkreis"] == config.DEFAULTS["umkreis"]
    assert opts["exclude_terms"] == []
    assert opts["mqtt_enabled"] is False


def test_load_merges_user_options(tmp_path, monkeypatch):
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"wo": "Berlin", "umkreis": 25}), encoding="utf-8")
    monkeypatch.setenv("OPTIONS_PATH", str(path))
    opts = config.load()
    assert opts["wo"] == "Berlin"
    assert opts["umkreis"] == 25
    # untouched defaults remain
    assert opts["poll_interval_minutes"] == config.DEFAULTS["poll_interval_minutes"]


def test_normalises_string_searches(tmp_path, monkeypatch):
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"searches": ["Python Entwickler"]}), encoding="utf-8")
    monkeypatch.setenv("OPTIONS_PATH", str(path))
    opts = config.load()
    assert opts["searches"] == [
        {"name": "Python Entwickler", "query": "Python Entwickler", "exclude": []}
    ]


def test_normalises_dict_searches_with_exclude(tmp_path, monkeypatch):
    path = tmp_path / "options.json"
    path.write_text(json.dumps({
        "searches": [
            {"name": "Admin", "query": "Systemadministrator", "exclude": ["Zeitarbeit", 123]},
            {"query": "Onlyquery"},
            {"name": "OnlyName"},
        ],
    }), encoding="utf-8")
    monkeypatch.setenv("OPTIONS_PATH", str(path))
    opts = config.load()
    assert opts["searches"][0] == {
        "name": "Admin", "query": "Systemadministrator", "exclude": ["Zeitarbeit"],
    }
    assert opts["searches"][1] == {"name": "Onlyquery", "query": "Onlyquery", "exclude": []}
    assert opts["searches"][2] == {"name": "OnlyName", "query": "OnlyName", "exclude": []}


def test_empty_searches_fall_back_to_default(tmp_path, monkeypatch):
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"searches": []}), encoding="utf-8")
    monkeypatch.setenv("OPTIONS_PATH", str(path))
    opts = config.load()
    assert opts["searches"] == config.DEFAULTS["searches"]


def test_exclude_terms_filters_non_strings(tmp_path, monkeypatch):
    path = tmp_path / "options.json"
    path.write_text(json.dumps({"exclude_terms": ["Zeitarbeit", 5, None, "Praktikum"]}),
                     encoding="utf-8")
    monkeypatch.setenv("OPTIONS_PATH", str(path))
    opts = config.load()
    assert opts["exclude_terms"] == ["Zeitarbeit", "Praktikum"]


def test_invalid_json_falls_back_to_defaults(tmp_path, monkeypatch):
    path = tmp_path / "options.json"
    path.write_text("not json", encoding="utf-8")
    monkeypatch.setenv("OPTIONS_PATH", str(path))
    opts = config.load()
    assert opts["wo"] == config.DEFAULTS["wo"]
