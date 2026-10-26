# HIMA-Ringbuffer

Unter **Inbetriebnahme → HIMA → Ringbuffer**. Das Tool verwendet keine
Stammdaten und benötigt kein ausgewähltes Projekt.

1. SPS-IP, Port (Standard 502) und Unit-ID (Standard 0) eingeben und verbinden.
   Das **Antwort-Timeout** ist auf 5 Sekunden voreingestellt und vor dem
   Verbinden zwischen 1 und 30 Sekunden einstellbar. Es ist unabhängig von
   der Wartezeit zwischen Schreiben und Lesen.
2. Die **0-basierten Modbus-Adressen** sind vorbelegt: ReadIndex wird mit
   **FC16 (Write Multiple Registers)** auf Register **0** geschrieben,
   Reset mit **FC05 (Write Single Coil)** auf Coil **0**.
   Gelesen werden Zeit auf Register 0, Kanal 1–8 auf Register 1–8 und
   Triggerposition auf Register 9. Alle Registerwerte sind 16 Bit breit.
3. Die Wartezeit je Sample ist auf **50 ms** eingestellt.
   Die Triggerposition beginnt bei 0. Ein Index wird nicht zurückgelesen.
4. **Datensatz auslesen** startet die automatische Übertragung aller 1000 Samples.
   Pro Sample wird ReadIndex (0–999) mit FC16 als einzelnes Register geschrieben, die eingestellte Zeit
   abgewartet und anschließend mit FC03 gelesen. Benachbarte Leseregister
   werden gemeinsam abgefragt. Die Oberfläche bleibt bedienbar.

Die SPS muss einen fertigen, während der gesamten Übertragung unveränderten
Ringbuffer bereitstellen. Eine Modbus-Schreibbestätigung bestätigt noch nicht,
dass das SPS-Programm die neue Leseadresse verarbeitet hat. Die Wartezeit muss zur
SPS passen; eine separate Bereit-/Index-Rückmeldung ist derzeit nicht vorgesehen.
Ändert sich die gelesene Triggerposition während der Übertragung oder liegt sie
außerhalb des Puffers, wird die Auslesung verworfen.

Nach vollständiger Übertragung wird die Adressfolge zyklisch verschoben:

`Start = (Triggerposition + 100 + 1) modulo 1000`

Die Sequenz enthält 899 Samples vor dem Trigger, das Trigger-Sample und
anschließend 100 Posttrigger-Samples. Zeit und alle acht Kanäle bleiben beim
Umsortieren zusammen. Die Tabelle zeigt den Zyklus relativ zum Trigger
(-899 bis +100), die ursprüngliche Pufferadresse und die unveränderten
vorzeichenlosen 16-Bit-Werte. Zeitwerte werden nicht skaliert oder nach Größe
sortiert. **Zum Trigger** springt auf Zyklus 0.

**CSV exportieren …** speichert den angezeigten vollständigen Datensatz in
derselben sortierten Reihenfolge. Die Datei enthält eine Kopfzeile und 1000
Datenzeilen mit Zyklus zum Trigger (-899 bis +100, Trigger = 0), Pufferadresse,
Zeit und Kanal 1–8. Alle Datenwerte bleiben numerisch und unverändert.
Trennzeichen ist ein Semikolon, die Kodierung UTF-8 mit BOM für Excel.
Der Speicherort wird im Speichern-Dialog gewählt. Der Export ist auch nach
Trennung der SPS möglich; während eines laufenden Auftrags ist er deaktiviert.

**Abbrechen** beendet die Übertragung nach der laufenden Modbus-Anfrage und
trennt die Verbindung. Bei einem Fehler wird ebenfalls getrennt. Es gibt keine
automatischen Schreibwiederholungen. Ein bereits vollständig ausgelesener
Datensatz bleibt bei neuer Auslesung, Abbruch, Reset und Trennung sichtbar;
Teilübertragungen ersetzen ihn nicht.

Bei Übertragungsfehlern nennt die Meldung das betroffene Sample, ReadIndex und
Register sowie den Schritt (ReadIndex schreiben oder Werte lesen). Ein Timeout
nennt zusätzlich Funktionscode, Unit-ID und die Phase der Übertragung.
Die eingestellte Antwortzeit begrenzt die einzelnen Socket-Wartevorgänge;
sie ist keine Zeitgrenze für die gesamte Auslesung. Ein erfolgreicher
TCP-Verbindungsaufbau bestätigt noch keine Modbus-Antwort der SPS.

**Reset (Impuls 1 → 0)** schreibt mit FC05 zunächst 1 auf den konfigurierten
Coil und anschließend 0. Als Impulsdauer sind vorläufig 50 ms angesetzt.
Auch beim Beenden der Anwendung wird das abschließende Schreiben von 0 noch
versucht. Wird es nicht bestätigt, meldet das Tool den unbestätigten Coil-Zustand.
Der Reset wird manuell ausgelöst. Die Rückmeldung bestätigt die Schreibaufträge,
nicht die Ausführung des Resets im SPS-Programm.

ReadIndex wird nur geschrieben; die SPS liefert keinen Index zurück.
Die Auslesung wurde vom Benutzer als funktionsfähig bestätigt.
Einstellungen und ausgelesene Werte bleiben für die laufende Anwendungssitzung
im Tool erhalten.
