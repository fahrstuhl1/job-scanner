import logging

import requests

log = logging.getLogger("scanner")

BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
HEADERS = {
    "X-API-Key": "jobboerse-jobsuche",
    "User-Agent": "ha-jobscanner/1.0",
    "Accept": "application/json",
}
PUBLIC_DETAIL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"
MAX_PAGES = 6
PAGE_SIZE = 100


def _parse(e, search_name):
    ort = e.get("arbeitsort") or {}
    refnr = e.get("refnr")
    return {
        "refnr": refnr,
        "title": e.get("titel") or e.get("beruf") or "Ohne Titel",
        "employer": e.get("arbeitgeber") or "—",
        "ort": ort.get("ort"),
        "plz": ort.get("plz"),
        "distance": ort.get("entfernung"),
        "published": e.get("aktuelleVeroeffentlichungsdatum"),
        "entry_date": e.get("eintrittsdatum"),
        "external_url": e.get("externeUrl") or (
            PUBLIC_DETAIL.format(refnr=refnr) if refnr else None),
        "search_name": search_name,
    }


def search_one(query, wo, umkreis, angebotsart, zeitarbeit, pav, search_name,
                veroeffentlichtseit=None):
    found = {}
    for page in range(1, MAX_PAGES + 1):
        params = {
            "was": query,
            "wo": wo,
            "umkreis": umkreis,
            "angebotsart": angebotsart,
            "page": page,
            "size": PAGE_SIZE,
            "zeitarbeit": "true" if zeitarbeit else "false",
            "pav": "true" if pav else "false",
        }
        if veroeffentlichtseit is not None:
            params["veroeffentlichtseit"] = veroeffentlichtseit
        r = requests.get(BASE, headers=HEADERS, params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        items = data.get("stellenangebote") or []
        for e in items:
            if e.get("refnr"):
                found[e["refnr"]] = _parse(e, search_name)
        max_n = data.get("maxErgebnisse") or 0
        if len(items) < PAGE_SIZE or page * PAGE_SIZE >= max_n:
            break
    return list(found.values())


def scan(searches, wo, umkreis, angebotsart, zeitarbeit, pav,
         veroeffentlichtseit=None):
    """Run every configured search; dedupe across searches (first match wins)."""
    all_jobs = {}
    for s in searches:
        query = s.get("query") or s.get("name")
        name = s.get("name") or query
        if not query:
            continue
        try:
            for j in search_one(query, wo, umkreis, angebotsart,
                                zeitarbeit, pav, name, veroeffentlichtseit):
                all_jobs.setdefault(j["refnr"], j)
            log.debug("Suche '%s': %d Treffer (kumuliert %d)",
                      name, len(all_jobs), len(all_jobs))
        except Exception as ex:  # noqa: BLE001 - keep scanning other searches
            log.error("Suche '%s' fehlgeschlagen: %s", name, ex)
    return list(all_jobs.values())
