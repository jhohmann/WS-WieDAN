# Engineering / Planung

Engineering wird ausschließlich über **Einstellungen** geöffnet. Im Bereich
**Engineering · aktive Datenbank bearbeiten** stehen getrennte Einstiege für den
Projekteditor, den Gerätekatalog und die tabellarische Stammdatenbearbeitung.
Es gibt keinen Engineering-Modus und kein Engineering-Menü im Hauptfenster.
Alle Projekte liegen in der ausgewählten lokalen SQLite-Arbeitsdatenbank.

## Projekt bearbeiten

- **Einstellungen → Projekteditor öffnen …** wählen. Ein bestehendes Projekt
  über die Projektauswahl im Editor öffnen.
- **Neues Projekt** legt zunächst einen ungespeicherten Entwurf an. Projektkennung,
  Anzeigename und weitere Eigenschaften stehen rechts. Die Projektkennung bleibt
  nach dem ersten Speichern stabil; Namen können geändert werden.
- Das Projekt im Baum auswählen und **Node hinzufügen** verwenden, um einen
  Wurzel-Node anzulegen. Bei einem ausgewählten Node entsteht ein Unter-Node.
- **Gerät hinzufügen** öffnet den durchsuchbaren Gerätetypkatalog für den
  ausgewählten Node. Protokoll und vorhandene Datenpunkte werden angezeigt.
- Eigenschaften werden rechts bearbeitet. Über die Node-Auswahl können Geräte
  und Nodes innerhalb des Projekts umgeordnet werden. Kreise und doppelte Pfade
  werden abgewiesen; UUIDs bleiben erhalten.
- Eine IP-Adresse kann während der Planung leer bleiben. Solche Geräte werden
  bei der Erreichbarkeitsprüfung ausgelassen.
- Bei WLAN-Geräten die **Geräterolle** auswählen. Nur bei **Access Point** erscheinen
  **Beginn RCoax (m)** und **Ende RCoax (m)**. Der Stammdateneditor bietet dieselben
  Felder für APs an. Die Rolle wird ausdrücklich festgelegt, nicht aus Namen abgeleitet.
- Ein Strecken-Nullpunkt ist kein bearbeitbarer Projektparameter. Die allgemeine
  Einbauposition wird ebenfalls nicht angeboten. Eine spätere Streckenmodellierung
  mit Einstieg, Ausstieg, Servicegleis, Einspeisung und Schleifertest ist zurückgestellt.
- Geräte und leere allgemeine Nodes können entfernt werden. Vorhandene
  Fahrzeugwurzeln bleiben als Kompatibilitätsstruktur erhalten.
- **Speichern** übernimmt den gesamten Projektentwurf gemeinsam. **Verwerfen**
  lädt den gespeicherten Stand. Beim Projektwechsel und Schließen werden
  ungespeicherte Änderungen berücksichtigt.

Die Ansicht **Nach Gerätekategorie** gruppiert dieselben Geräte nach ihrer
Typkategorie und zeigt den zugehörigen Node. Die fachliche Nodezuordnung wird
dadurch nicht geändert. In der Anlagenstruktur sind auch leere Nodes sichtbar.
Node- und Gerätesymbole entsprechen der Live-Ansicht. Allgemeine Nodes erhalten
ein Struktursymbol; Fahrzeuge und Zentrale behalten ihre bisherigen Symbole.
Die Kategorieansicht sortiert Kategorien und Geräte alphabetisch.

## Stammdaten und Katalog

Der Stammdateneditor bleibt für tabellarische Änderungen verfügbar. Er schreibt
nach dem Änderungsvergleich direkt in die Arbeitsdatenbank; ein neuer Dateiname
oder ein manuell benannter Datenstand ist nicht mehr erforderlich.

Unter **Einstellungen → Gerätekatalog bearbeiten …** können Kategorien angelegt,
umbenannt und Gerätetypen zugeordnet werden. Technische Typdefinitionen bleiben
hier schreibgeschützt. Protokoll, Datenpunkte und deren Adressierung gehören zum
Datenstamm; die Ausführung des Protokolls bleibt Programmcode. Die Kategorie ist
eine Ordnungshilfe und entscheidet nicht über die technischen Fähigkeiten.

## Eigene Dokumentationsfelder

1. **Einstellungen → Gerätekatalog bearbeiten …** öffnen und den Gerätetyp auswählen.
2. **Dokumentationsfelder für ausgewählten Gerätetyp …** öffnen, ein Feld hinzufügen
   und den Datentyp **Text**, **Zahl** oder **Ja / Nein** wählen.
3. **Übernehmen** und anschließend im Gerätekatalog **Speichern** drücken.
4. Im Projekteditor ein Gerät dieses Typs auswählen. Rechts unter
   **Dokumentationsfelder** die individuellen Werte eintragen und das Projekt speichern.

Definitionen gelten für alle Instanzen des Gerätetyps, Werte gehören jeweils nur
zu einem Gerät. Leere Angaben sind nicht gesetzt; Nein und 0 sind gültige Werte.
Feldnamen können später geändert werden; gespeicherte Werte bleiben über die
Feld-UUID zugeordnet. Der Datentyp eines gespeicherten Felds bleibt fest.
Dokumentationsfelder haben keine Protokolladresse und werden nicht ans Gerät übertragen.

## Speicherung und Migration

Das aktuelle Format ist **4**. Die mitgelieferte Datenbank und bestehende lokale
Datenbanken werden beim bloßen Öffnen nicht geändert. Beim ersten Speichern in
Format 1, 2 oder 3 wird eine Sicherung neben der Originaldatei angelegt:
`<Name>.vor-format-4-<Kennung>.sqlite`. Anschließend erfolgen die additive
Migration und die Änderungen in einer Transaktion.

Format 2 ergänzt Geräteparameter. Format 3 ergänzt `device_categories` und
`device_types.category_id`. Die bisherigen Kategorien aus den Typdefinitionen
werden übernommen; danach ist die relationale Zuordnung maßgeblich. Die
allgemeine Node-Struktur verlangt keine Zentrale und keine Fahrzeuge mehr.
Alte Fahrzeugzuordnungen und alle bestehenden UUIDs bleiben erhalten.
Format 4 ergänzt `device_field_definitions` für die typgebundenen Felddefinitionen
und `device_field_values` für Werte je Geräteinstanz. Fremdschlüssel und die
Inhaltsprüfung sichern Gerätebezug, Typzuordnung und Werte ab.
Die bisherigen SQL-Spalten für Positionsdaten bleiben aus Kompatibilitätsgründen
bestehen. `track_start` und `track_end` werden als RCoax-Grenzen verwendet;
vorhandene ausgeblendete Altdaten werden nicht gelöscht.

Jeder Schreibvorgang prüft den Datenstandsbezug des geöffneten Entwurfs. Wurde
zwischenzeitlich anderswo gespeichert, wird der veraltete Entwurf abgewiesen.
Es gibt noch keine automatische Zusammenführung. Bei Fehlern wird die gesamte
Schreibtransaktion einschließlich einer begonnenen Migration zurückgerollt.

Die neue Datenstandskennung ist ein Konfliktschutz für die lokale Bearbeitung,
keine Freigabe oder vollständige Änderungshistorie. Freigabestände, Serviceabgleich
und Hardwarehistorien sind weiterhin spätere Ausbauschritte.

## Bewusst begrenzter Umfang

Dieser Schritt baut Projektstruktur und Katalogzuordnung aus. Die bestehende
Scalance-Parameterbearbeitung bleibt erhalten, ebenso ihre lokalen YAML-Entwürfe.
Ein allgemeiner Vorlagen-/Revisionsmechanismus und die Verlagerung des bisherigen
Scalance-Parameterkatalogs aus Python in den Datenstamm folgen separat.

Servicewerkzeuge und alternative Parametrierungen sollen die Engineering-Basis
künftig erst nach dem Zurücklesen der Originalgeräte und einer bewussten Übernahme
ändern. Dieser Serviceablauf wird in diesem Schritt nicht implementiert.
Der direkte Menüeintrag zum Übernehmen einer Scalance-Arbeitskonfiguration in die
Stammdaten wird nicht mehr angeboten. Stammdatenpflege erfolgt über die Einstellungen.
