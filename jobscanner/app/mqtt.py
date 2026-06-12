"""Optional MQTT discovery for a 'neue Stellen' sensor.

Connects to the Home Assistant-managed broker via the Supervisor API
(requires `services: - mqtt:want` in config.yaml). Silently does nothing
if MQTT is disabled, paho-mqtt is missing, or no broker is available.
"""

import json
import logging
import os
import threading

import requests

log = logging.getLogger("mqtt")

try:
    import paho.mqtt.client as mqtt_client
except ImportError:  # pragma: no cover - optional dependency
    mqtt_client = None

DISCOVERY_TOPIC = "homeassistant/sensor/jobscanner_new_jobs/config"
STATE_TOPIC = "jobscanner/new_jobs/state"

_client = None
_lock = threading.Lock()
_unavailable = False


def _supervisor_mqtt_service():
    token = os.environ.get("SUPERVISOR_TOKEN")
    if not token:
        return None
    try:
        r = requests.get(
            "http://supervisor/services/mqtt",
            headers={"Authorization": f"Bearer {token}"},
            timeout=5,
        )
        r.raise_for_status()
        return r.json().get("data")
    except Exception:
        log.debug("Kein MQTT-Service ueber Supervisor verfuegbar", exc_info=True)
        return None


def _get_client():
    global _client, _unavailable
    if _client is not None or _unavailable:
        return _client
    with _lock:
        if _client is not None or _unavailable:
            return _client
        if mqtt_client is None:
            log.warning("paho-mqtt nicht installiert - MQTT deaktiviert")
            _unavailable = True
            return None
        info = _supervisor_mqtt_service()
        if not info or not info.get("host"):
            log.warning("Kein MQTT-Broker via Supervisor gefunden - MQTT deaktiviert")
            _unavailable = True
            return None
        c = mqtt_client.Client(client_id="jobscanner")
        if info.get("username"):
            c.username_pw_set(info["username"], info.get("password"))
        try:
            c.connect(info["host"], int(info.get("port", 1883)), keepalive=30)
            c.loop_start()
        except Exception:
            log.exception("MQTT-Verbindung fehlgeschlagen")
            _unavailable = True
            return None
        discovery = {
            "name": "Jobscanner neue Stellen",
            "unique_id": "jobscanner_new_jobs",
            "state_topic": STATE_TOPIC,
            "unit_of_measurement": "Stellen",
            "icon": "mdi:briefcase-search-outline",
        }
        c.publish(DISCOVERY_TOPIC, json.dumps(discovery), retain=True)
        _client = c
    return _client


def publish_new_count(count):
    """Publish the current 'new jobs' count as MQTT sensor state."""
    client = _get_client()
    if client is None:
        return
    try:
        client.publish(STATE_TOPIC, str(count), retain=True)
    except Exception:
        log.exception("MQTT-Publish fehlgeschlagen")
