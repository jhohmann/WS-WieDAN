# STATUS.md

## BIG PROJECT GOAL

WieDAN: Windows-GUI-Werkzeugsammlung (Python) für den Produktlebenszyklus: Fernwartung, Anlagenstatus, Erreichbarkeit, Meldearchiv, Dashboard, Datenlogger (Profile), Inbetriebnahme/Test, Netzwerk-Vorkonfiguration, Konfig-Batch, DHCP/SFTP-Server, Fahrzeug-Erstkonfig, Auto-Tests, Plotting, Datendarstellung, Doku-Export.
Ein gemeinsamer Datenstamm, mehrere schlanke Tools, Rollout an Kollegen.

---

## CURRENT CHRONOLOGICAL STEP

Planung der stabilen Basis (Architektur, Datenstamm, Struktur). Noch kein Code.

---

## CURRENT VERIFIED STATE

- Repo enthält nur AI-AGENT.md und STATUS.md.
- Architektur-Skizze steht (core / features / apps, siehe AI-AGENT.md FILE MAP).
- Entscheidungen siehe VERIFIED FACTS.

---

## CURRENT BLOCKERS

- Entwurf Schema (Hierarchie, Library) wartet auf Bestätigung.

---

## NEXT ACTION

- SPS-Modellierung klären (siehe OFFEN), dann Gerätetypen unter data/library/device_types/ anlegen.

---

## VERIFIED FACTS
(only place grounded/verified truths here)

- Plattform: Windows, GUI.
- Protokolle: SSH, HTTP, Modbus/TCP, Modbus/RTU, optional SNMP. Erweiterbar über Treiber.
- Ein Gerät hat einen festen Kommunikationsweg; Wechsel = neues Gerät anlegen.
- Stammdaten existieren; Import manuell und sauber, nicht automatisiert.
- Ein Datenstamm, keine mehrfache Pflege.
- GUI-Framework: PySide6 (entschieden). Live-Plots: pyqtgraph.
- Tooling: pyproject.toml, pytest, ruff (keine Schema-Validierungsbibliothek). Rollout via pipx oder PyInstaller-EXE.
- Workflows = Abfolge von Jobs. Jede längere Aufgabe (Logger, Batch, Auto-Test, DHCP) ist ein Job mit einheitlichem Status, Abbruch und Ergebnis; GUI und Dashboard lesen denselben Status.
- Treiber haben eine gemeinsame Schnittstelle (connect, read, ping); Features kennen keine Protokolle.
- Ergebnisse liegen als Dateien pro Lauf (Ordner + Metadaten: Bahn, Geräte-IDs, Zeit, Profil), nicht im GUI-Zustand.
- Architektur der Sammlung: ein Paket (Monorepo) mit core + features, gestartet über einen Launcher (entschieden). Mechanismus der Feature-Anmeldung bewusst noch offen.
- Funktionsumfang wächst iterativ; jetzt Fokus auf stabile Basis.
- Reihenfolge: Datenmodell -> Erreichbarkeit -> Logger/Speicher -> Plotting/Export -> Fernwartung/Meldearchiv/Dashboard -> Inbetriebnahme.
- Datenstamm ist projektspezifisch (projects/<id>.yaml; Vorlage: xuzhou.yaml). Gerätetypen/Datenpunkte und Logging-Sets sind projektunabhängig (library/), Neues Projekt = xuzhou.yaml kopieren und anpassen (kein templates/-Ordner).
- Geräte gehören zur Zentrale (central) oder zu genau einem Fahrzeug; Geräte-ID = Pfad (z. B. fzg_03/inverter). Gerätegruppen werden nicht gepflegt, sondern per Abfrage (Typ/Rolle/Ort) gebildet. Logging-Sets referenzieren Typ/Rolle, keine Geräte-IDs (Entwurf, noch zu bestätigen).
- Stammdaten gelten als korrekt, geprüft und unveränderlich: keine Validierung beim Laden, kein Pydantic. YAML wird direkt gelesen (PyYAML), Zugriff über schlanke Dataclasses oder Dicts.
- Auslieferung als .exe (PyInstaller). Stammdaten/Library/Templates liegen unter src/wiedan/data/ und werden mitgepackt (read-only). Laufzeitdaten (Aufnahmen, Ergebnisse, Einstellungen) liegen im Nutzerordner, nicht in der exe. xuzhou.yaml ist als Hierarchie (central/vehicles) unter data/projects/ neu angelegt und dient als Muster; Logging-Sets referenzieren Gerätetyp statt Geräte-IDs.
- Jedes Fahrzeug hat eine SPS HIMatrix F35 (Gerät `plc` im Fahrzeug). Alle Geräte sind pingbar, außer wenn Ping am Gerät deaktiviert ist -> Geräte-Feld `pingable: true/false` (in jedem Gerät explizit); Erreichbarkeit nutzt dann ersatzweise den Verbindungsport bzw. gilt als "nicht prüfbar".
- SPS-Modbus (Ein-/Ausgänge) gibt es nur in der Inbetriebnahme (Inbetriebnahme-Programm auf der SPS). Im Wirkbetrieb/Fernwartung ist die SPS nur pingbar, kein Modbus. Der Zugriffsweg hängt also vom Betriebsmodus (commissioning / operation), nicht vom Gerät.
- OFFEN: Modellierung des Betriebsmodus bei der SPS und ihre IPs (nicht in xuzhou.yaml eingetragen, keine Werte geraten).
- Entschieden: SPS-Variante 1: Gerät hat `connection` (Wirkbetrieb) und optional `commissioning_connection` (Inbetriebnahme). SPS: connection = icmp, commissioning_connection = modbus_tcp. IP SPS = FU-IP - 2.
- Pro Fahrzeug zusätzlich `client` (Typ siemens_scalance_w700), IP = FU-IP - 1. Protokoll vorläufig `icmp` (nur Ping bekannt; Platzhalter, bei Bedarf z. B. HTTP/SNMP ergänzen). Modbus-Port/unit_id der SPS noch nicht eingetragen.
- Entschieden: SPS-Modbus (Inbetriebnahme) wie FU: Port 502, unit_id 0. Clients (siemens_scalance_w700) per SSH, Port 22, Zugang über Projekt-credentials: (Klartext, Eintrag client, Werte noch leer). Geräte verweisen per Name auf einen credentials-Eintrag.
