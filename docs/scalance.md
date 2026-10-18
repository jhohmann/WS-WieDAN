# Scalance: Arbeiten in der Tabelle

Unter **Inbetriebnahme → Siemens → Scalance Config Generator** werden
Gerätekonfigurationen ohne angeschlossene Hardware geplant. Jedes Projektgerät
hat eine Zeile; die Parameter stehen in Spalten. Gerätezuordnung und Projekt-IP
sind schreibgeschützt. Vorerst lassen sich W700 bearbeiten. Switches bleiben als
„Noch nicht unterstützt“ sichtbar; bestehende Switch-Datensätze bleiben erhalten.

## Bearbeiten

- Eine Zelle doppelt anklicken oder mit der Tastatur bearbeiten. Die erste Vorgabe
  legt die Gerätekonfiguration an; ein gesondertes Anlegen ist nicht nötig.
- **Spalten** blendet weitere Parameter ein. Das Ein-/Ausblenden ändert keine Daten.
- Mehrere Zellen einer Parameterspalte markieren und **Wert setzen** verwenden.
  Alternativ einen einzelnen Wert kopieren und mit **Strg+V** in die Auswahl einfügen.
- Rechteckige Bereiche aus Excel mit **Strg+V** einfügen. Eine einzelne Zielzelle
  bestimmt die linke obere Ecke; eine größere Auswahl muss genau zum Bereich passen.
  Ausgeblendete Zeilen und Spalten werden übersprungen. Ein Bereich, der nicht passt
  oder schreibgeschützte Zellen trifft, wird vollständig abgewiesen.
- **Strg+C** kopiert den markierten Bereich zurück nach Excel.
- **Entf** entfernt die Vorgaben aus den markierten Parameterzellen.
  Eine leere Zelle bedeutet „keine eigene Vorgabe“. Werden alle Vorgaben entfernt,
  hat das Gerät wieder keine Konfiguration.
- **Rückgängig / Wiederholen** gilt auch für gemeinsame Änderungen, Einfügen und
  Vorlagenübernahme. Die Historie gilt für die aktuell geöffnete Konfiguration.
- Typfilter und Suche grenzen die Ansicht ein. Eine Filteränderung hebt die
  Zellenauswahl auf, damit keine unsichtbaren Geräte versehentlich mitbearbeitet werden.

Fehlende Rolle oder ungültige Werte ergeben einen **Entwurf**. Betroffene Zellen
werden rot unterstrichen; der Tooltip erklärt den Fehler. Entwürfe können gespeichert
werden. **Konfiguration hinterlegt** bedeutet weder auf Hardware übertragen noch
für eine bestimmte Firmware geprüft. Modell-, Firmware- und Länderabhängigkeiten
gehören zur späteren Hardwareprüfung. Es werden keine Firmware-Defaults angenommen.

## Vorlagen und lokale Ablage

**Vorlage übernehmen** befüllt die markierten WLAN-Geräte aus einer gespeicherten
Konfiguration, auch aus anderen Projekten. Externe YAML-Sätze können geöffnet werden.
Vorlagen werden unabhängig kopiert. Vorhandene individuelle Gerätenamen und die
Projekt-IP bleiben erhalten; der Gerätename der Vorlage wird nicht kopiert.

**Speichern** sichert lokal; die erste Konfiguration heißt **Standard**.
Die Auswahl oben öffnet gespeicherte Konfigurationen direkt. **Neue Konfiguration**
und **Speichern unter** liegen im Menü **…**. Beim Projektöffnen wird Standard,
alternativ die einzige gespeicherte Konfiguration geladen. Bei mehreren anderen
Konfigurationen wählt der Nutzer den gewünschten Stand aus. Änderungen werden
als ungespeichert gekennzeichnet; beim Verlassen wird nachgefragt.

YAML-Dateien liegen unter `%LOCALAPPDATA%/WieDAN/scalance/<Projekt-ID>-<Hash>/`.
Das bestehende Format `schema_version: 2` bleibt kompatibel: Projekt-ID, Name und
Gerätezuordnungen mit Gerätetyp sowie expliziten Parametern. SSH-Zugänge und Kopien
der Projekt-IP werden nicht gespeichert. Konfigurationen entfernter Projektgeräte
bleiben beim erneuten Speichern erhalten. Der Parameterkatalog liegt in
`core/scalance_config.py`.

## Zurückgestellt

- Switch-spezifische Parameterprofile
- Wizard **Gerät einrichten**
- Wizard **Siemens-Dateien erzeugen**
- Auslesen und Vergleich mit Geräten
- Gemeinsame Projektablage, Synchronisation und Konfliktbehandlung

YAML-Planungssätze sind keine nativen Siemens-Konfigurationsdateien.
