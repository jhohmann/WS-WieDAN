# STATUS.md

## BIG PROJECT GOAL

WieDAN: Windows-GUI-Werkzeugsammlung (Python, PySide6) für den Produktlebenszyklus: Fernwartung, Anlagenstatus, Erreichbarkeit, Meldearchiv, Dashboard, Datenlogger (Profile), Inbetriebnahme/Test, Netzwerk-Vorkonfiguration, Konfig-Batch, DHCP/SFTP-Server, Fahrzeug-Erstkonfig, Auto-Tests, Plotting, Datendarstellung, Doku-Export.
Ein gemeinsamer Datenstamm, mehrere schlanke Tools, Verteilung als .exe an Kollegen.

---

## CURRENT CHRONOLOGICAL STEP

Zahlenfelder verwenden eigene kontrastreiche Hoch-/Runter-Pfeile für hellen
und dunklen Stil sowie getrennte Schaltflächen rechts im Feld, unabhängig
von nativen Windows-Pfeilen. Keine Tests oder GUI-Laufzeitprüfung ausgeführt.

HIMA-Ringbuffer: Adressbelegung in das mitgelieferte Profil DEBUG Ringbuffer V1
ausgelagert. Im Tool nur noch aufklappbare Adressübersicht; Wartezeit weiterhin
einstellbar. Separate Offline-Hilfe mit Inhaltsverzeichnis und Suche ergänzt.
Abschnitte für Modbus- und Baustein-Parametrierung vorbereitet; Screenshots und
konkrete Einstellfeld-Erläuterungen fehlen noch. Keine Tests ausgeführt.

HIMA-Auslesung vom Benutzer als funktionsfähig bestätigt. CSV-Export des
vollständigen sortierten Datensatzes ergänzt: 1000 Zeilen, Triggerzyklus,
Pufferadresse, Zeit und acht Kanäle; Semikolon und UTF-8 mit BOM.
Speichern-Dialog mit Fehlerbehandlung und atomarem Schreiben. Keine Tests ausgeführt.

HIMA-Timeout-Diagnose ergänzt: Antwort-Timeout separat einstellbar (1–30 s,
Standard 5 s), Fehler mit Sample/ReadIndex, Register, Schreib-/Leseschritt,
Funktionscode, Unit-ID und Übertragungsphase. Ursache des gemeldeten Timeouts
beim Auslesen noch nicht bestätigt; keine Tests oder SPS-Verbindung ausgeführt.

HIMA-Ringbuffer als projektunabhängiges Tool ergänzt: konfigurierbare
Modbus-Schnittstelle, automatische Auslesung von 1000 Samples mit acht Kanälen
und Zeit, Fortschritt/Abbruch und zyklische Sortierung mit 100 Posttriggerzyklen.
Lesebelegung vorbelegt: Zeit 0, Kanäle 1–8, Triggerposition 9 (Werte ab 0),
Wartezeit 50 ms. Reset manuell als Impuls 1 → 0 (vorläufig 50 ms Impulsdauer).
ReadIndex auf Register 0 mit FC16, Reset auf Coil 0 mit FC05; kein Index-Rücklesen.
Projektunabhängige Tools bleiben ohne ausgewähltes Projekt verfügbar;
Details in `docs/hima-ringbuffer.md`. Syntax geprüft, keine Tests
und keine SPS-Verbindung ausgeführt.

Engineering-Einstiege in die Einstellungen verlegt; Modus und Menü im Hauptfenster
entfernt. Projekteditor als separates Fenster mit eigener Projektauswahl,
Gerätekatalog und Stammdateneditor als getrennte Dialoge. Gemeinsame Symbole für
Live- und Projektbaum; allgemeine Nodes mit neuem Struktursymbol. Kategorieansicht
bleibt umschaltbar und sortiert alphabetisch. Direkter Scalance-Menüeintrag zur
Stammdatenübernahme entfernt. Keine Tests ausgeführt; statische Prüfung ohne Befund.

Dokumentationsfelder ergänzt: Definition je Gerätetyp im Gerätekatalog (Text,
Zahl, Ja/Nein), individuelle Werte im Projekteditor. Format 4 ergänzt Definitionen
und Werte mit stabilen Feld-UUIDs. Migration mit Sicherung beim ersten Speichern.
Strecken-Nullpunkt und allgemeine Einbauposition aus der Bearbeitung entfernt;
Beginn/Ende RCoax in Metern ausschließlich bei ausdrücklich gewählter Rolle
Access Point. Streckenmodellierung bleibt zurückgestellt. Keine Tests ausgeführt;
Syntax und gezielte statische Prüfung ohne Befund, GUI-Laufzeitprüfung offen.

Engineering / Planung ergänzt: Projekteditor mit Neuanlage, allgemeinen Nodes,
Geräten aus dem Katalog, Eigenschaften, Umordnung und Kategorieansicht.
Stammdatenänderungen werden direkt in SQLite gespeichert. Format 3 ergänzt
relationale Kategorien; ältere Datenbanken werden erst beim Speichern mit
vorheriger Sicherung migriert. UUIDs bleiben bestehen. Details: `docs/engineering.md`.
Keine Tests ausgeführt; Syntax und gezielte statische Prüfung ohne Befund.
GUI-Bedienung und Speichern/Migration sind noch nicht zur Laufzeit geprüft.
Freigaben, Serviceabgleich und allgemeine Konfigurationsrevisionen bleiben spätere Schritte.
Die folgenden älteren Notizen beschreiben teilweise überholte Zwischenstände.

Stammdaten auf eine gemeinsame lokale SQLite-Datenbank umgestellt. Der ursprüngliche
YAML-Bestand ist unter `archive/yaml-data-2026-10-18/` archiviert; die Anwendung liest
ausschließlich SQLite. Details und Verteilung: `docs/sqlite.md`. Scalance-Entwürfe
bleiben vorläufig separate lokale Arbeitsdaten. Die nachfolgenden älteren
Funktionsnotizen dokumentieren den bisherigen Ausbau, keine aktuellen Testläufe.

---

## CURRENT VERIFIED STATE

- Theme: Hell verwendet #50AF47 als Akzent und #004F38 für Statusleiste, primäre Aktionen und lesbare grüne Texte. Weiße Eingaben, graugrüne Nebenflächen und abgestimmte Auswahl-, Hover-, Rahmen- und Fehlerfarben. Alle Farben zentral in ui/theme.py, spätere CD-Anpassung dort möglich.
- Themewechsel setzt zusätzlich zum Stylesheet eine Qt-Palette, damit native Eingaben, Dropdowns, Pfeile und Scrollleisten nicht vom Windows-Farbstil abhängen. Text-/Zahlenfelder, Auswahllisten, Buttons und Gruppenrahmen mit expliziten Styles einschließlich Fokus und deaktivierten Zuständen; Fehlerrahmen behalten die Feldgröße. Darkmode- und Pastellpalette ergänzt; primäre Buttons haben eine eigene kontrastreiche Textfarbe.
- Repo: AGENTS.md, STATUS.md, pyproject.toml, src/wiedan (core/model.py, data/), tests/. 1 Test grün.
- Hauptfenster steht (apps/main_window.py, Start: `wiedan`): Kopfzeile mit Projekt- und Farbstil-Wahl, Activity Bar mit Icons (Live, Inbetriebnahme, Plotter), Seitenleiste, Tab-Bereich, Statusleiste. Live: Projekt-Explorer (Baum, Icons, Doppelklick = Geräte-Tab, Platzhalterinhalt). Inbetriebnahme und Plotter nur Platzhalter. Farbstile hell (Standard), dunkel, pastell (Debug, jeder Bereich andere Farbe), gespeichert in %LOCALAPPDATA%\WieDAN\settings.json. Beide Projekte `live: true`. 3 Tests grün.
- Explorer: Icon + Text farbig nach Ping-Status (grün/rot/neutral). Ping-Einträge: Aktionen-Menü "Alle Geräte anpingen" (Projekt), Rechtsklick auf Zentrale/Fahrzeug "Alle Geräte anpingen", auf Gerät "Gerät anpingen". Fahrzeuge per Rechtsklick "Inaktiv setzen" (nur Session, ausgegraut, nicht mehr an Live-Aktionen beteiligt). Deaktivierte Menüpunkte sind ausgegraut.
- Bekannt: Ping-Task (QRunnable) liegt noch in features/live.py; Job-Schicht später.
- Stammdaten-Hierarchie: Projekt (`control: HIMA`, `product: CoasterKart|WieFlyer|Bobkart`, pro Fahrzeug überschreibbar) -> Fahrzeuge -> Geräte. Gerätetypen haben `category` (inverter, plc, comms, io). Icons: Fahrzeug nach Produkttyp (`ui/svg/<produkt>.svg`), Gerät nach Kategorie, Ersatz `vehicle` bzw. `device`. Projekt-Icon: Riesenrad.
- Gerätetypen mit Datenpunkten: nidec_m700, bender_iso685. himatrix_f35 und siemens_scalance_w700 ohne Datenpunkte.
- Gerätetypen CK Ulsan (`himatrix_remote_io`, `beckhoff_kl`, `windows_pc`, `siemens_sentron`, `siemens_x200`): Protokoll icmp, ohne Datenpunkte.
- Explorer: Gruppen (Zentrale/Fahrzeug) grün, wenn alle pingbaren Geräte erreichbar, rot bei mindestens einem Ausfall (klappt dann bis zum Gerät auf). Ping-Ergebnisse erscheinen pro Gerät, während der Prüfung Spinner statt Icon. Spinner und "Alles einklappen" neben dem Explorer-Titel.
- Inbetriebnahme: `features/commissioning.py` ist die Tool-Registry (`TOOLS`, Eintrag = Tool). App-Kacheln in der Seitenleiste (`ui/tool_tile.py`): großes Icon links in Akzentfarbe, Titel und Kurzbeschreibung rechts daneben, linksbündig. Modbus-Kachel: „Modbus Browser“, darunter „schreiben und lesen über Modbus/TCP“. Echte, per Tastatur bedienbare Buttons; aktives Tool bleibt über eine exklusive Auswahl markiert. Hover/Fokus/Auswahl mit gleichbleibender Rahmenstärke. Werkzeug im Hauptbereich, je Tool einmal erzeugt und behalten. Neues Tool = Eintrag in `TOOLS`.
- Modbus-Browser (`features/modbus_browser.py`, `core/modbus.py`): projektunabhängig, Modbus/TCP-Lesen wahlweise FC03 (Holdingregister) oder FC02 (Discrete Inputs), Unit-ID fest 0. FC03-Abfragen: Name, Adresse (0-basiert), Offset (Bitposition 0–31, LSB = 0), Bitlänge (1–32, Offset + Bitlänge höchstens 32). Je nach Bitbereich ein oder zwei aufeinanderfolgende Register; Wortfolge Hi-Lo/Lo-Hi je Abfrage. FC02-Abfragen: Startadresse und 1–32 aufeinanderfolgende Eingänge in der GUI; Offset/Wortfolge deaktiviert. Startadresse entspricht Bit 0 des Ergebnisses (rechts in der Binäranzeige). Treiber unterstützt FC02 bis 2000 Eingänge. Ergebnisse gleichzeitig als vorzeichenlose Dezimalzahl, Hex (0x) und Binär in Vierergruppen, mit führenden Nullen. Tabelle zeigt auch den Funktionscode. Polling im Hintergrund (QThreadPool), eine Abfrage gleichzeitig, Intervall 500 ms Standard.
- Eigener minimaler Modbus-Client statt `pymodbus`: keine Abhängigkeitsänderung.
- Modbus-Browser: Abfragen und Ergebnis-Cache über `(Funktion, Adresse, Anzahl)` getrennt, auch bei identischen Adressen für FC02 und FC03. Der frühere Entpackfehler im Poll-Worker ist korrigiert.
- Modbus-Browser: auf Nutzerwunsch Schreibbereich für vollständige 16-/32-Bit-Registerwerte, Dezimal-/0x-Hex-Eingabe und Wortfolge bei 32 Bit ergänzt. Zeilenauswahl übernimmt die Adresse; Offset und Bitlänge gelten nur beim Lesen. Vorhandene Treiberfunktionen 0x06/0x10 verwendet; Lesen und Schreiben laufen nacheinander im Hintergrund. Rückmeldung bestätigt die Geräteantwort, keinen Wertevergleich. Keine automatischen Schreibwiederholungen.
- Modbus-Browser: Schreibfunktion wahlweise Holdingregister (FC06/FC16) oder Coils (FC15 = 0x0F). FC15: 1–1968 Werte als 0/1-Folge, Leerzeichen erlaubt, linke Ziffer gehört zur Startadresse, weitere Ziffern zu aufsteigenden Coil-Adressen. Nicht passende Registeroptionen werden ausgeblendet. FC02-Zeilenauswahl übernimmt kein Schreibziel, da Discrete Inputs nur lesbar sind. Aufträge speichern Funktion, Adresse, Werte und Bestätigungstext vor dem Start; Hinweise/Fehler bleiben in der Hauptfenster-Infozeile. Adressbereiche werden in GUI und Treiber auf 0–65535 begrenzt. FC15-Geräteantwort auf Startadresse und Anzahl geprüft; kein Coil-Rücklesen (FC01 nicht implementiert).
- Modbus-Browser: Name und Werte (Dezimal, Hex, Binär) stehen nebeneinander und sind fett gesetzt; Wertspalten passen sich dem Inhalt an, Adress-/Bitangaben folgen kompakt. Farben bleiben in ui/theme.py.
- Darkmode: Nur Fensterhintergrund #121b16 (eigener Theme-Schlüssel `window`, nur für QMainWindow). Hauptfläche #1e1e1e, Seitenleiste #252526, Activity Bar #333333 und Kachelflächen #181818 wieder wie zuvor. Zentral in ui/theme.py gepflegt; Hell/Pastell unverändert dargestellt.
- Darkmode: Haupttext #dddddd statt #cccccc, sekundäre Texte #a0a0a0 statt #858585 für mehr Schriftkontrast.
- Tool-Lesbarkeit: Im vorgefundenen Darkmode war `muted` auf #050404 geändert; auf #a0a0a0 zurückgesetzt. Kacheltexte verwenden ausdrücklich die Theme-Textfarben, Icons die Akzentfarbe. Aktuelle weitere Farbanpassungen (u. a. Darkmode-Akzent #50AF47 und Statusleiste #004F38) beibehalten.
- Modbus-Verbindungsbutton: Normal-, Fokus- und Fehlerzustand verwenden denselben 2-px-Rahmen und Innenabstand; bei Markierung ändert sich nur die Rahmenfarbe. Breite wird nach Anwendung des Styles anhand der längeren Beschriftung „Verbinden“ festgelegt und bleibt bei „Trennen“ gleich. Styles zentral in ui/theme.py.
- Modbus-Browser: Schreibbutton bei leerem/ungültigem Wert und fehlender Verbindung anklickbar. Beim Klick werden betroffene Eingabe bzw. Verbindungsbutton markiert und fokussiert; Hinweise, Schreibbestätigung und Fehler gehen per Qt-Signal über CommissioningArea an MainWindow.log (Infozeile). Eingaben bleiben beim Verbinden erhalten; kein automatisches Schreiben nach Verbindungsaufbau. Während eines ausstehenden/laufenden Schreibauftrags sind Button und Schreibfelder gesperrt, ohne „Schreibt …“-Anzeige. Lokale Schreib-Hinweiszeile entfernt; wiederholte gleiche Pollingfehler überschreiben die Infozeile nicht ständig.

---

## CURRENT BLOCKERS

- Keine.

---

## NEXT ACTION

- Nutzer prüft Hell/Dunkel/Hell im Modbus-Browser: Text- und Zahlenfelder, Dropdowns samt Auswahllisten, Fokus per Tab, deaktivierte Felder, Fehlerrahmen und Schreibbutton. Theme-Datei Ruff-fehlerfrei; main_window.py weiterhin mit den bereits dokumentierten I001-/DTZ005-Hinweisen. Keine Tests durch Agent ausgeführt, Sichtprüfung offen.
- Nutzer prüft FC02 (einzeln und mehrere Eingänge, auch über Bytegrenzen) zusammen mit FC03 sowie FC15 (0/1-Folge über Bytegrenzen, nicht durch acht teilbare Anzahl, Gerätefehler). Ruff für Treiber und Browser fehlerfrei; keine Tests durch Agent ausgeführt. Protokollgrundlage: Modbus Application Protocol V1.1b3, Abschnitte 6.2 und 6.11 (https://www.modbus.org/file/secure/modbusprotocolspecification.pdf).
- Nutzer prüft Tool-Kacheln im Darkmode und beim Themewechsel: Textkontrast, ausgewählte Kachel, Maus- und Tastaturbedienung (Tab/Leertaste). Ruff für Kachel, Tool-Browser und Theme fehlerfrei; keine Tests durch Agent ausgeführt.
- Nutzer prüft Schreibworkflow: leerer/ungültiger Wert, fehlende Verbindung, Eingaben beim Verbinden behalten, erneuter bewusster Schreibklick, Rückmeldung in Infozeile. Keine Tests durch Agent ausgeführt. Ruff: Feature-/Theme-Dateien ohne Befund; in main_window.py bestehen Importformatierung (I001) und Zeitzonenhinweis (DTZ005) bereits zuvor.
- Nutzer prüft 32-Bit-Leseabfragen (Offset 0, Bitlänge 32, Hi-Lo/Lo-Hi) sowie Schreibbereich und Darstellung: 16-/32-Bit-Werte, Dezimal-/Hex-Eingabe und Fehlerrückmeldung. Zeilenauswahl übernimmt jetzt auch Registeranzahl und Wortfolge in den Schreibbereich. Keine Tests durch Agent ausgeführt.
- Modbus-Browser an echter Anlage bzw. Simulator prüfen (Adressierung 0-basiert, Unit-ID 0 bei Gateways unbestätigt).

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
- Stammdatenbank wird vor der Verwendung auf Format, Integrität und Beziehungen geprüft; App-Zugriff nur lesend.
- Dateiänderungen nur über edit/create, Shell nur zum Ausführen (außer ausdrücklich erlaubt).

**Architektur**
- Ein Paket (Monorepo): core + features + apps. Kein getrennter Launcher mehr: ein Hauptfenster mit Modi.
- Treiber mit gemeinsamer Schnittstelle (connect, read, ping); Features kennen keine Protokolle.
- Längere Aufgaben sind Jobs (Status, Abbruch, Ergebnis); Workflows sind Abfolgen von Jobs.
- Ergebnisse als Dateien pro Lauf (Ordner + Metadaten). Laufzeitdaten liegen im Nutzerordner, nicht in der .exe.
- Reihenfolge: Datenmodell -> Erreichbarkeit -> Logger/Speicher -> Plotting/Export -> Fernwartung/Meldearchiv/Dashboard -> Inbetriebnahme.

**Oberfläche (entschieden)**
- Aufbau nach VS-Code-Vorbild: Kopfzeile (aktives Projekt), Activity Bar (Modus), Seitenleiste (Navigator des Modus), Hauptfenster mit Tabs (parallel), Statusleiste (Jobs, Verbindungen).
- Projekt ist immer Kontext; alle Aufnahmen und Meldungen haben Projektbezug. Stammdatenpflege gehört derzeit nicht zur Anwendung.
- Modus Live: Seitenleiste = Projekt-Explorer (Baum aller erreichbaren Geräte, kleines Icon pro Gerät, Farbe = Erreichbarkeit). Doppelklick auf ein Gerät öffnet dessen Datenseite als Tab. Live nur möglich, wenn die Projektstammdaten es als realisiert kennzeichnen (Feld `live` auf Projektebene).
- Modus Inbetriebnahme: Seitenleiste = Tool-Browser, Hauptfenster = gewähltes Tool.
- Modus Plotter (zugleich Signal-Recorder, immer mit Projektbezug): Seitenleiste = Kanäle (Farbe, Kurzname, ein/ausblenden, Doppelklick = bearbeiten); Hauptfenster = Plot und Dateneditor als Tabs.
- Live und Logging/Dashboard laufen parallel (Hintergrund-Jobs). Live-Funktionen erzeugen Läufe als Dateien, Offline-Funktionen lesen sie.
- Farbstile: hell (Standard), dunkel, pastell. Pastell färbt jeden Bereich anders und dient dem Nutzer zum Debuggen des Layouts. Farben nur in ui/theme.py.
- Icons: SVG-Linien-Icons in ui/icons.py, in Themefarbe gerendert.
- Mechanismus zur Anmeldung von Modi/Werkzeugen bleibt offen (Modi sind aktuell in apps/main_window.py fest eingetragen).

**Stammdaten**
- `src/wiedan/data/stammdaten.sqlite` enthält alle Projekte, Typen, Logging-Vorlagen und Bilder. Beim ersten Start wird eine lokale Kopie bereitgestellt; vorhandene Datenstände bleiben erhalten.
- Datenstände werden als vollständige SQLite-Datei verteilt und lokal ausgewählt. Keine Einzelprojektdateien; keine YAML-Stammdatenpflege.
- Hierarchie: `central` und `vehicles`; jedes Gerät gehört zur Zentrale oder zu genau einem Fahrzeug. Geräte-ID = `<fzg_xx|central>/<name>`.
- Projekt-Gerät: Name (individuell) + `type` + `ip`; optional `label`, `pingable`.
- Gerätetyp (Library): label, pingable, connection (Protokoll, Port, unit_id, credentials), optional commissioning_connection, datapoints (Register, Datentyp, Skalierung, Einheit, Intervall).
- Gerätegruppen werden nicht gepflegt, sondern per `Project.find(type, vehicle, central)` abgefragt. Logging-Sets referenzieren Gerätetyp, keine Geräte-IDs.
- Ein Gerät hat einen festen Kommunikationsweg; Wechsel = neues Gerät anlegen.
- Zugangsdaten: projektspezifisch in der Tabelle `credentials`; Geräte verweisen per Name (z. B. `client`). Datenbank ist nicht verschlüsselt.

**Fahrzeug-Geräte (je Fahrzeug)**
- `inverter` (nidec_m700, IP x), `plc` (himatrix_f35, IP x-2), `client` (siemens_scalance_w700, IP x-1).
- SPS: Wirkbetrieb nur Ping (`connection: icmp`); Modbus/TCP nur in der Inbetriebnahme (`commissioning_connection`, Port 502, unit_id 0).
- Clients und Access Points: SSH, Port 22, credentials `client`.

**Projekte**
- xuzhou: 4 Isometer in der Zentrale, 20 Fahrzeuge, FU-IPs 192.168.196.22 + 5 pro Fahrzeug.
- rhigos: 2 Isometer (Track 1 .19, Track 2 .17), 16 Access Points ap01..ap16 (.230-.245), 14 Fahrzeuge im selben Schema; credentials client: admin.
