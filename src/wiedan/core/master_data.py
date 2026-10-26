"""Stammdaten bearbeiten und gemeinsam in der lokalen Arbeitsdatenbank speichern."""

import ipaddress
import json
import math
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from wiedan.core.project_database import (
    FORMAT_VERSION, ProjectDatabaseError, connect, inspect_database, migrate_schema, write_transaction,
)
from wiedan.core.working_configuration import PARAMETERS, available_parameters, parse_value
from wiedan.core.structure import refresh_stored_paths

# SQL-Felder sind explizit freigegeben; Kennungen, Zuordnungen und Typen bleiben stabil.
FIELDS = {
    "projects": {"display_name": ("Projektanzeige", "text"), "name": ("Kurzname", "text"),
                 "full_name": ("Vollständiger Name", "optional"), "control": ("Steuerung", "optional"),
                 "product": ("Produkt", "optional"), "live": ("Live", "bool")},
    "vehicles": {"label": ("Bezeichnung", "text"), "product": ("Produkt", "text")},
    "nodes": {"label": ("Bezeichnung", "text"), "state": ("Zustand", "nullable")},
    "devices": {"label": ("Bezeichnung", "nullable"), "ip": ("Projekt-IP", "ip"),
                "pingable": ("Pingbar", "optional_bool"),
                "track_start": ("Beginn RCoax (m)", "number"), "track_end": ("Ende RCoax (m)", "number")},
}

RCOAX_FIELDS = {"track_start", "track_end"}


def device_field_available(field, role):
    return field not in RCOAX_FIELDS or role == "Access Point"


def parse_field(table, field, text):
    text = text.strip()
    if field.startswith("parameter:"):
        return parse_value(field.split(":", 1)[1], text) if text else None
    kind = FIELDS[table][field][1]
    if kind in {"number", "nullable", "optional_bool"} and not text:
        return None
    if kind in {"bool", "optional_bool"}:
        if text.casefold() not in {"ja", "nein", "1", "0"}:
            raise ValueError("Bitte Ja oder Nein eingeben; leer übernimmt bei Geräten die Typvorgabe.")
        return int(text.casefold() in {"ja", "1"})
    if kind == "number":
        value = float(text.replace(",", "."))
        if not math.isfinite(value):
            raise ValueError("Bitte eine endliche Position in Metern eingeben.")
        return value
    if kind == "ip" and text:
        ipaddress.ip_address(text)
    if kind == "text" and not text:
        raise ValueError("Dieses Feld darf nicht leer sein.")
    return text


class MasterDataDraft:
    def __init__(self, source):
        self.source = Path(source).resolve()
        self.info = inspect_database(self.source)
        with connect(self.source) as connection:
            self.rows = {table: {row["uid"]: dict(row) for row in connection.execute(f"SELECT * FROM {table}")}
                         for table in FIELDS}
            self.parameters = {}
            if self.info["schema_version"] >= 2:
                for row in connection.execute("SELECT * FROM device_parameters"):
                    self.parameters[(row["device_uid"], row["name"])] = json.loads(row["value_json"])
        self.changes = {}

    def original(self, table, uid, field):
        if field.startswith("parameter:"):
            return self.parameters.get((uid, field.split(":", 1)[1]))
        return self.rows[table][uid][field]

    def value(self, table, uid, field):
        return self.changes.get((table, uid, field), self.original(table, uid, field))

    def change(self, table, uid, field, value):
        row = self.rows[table][uid]
        if field.startswith("parameter:"):
            name = field.split(":", 1)[1]
            if table != "devices" or name == "ip" or name not in available_parameters(row["type_id"]):
                raise ValueError("Dieser Parameter gehört nicht zu diesem Gerätetyp.")
        elif field not in FIELDS[table]:
            raise ValueError("Dieses Feld kann nicht bearbeitet werden.")
        elif table == "devices" and value is not None and not device_field_available(
                field, self.value("devices", uid, "parameter:role")):
            raise ValueError("Beginn und Ende RCoax gehören ausschließlich zu Access Points.")
        key = (table, uid, field)
        if value == self.original(*key):
            self.changes.pop(key, None)
        else:
            self.changes[key] = value

    def describe(self, table, uid, field):
        row = self.rows[table][uid]
        project = row if table == "projects" else self.rows["projects"][row["project_uid"]]
        label = f"{project['display_name']} / {row.get('path', row['uid'])}"
        title = PARAMETERS[field.split(":", 1)[1]].label if field.startswith("parameter:") else FIELDS[table][field][0]
        return label, title

    def proposals(self, working):
        """Explizite Abweichungen samt historischem und aktuellem Vergleichswert."""
        proposals = []
        for path, entry in working["devices"].items():
            base = working.get("base", {}).get(path)
            uid = base.get("uid") if base else None
            row = self.rows["devices"].get(uid)
            if row is None or row["project_uid"] != working.get("project_uid") or row["type_id"] != entry["type"]:
                raise ValueError(f"Gerät nicht eindeutig im aktiven Stamm gefunden: {path}")
            for name, value in entry["parameters"].items():
                field = "ip" if name == "ip" else f"parameter:{name}"
                current = self.original("devices", uid, field)
                if current == value:
                    continue
                old = base["parameters"].get(name)
                conflict = bool(working.get("legacy_base")) or old != current
                proposals.append((("devices", uid, field), old, current, value, conflict))
        return proposals

    def save_current(self):
        if not self.changes:
            return
        self._validate_field_changes()
        with write_transaction(self.source, self.info["uid"]) as connection:
            for (table, uid, field), value in self.changes.items():
                if field.startswith("parameter:"):
                    name = field.split(":", 1)[1]
                    if value is None:
                        connection.execute("DELETE FROM device_parameters WHERE device_uid=? AND name=?", (uid, name))
                    else:
                        connection.execute("INSERT OR REPLACE INTO device_parameters VALUES(?,?,?)",
                                           (uid, name, json.dumps(value)))
                else:
                    connection.execute(f"UPDATE {table} SET {field}=? WHERE uid=?", (value, uid))
            self._refresh_paths(connection)

    def _refresh_paths(self, connection):
        projects = {self.rows[table][uid]["project_uid"] for table, uid, field in self.changes
                    if table in {"nodes", "devices"} and field == "label"}
        for uid in projects:
            refresh_stored_paths(connection, uid, self.rows["nodes"], self.rows["devices"])

    def _validate_field_changes(self):
        for (table, uid, field), value in self.changes.items():
            if table == "devices" and field in RCOAX_FIELDS and value is not None and not device_field_available(
                    field, self.value("devices", uid, "parameter:role")):
                raise ValueError("Beginn und Ende RCoax gehören ausschließlich zu Access Points.")

    def save(self, destination, data_version):
        self._validate_field_changes()
        destination = Path(destination).resolve()
        if not self.changes:
            raise ValueError("Es sind keine Änderungen vorhanden.")
        if not data_version.strip() or data_version.strip() == self.info["data_version"]:
            raise ValueError("Bitte eine neue Datenstandsbezeichnung angeben.")
        if destination.exists() or destination == self.source:
            raise ValueError("Bitte eine neue Datei wählen. Bestehende Datenstände werden nicht überschrieben.")
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        output = None
        try:
            output = sqlite3.connect(temporary)
            output.row_factory = sqlite3.Row
            with connect(self.source) as source:
                source.backup(output)
            if output.execute("SELECT uid FROM database_info").fetchone()[0] != self.info["uid"]:
                raise ValueError("Der Ausgangsdatenstand wurde inzwischen ersetzt. Bitte den Editor neu öffnen.")
            output.execute("PRAGMA foreign_keys=ON")
            with output:
                migrate_schema(output)
                for (table, uid, field), value in self.changes.items():
                    if field.startswith("parameter:"):
                        name = field.split(":", 1)[1]
                        row = output.execute("SELECT value_json FROM device_parameters WHERE device_uid=? AND name=?",
                                             (uid, name)).fetchone()
                        actual = json.loads(row[0]) if row else None
                        if actual != self.original(table, uid, field):
                            raise ValueError("Der Stamm wurde während der Bearbeitung geändert. Bitte neu öffnen.")
                        if value is None:
                            output.execute("DELETE FROM device_parameters WHERE device_uid=? AND name=?", (uid, name))
                        else:
                            output.execute("INSERT OR REPLACE INTO device_parameters VALUES(?,?,?)", (uid, name, json.dumps(value)))
                    else:
                        row = output.execute(f"SELECT {field} FROM {table} WHERE uid=?", (uid,)).fetchone()
                        if row is None or row[0] != self.original(table, uid, field):
                            raise ValueError("Der Stamm wurde während der Bearbeitung geändert. Bitte neu öffnen.")
                        output.execute(f"UPDATE {table} SET {field}=? WHERE uid=?", (value, uid))
                self._refresh_paths(output)
                output.execute(f"PRAGMA user_version={FORMAT_VERSION}")
                output.execute("UPDATE database_info SET uid=?,data_version=?,created_at=?",
                               (str(uuid4()), data_version.strip(), datetime.now(timezone.utc).isoformat()))
            output.close()
            output = None
            inspect_database(temporary)
            temporary.rename(destination)
        except sqlite3.Error as exc:
            raise ProjectDatabaseError(f"Datenstand konnte nicht gespeichert werden: {exc}") from exc
        finally:
            if output is not None:
                output.close()
            temporary.unlink(missing_ok=True)
        return destination
