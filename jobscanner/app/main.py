import logging

from waitress import serve

import config
import db
import mqtt
import scanner
import server

PORT = 8099


def poller(state):
    log = logging.getLogger("poller")
    first_run = db.meta_get("last_scan") is None
    while True:
        o = state.opts
        days = state.pending_days
        state.pending_days = None
        if days is None and first_run:
            days = int(o.get("initial_scan_days", 30)) or None
        try:
            state.scanning = True
            jobs = scanner.scan(
                o["searches"], o["wo"], o["umkreis"],
                o.get("angebotsart", 1),
                o.get("include_zeitarbeit", False),
                o.get("include_pav", False),
                veroeffentlichtseit=days,
                exclude_terms=o.get("exclude_terms"),
            )
            new = db.upsert(jobs)
            removed = db.prune(int(o.get("prune_after_days", 45)))
            db.meta_set("last_scan", db.now_iso())
            if o.get("mqtt_enabled"):
                win = int(o.get("new_window_hours", 24))
                mqtt.publish_new_count(db.stats(win)["new"])
            if days is not None:
                log.info("Scan fertig (letzte %d Tage): %d gesehen, %d neu, %d entfernt",
                         days, len(jobs), new, removed)
            else:
                log.info("Scan fertig: %d gesehen, %d neu, %d entfernt",
                         len(jobs), new, removed)
        except Exception as ex:  # noqa: BLE001
            log.exception("Scan-Fehler: %s", ex)
        finally:
            state.scanning = False
            first_run = False

        interval = int(o.get("poll_interval_minutes", 60)) * 60
        if state.scan_event.wait(timeout=interval):
            state.scan_event.clear()


def main():
    opts = config.load()
    level = getattr(logging, str(opts.get("log_level", "info")).upper(),
                    logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logging.getLogger("waitress").setLevel(logging.WARNING)

    db.init()
    override = db.get_settings_override()
    if override:
        opts.update(override)
        opts = config.normalize(opts)
    state = server.State()
    state.opts = opts

    import threading
    threading.Thread(target=poller, args=(state,), daemon=True).start()

    logging.getLogger("main").info(
        "Jobscanner laeuft auf Port %d - Standort %s, Umkreis %s km, %d Suchen",
        PORT, opts.get("wo"), opts.get("umkreis"), len(opts.get("searches", [])))
    serve(server.create_app(state), host="0.0.0.0", port=PORT, threads=8)


if __name__ == "__main__":
    main()
