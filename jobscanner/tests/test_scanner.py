import scanner


def test_parse_maps_fields():
    entry = {
        "refnr": "123-ABC",
        "titel": "Systemadministrator (m/w/d)",
        "arbeitgeber": "ACME GmbH",
        "arbeitsort": {"ort": "Rostock", "plz": "18055", "entfernung": 12.3},
        "aktuelleVeroeffentlichungsdatum": "2026-06-01",
        "eintrittsdatum": "2026-07-01",
        "externeUrl": "https://example.com/job/123",
    }
    job = scanner._parse(entry, "Admin-Suche")
    assert job == {
        "refnr": "123-ABC",
        "title": "Systemadministrator (m/w/d)",
        "employer": "ACME GmbH",
        "ort": "Rostock",
        "plz": "18055",
        "distance": 12.3,
        "published": "2026-06-01",
        "entry_date": "2026-07-01",
        "external_url": "https://example.com/job/123",
        "search_name": "Admin-Suche",
    }


def test_parse_falls_back_to_public_detail_url():
    entry = {"refnr": "456-DEF", "beruf": "IT-Leiter", "arbeitsort": {}}
    job = scanner._parse(entry, "Leitung")
    assert job["title"] == "IT-Leiter"
    assert job["employer"] == "—"
    assert job["external_url"] == scanner.PUBLIC_DETAIL.format(refnr="456-DEF")


def test_is_excluded_matches_title_or_employer_case_insensitively():
    job = {"title": "Sachbearbeiter Zeitarbeit", "employer": "Foo GmbH"}
    assert scanner._is_excluded(job, ["zeitarbeit"])
    assert scanner._is_excluded(job, ["FOO"])
    assert not scanner._is_excluded(job, ["Praktikum"])
    assert not scanner._is_excluded(job, [])
    assert not scanner._is_excluded(job, None)


def test_scan_dedupes_and_applies_exclude_terms(monkeypatch):
    results = {
        "Suche A": [
            {"refnr": "1", "title": "Teamleiter IT", "employer": "ACME"},
            {"refnr": "2", "title": "Zeitarbeit Helfer", "employer": "Foo"},
        ],
        "Suche B": [
            {"refnr": "1", "title": "Teamleiter IT (Duplikat)", "employer": "ACME"},
            {"refnr": "3", "title": "IT Manager", "employer": "Bar"},
        ],
    }

    def fake_search_one(query, wo, umkreis, angebotsart, zeitarbeit, pav, search_name,
                         veroeffentlichtseit=None):
        return results[search_name]

    monkeypatch.setattr(scanner, "search_one", fake_search_one)

    searches = [
        {"name": "Suche A", "query": "Teamleiter IT"},
        {"name": "Suche B", "query": "IT Manager", "exclude": ["Bar"]},
    ]
    jobs = scanner.scan(searches, "Berlin", 50, 1, False, False,
                         exclude_terms=["Zeitarbeit"])
    refnrs = {j["refnr"] for j in jobs}
    # "2" excluded globally (Zeitarbeit), "3" excluded per-search (Bar),
    # "1" kept once despite appearing in both searches
    assert refnrs == {"1"}


def test_scan_skips_searches_without_query():
    jobs = scanner.scan([{}], "Berlin", 50, 1, False, False)
    assert jobs == []
