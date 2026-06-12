# Job Scanner – Home Assistant Add-on

Beobachtet die **Jobsuche der Bundesagentur für Arbeit** (größte Stellendatenbank
Deutschlands) und meldet neue Stellen im konfigurierten Umkreis. Mit eigenem
Dashboard über HA-Ingress: ein **Neu**-Tab für frisch entdeckte Treffer und ein
**Archiv** für ältere.

Die Datenquelle ist die inoffizielle, aber öffentlich dokumentierte JSON-API
(`rest.arbeitsagentur.de/jobboerse/jobsuche-service`). Es wird **nicht** auf
StepStone/LinkedIn o. ä. gescraped – das spart rechtlichen Ärger und ist stabil.

## Installation (HA Supervised, via Add-on-Repository)

1. **Einstellungen → Add-ons → Add-on Store → ⋮ (oben rechts) → Repositories**.
2. URL eintragen und mit „Hinzufügen“ bestätigen:

   ```
   https://github.com/fahrstuhl1/job-scanner
   ```

3. Store schließen/neu laden – das Add-on **Job Scanner** erscheint unter
   *Local add-ons* (bzw. unter dem Namen des Repos).
4. Installieren → **Konfiguration** anpassen → **Starten**.
5. Dashboard öffnet sich über den Eintrag **Jobscanner** in der Seitenleiste
   (Ingress, kein Port-Freigeben nötig).

> Erfordert ein Repo mit `repository.yaml` im Root und diesem `jobscanner/`-Ordner
> als Unterverzeichnis (siehe Struktur dieses Pakets). Updates landen über
> normale „Add-on aktualisieren“-Hinweise, sobald neue Commits/Tags im Repo liegen.

### Alternative: manuelles Kopieren

Falls kein Git/Internet-Zugriff vom Supervisor aus möglich ist, den Ordner
`jobscanner/` per Samba/SSH-Add-on nach `/addons/jobscanner/` kopieren und unter
*Lokale Add-ons* „neu laden“.

## Konfiguration

| Option | Bedeutung |
|---|---|
| `wo` | Standort, von dem aus gesucht wird (z. B. `Nienhagen`, PLZ geht auch) |
| `umkreis` | Radius in km (1–200) |
| `searches` | Liste von Suchprofilen, je `name` (Anzeige) + `query` (Suchbegriff für `was`) |
| `angebotsart` | 1=Arbeit, 2=Selbstständigkeit, 4=Ausbildung, 34=Praktikum/Trainee |
| `include_zeitarbeit` | Zeitarbeitsfirmen einbeziehen (Standard: aus) |
| `include_pav` | Private Arbeitsvermittlung einbeziehen (Standard: aus) |
| `poll_interval_minutes` | Scan-Intervall (5–1440) |
| `new_window_hours` | Wie lange ein Treffer als „neu“ gilt (Standard: 24) |
| `prune_after_days` | Treffer löschen, die so lange nicht mehr in Ergebnissen auftauchten |
| `initial_scan_days` | Beim allerersten Scan zusätzlich Stellen abrufen, die bis zu so viele Tage zurückliegen (0 = aus, Standard: 30) |
| `exclude_terms` | Globale Liste von Begriffen; Treffer, deren Titel oder Arbeitgeber einen davon enthalten, werden verworfen |
| `mqtt_enabled` | Veröffentlicht einen Sensor „neue Stellen“ per MQTT-Discovery (benötigt den HA-MQTT-Dienst) |
| `log_level` | trace/debug/info/warning/error |

Beispiel:

```yaml
wo: "Nienhagen"
umkreis: 50
searches:
  - name: "Teamleiter IT-Infrastruktur"
    query: "Teamleiter IT Infrastruktur"
  - name: "IT Infrastructure Manager"
    query: "IT Infrastructure Manager"
  - name: "Leitung Systemadministration"
    query: "Leiter Systemadministration"
    exclude:
      - "Zeitarbeit"
exclude_terms:
  - "Praktikum"
mqtt_enabled: true
```

Jedes Suchprofil kann zusätzlich eine eigene `exclude`-Liste mitbringen, die
zusammen mit den globalen `exclude_terms` angewendet wird (Treffer, deren
Titel oder Arbeitgeber einen der Begriffe enthält – ohne Berücksichtigung
von Groß-/Kleinschreibung –, werden verworfen).

## Wie „Neu“ vs. „Archiv“ funktioniert

Der Scanner merkt sich pro Stelle den Zeitpunkt der **ersten Entdeckung**
(`first_seen`). Solange das jünger als `new_window_hours` ist, steht die Stelle
im **Neu**-Tab; danach wandert sie automatisch ins **Archiv**. Das ist der
eigentliche Scanner-Mehrwert: du siehst, was seit deinem letzten Blick wirklich
neu ist – nicht nur, was die Behörde als „aktuell“ markiert. Beim allerersten
Scan ist erwartungsgemäß alles „neu“.

Jede Karte zeigt zusätzlich das Veröffentlichungsdatum und die Entfernung vom
`wo`-Standort. Der linke Rand der „Neu“-Karten ist umso wärmer (bernsteinfarben),
je frischer der Treffer ist.

Über den Treffern lassen sich die Karten zusätzlich nach Entdeckungsdatum,
Entfernung, Veröffentlichungs- oder Eintrittsdatum sortieren.

### Tiefensuche

Die Jobsuche-API liefert standardmäßig vor allem aktuell veröffentlichte
Stellen. Mit dem Button **„Tiefensuche“** lässt sich gezielt ein Scan
anstoßen, der zusätzlich Stellen der letzten *X* Tage abruft (per Dialog
einstellbar, 0–90 Tage). Beim allerersten Scan passiert das automatisch über
`initial_scan_days`, damit von Anfang an auch ältere, noch offene Stellen
auftauchen.

## Merken & Verstecken

Jede Karte hat zwei Aktionen:

- **☆ Merken / ★ Gemerkt**: legt die Stelle im Tab **Gemerkt** ab (zur
  Wiedervorlage) – gemerkte Stellen werden auch nie automatisch durch
  `prune_after_days` gelöscht.
- **Verstecken**: entfernt die Stelle aus Neu/Archiv/Gemerkt; landet im Tab
  **Versteckt** und kann von dort über „Wiederherstellen“ zurückgeholt werden.

## HA-Benachrichtigung bei neuen Treffern (MQTT)

Mit `mqtt_enabled: true` (und installiertem MQTT-Broker-Add-on, z. B.
Mosquitto) veröffentlicht der Scanner nach jedem Lauf per MQTT-Discovery
einen Sensor **„Jobscanner neue Stellen“** mit der aktuellen Anzahl neuer
Treffer (`new_window_hours`). Darauf lässt sich eine HA-Automation (z. B.
Push-Benachrichtigung bei Anstieg) aufsetzen.

## Daten & Speicher

SQLite unter `/data/jobs.db` (überlebt Add-on-Neustarts/-Updates), inkl.
Indizes auf Entdeckungsdatum, Suchprofil und Status für flotte Abfragen auch
bei vielen Treffern. Die Liste lädt anfangs 100 Treffer und bietet bei Bedarf
einen „Mehr laden“-Button. HTTP-Anfragen an die Jobsuche-API werden bei
vorübergehenden Fehlern automatisch (mit Backoff) wiederholt.

## Mögliche Erweiterungen

- **Radius/Standort pro Suchprofil** statt global.
