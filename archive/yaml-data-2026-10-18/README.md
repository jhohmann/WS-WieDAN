# Archiv des bisherigen Datenstamms

Diese Dateien wurden unverändert aus `src/wiedan/data/projects/` und
`src/wiedan/data/library/` übernommen. Der aktive Datenstamm befindet sich in
`src/wiedan/data/stammdaten.sqlite`, Datenstand `2026.10.18`, Formatversion `1`.

Das Archiv dient ausschließlich der Nachvollziehbarkeit der Migration. Die
Anwendung liest es nicht; Änderungen hier ändern den aktiven Datenstamm nicht.
Projektbilder, alle Gerätetypen einschließlich Datenpunktdefinitionen und alle
Logging-Vorlagen sind ebenfalls in der Datenbank enthalten.

Die Übernahme lässt sich aus dem Repository erneut in eine **neue** Datei ausführen:

```powershell
.venv\Scripts\python.exe -m tools.migrate_yaml build/migration.sqlite --source archive/yaml-data-2026-10-18 --data-version 2026.10.18
```

Das Werkzeug prüft Datenbankintegrität und Inhaltsgleichheit vor der Freigabe.
Es dient der ursprünglichen Übernahme, nicht der Pflege neuer Datenstände.
