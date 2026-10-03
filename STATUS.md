# STATUS.md

## BIG PROJECT GOAL

WieDAN: Windows-GUI-Werkzeugsammlung (Python, PySide6) für den Produktlebenszyklus: Fernwartung, Anlagenstatus, Erreichbarkeit, Meldearchiv, Dashboard, Datenlogger (Profile), Inbetriebnahme/Test, Netzwerk-Vorkonfiguration, Konfig-Batch, DHCP/SFTP-Server, Fahrzeug-Erstkonfig, Auto-Tests, Plotting, Datendarstellung, Doku-Export.
Ein gemeinsamer Datenstamm, mehrere schlanke Tools, Verteilung als .exe an Kollegen.

---

## CURRENT CHRONOLOGICAL STEP

Stammdaten-Basis und Hauptfenster-Gerüst (Modus Live mit Explorer, Farbstile) fertig.

---

## CURRENT VERIFIED STATE

- Repo: AGENTS.md, STATUS.md, pyproject.toml, src/wiedan (core/model.py, data/), tests/. 1 Test grün.
- Hauptfenster steht (apps/main_window.py, Start: `wiedan`): Kopfzeile mit Projekt- und Farbstil-Wahl, Activity Bar mit Icons (Live, Inbetriebnahme, Plotter), Seitenleiste, Tab-Bereich, Statusleiste. Live: Projekt-Explorer (Baum, Icons, Doppelklick = Geräte-Tab, Platzhalterinhalt). Inbetriebnahme und Plotter nur Platzhalter. Farbstile hell (Standard), dunkel, pastell (Debug, jeder Bereich andere Farbe), gespeichert in %LOCALAPPDATA%\WieDAN\settings.json. Beide Projekte `live: true`. 3 Tests grün.
- Offen im Explorer: Farbe = Erreichbarkeit (Icons sind vorerst grau).
- Gerätetypen mit Datenpunkten: nidec_m700, bender_iso685. himatrix_f35 und siemens_scalance_w700 ohne Datenpunkte.

---

## CURRENT BLOCKERS

- Keine.

---

## NEXT ACTION

- Nächster Schritt vom Nutzer zu bestimmen (Kandidaten: Erreichbarkeits-Job für den Explorer, Inhalt der Geräte-Datenseite, Modus Inbetriebnahme, Modus Plotter).

## BACKLOG (später)

- Erreichbarkeitsprüfung (Ping/TCP-Port) als Hintergrund-Job, färbt den Explorer; erst an der echten Anlage prüfbar.
- Projektfeld `live` (bool) ist umgesetzt; beide Projekte true.
- Modi Inbetriebnahme (Tool-Browser) und Plotter/Recorder inhaltlich.
- Befehlssuche (Strg+K) bewusst zurückgestellt.
- Logging-Sets: neue Datenpunkte (dc_link_voltage, alarm_state) aufnehmen; Einheit `Vd` in nidec_m700 vermutlich `V`.
- Test: jeder Gerätetyp eines Projekts existiert in der Library; Test für rhigos.
- SPS-Register-Mapping (Ein-/Ausgänge, Inbetriebnahme).
- Netzwerkdaten für Inbetriebnahme/DHCP (Netzmaske, Gateway, MAC, Hostnamen).
- Mechanismus der Feature-Anmeldung am Launcher (bewusst offen).

---

## VERIFIED FACTS
(only place grounded/verified truths here)

**Plattform und Tooling**
- Windows, GUI mit PySide6, Live-Plots mit pyqtgraph. Auslieferung als .exe (PyInstaller).
- pyproject.toml, PyYAML, dev: pytest, ruff. Entwicklung in .venv: `pip install -e .[dev]`, `pytest`.
- Keine Validierung der Stammdaten, kein Pydantic. Sie gelten als korrekt und unveränderlich.
- Dateiänderungen nur über edit/create, Shell nur zum Ausführen (außer ausdrücklich erlaubt).

**Architektur**
- Ein Paket (Monorepo): core + features + apps. Kein getrennter Launcher mehr: ein Hauptfenster mit Modi.
- Treiber mit gemeinsamer Schnittstelle (connect, read, ping); Features kennen keine Protokolle.
- Längere Aufgaben sind Jobs (Status, Abbruch, Ergebnis); Workflows sind Abfolgen von Jobs.
- Ergebnisse als Dateien pro Lauf (Ordner + Metadaten). Laufzeitdaten liegen im Nutzerordner, nicht in der .exe.
- Reihenfolge: Datenmodell -> Erreichbarkeit -> Logger/Speicher -> Plotting/Export -> Fernwartung/Meldearchiv/Dashboard -> Inbetriebnahme.

**Oberfläche (entschieden)**
- Aufbau nach VS-Code-Vorbild: Kopfzeile (aktives Projekt), Activity Bar (Modus), Seitenleiste (Navigator des Modus), Hauptfenster mit Tabs (parallel), Statusleiste (Jobs, Verbindungen).
- Projekt ist immer Kontext; alle Aufnahmen und Meldungen haben Projektbezug. Nur der Projekteditor ändert Stammdaten, alle anderen Werkzeuge lesen nur.
- Modus Live: Seitenleiste = Projekt-Explorer (Baum aller erreichbaren Geräte, kleines Icon pro Gerät, Farbe = Erreichbarkeit). Doppelklick auf ein Gerät öffnet dessen Datenseite als Tab. Live nur möglich, wenn die Projektstammdaten es als realisiert kennzeichnen (Feld `live` auf Projektebene).
- Modus Inbetriebnahme: Seitenleiste = Tool-Browser, Hauptfenster = gewähltes Tool.
- Modus Plotter (zugleich Signal-Recorder, immer mit Projektbezug): Seitenleiste = Kanäle (Farbe, Kurzname, ein/ausblenden, Doppelklick = bearbeiten); Hauptfenster = Plot und Dateneditor als Tabs.
- Live und Logging/Dashboard laufen parallel (Hintergrund-Jobs). Live-Funktionen erzeugen Läufe als Dateien, Offline-Funktionen lesen sie.
- Farbstile: hell (Standard), dunkel, pastell. Pastell färbt jeden Bereich anders und dient dem Nutzer zum Debuggen des Layouts. Farben nur in ui/theme.py.
- Icons: SVG-Linien-Icons in ui/icons.py, in Themefarbe gerendert.
- Mechanismus zur Anmeldung von Modi/Werkzeugen bleibt offen (Modi sind aktuell in apps/main_window.py fest eingetragen).

**Stammdaten**
- `src/wiedan/data/` wird mitgepackt (read-only): `projects/<id>.yaml`, `library/device_types/<typ>.yaml`, `library/logging_sets/`.
- Neues Projekt = bestehendes Projekt kopieren und anpassen (kein templates/-Ordner).
- Hierarchie: `central` und `vehicles`; jedes Gerät gehört zur Zentrale oder zu genau einem Fahrzeug. Geräte-ID = `<fzg_xx|central>/<name>`.
- Projekt-Gerät: Name (individuell) + `type` + `ip`; optional `label`, `pingable`.
- Gerätetyp (Library): label, pingable, connection (Protokoll, Port, unit_id, credentials), optional commissioning_connection, datapoints (Register, Datentyp, Skalierung, Einheit, Intervall).
- Gerätegruppen werden nicht gepflegt, sondern per `Project.find(type, vehicle, central)` abgefragt. Logging-Sets referenzieren Gerätetyp, keine Geräte-IDs.
- Ein Gerät hat einen festen Kommunikationsweg; Wechsel = neues Gerät anlegen.
- Zugangsdaten: projektspezifisch, Klartext im Projekt unter `credentials:`; Geräte verweisen per Name (z. B. `client`). Repo privat halten.

**Fahrzeug-Geräte (je Fahrzeug)**
- `inverter` (nidec_m700, IP x), `plc` (himatrix_f35, IP x-2), `client` (siemens_scalance_w700, IP x-1).
- SPS: Wirkbetrieb nur Ping (`connection: icmp`); Modbus/TCP nur in der Inbetriebnahme (`commissioning_connection`, Port 502, unit_id 0).
- Clients und Access Points: SSH, Port 22, credentials `client`.

**Projekte**
- xuzhou: 4 Isometer in der Zentrale, 20 Fahrzeuge, FU-IPs 192.168.196.22 + 5 pro Fahrzeug.
- rhigos: 2 Isometer (Track 1 .19, Track 2 .17), 16 Access Points ap01..ap16 (.230-.245), 14 Fahrzeuge im selben Schema; credentials client: admin.
