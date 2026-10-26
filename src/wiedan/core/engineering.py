"""Projektbearbeitung ohne UI: Entwürfe, Katalogauswahl und atomare Speicherung."""

import copy
import json
from pathlib import Path
from uuid import uuid4

from wiedan.core.device_fields import FIELD_TYPES, load_definitions, parse_documentation_value
from wiedan.core.master_data import FIELDS, RCOAX_FIELDS, device_field_available, parse_field
from wiedan.core.project_database import connect, inspect_database, read_catalog, write_transaction
from wiedan.core.structure import path_component, refresh_paths


class ProjectDraft:
    def __init__(self, source, project_uid=None):
        self.source = Path(source)
        inspect_database(source)
        self.is_new = project_uid is None
        with connect(source) as connection:
            connection.execute("BEGIN")
            self.base_uid = connection.execute("SELECT uid FROM database_info").fetchone()[0]
            self.types, self.categories = read_catalog(connection)
            self.parameters = {}
            self.field_definitions = load_definitions(connection)
            self.documentation = {}
            if project_uid is None:
                project_uid = str(uuid4())
                self.project = dict(uid=project_uid, project_id="", display_name="Neues Projekt", name="Neues Projekt",
                                    full_name="", live=0, control="", product="", track_origin_description="")
                self.nodes, self.devices = {}, {}
                self.vehicle_products = {}
            else:
                row = connection.execute("SELECT * FROM projects WHERE uid=?", (project_uid,)).fetchone()
                if row is None:
                    raise ValueError("Das Projekt ist nicht mehr vorhanden.")
                self.project = dict(row)
                self.vehicle_products = dict(connection.execute(
                    "SELECT uid,product FROM vehicles WHERE project_uid=?", (project_uid,)))
                self.nodes = {r["uid"]: dict(r) for r in connection.execute(
                    "SELECT * FROM nodes WHERE project_uid=? ORDER BY ordinal", (project_uid,))}
                self.devices = {r["uid"]: dict(r) for r in connection.execute(
                    "SELECT * FROM devices WHERE project_uid=? ORDER BY ordinal", (project_uid,))}
                if connection.execute("PRAGMA user_version").fetchone()[0] >= 2:
                    for row in connection.execute(
                            "SELECT p.* FROM device_parameters p JOIN devices d ON d.uid=p.device_uid WHERE d.project_uid=?",
                            (project_uid,)):
                        self.parameters.setdefault(row["device_uid"], {})[row["name"]] = json.loads(row["value_json"])
                if connection.execute("PRAGMA user_version").fetchone()[0] >= 4:
                    for row in connection.execute(
                            "SELECT v.* FROM device_field_values v JOIN devices d ON d.uid=v.device_uid WHERE d.project_uid=?",
                            (project_uid,)):
                        self.documentation.setdefault(row["device_uid"], {})[row["field_uid"]] = json.loads(row["value_json"])
        self.original = copy.deepcopy((self.project, self.nodes, self.devices, self.parameters, self.documentation))
        self._path_baselines = copy.deepcopy((self.nodes, self.devices))

    @property
    def dirty(self):
        return self.is_new or (self.project, self.nodes, self.devices, self.parameters, self.documentation) != self.original

    def row(self, kind, uid):
        return self.project if kind == "projects" else getattr(self, kind)[uid]

    def edit(self, kind, uid, field, text):
        self.row(kind, uid)[field] = parse_field(kind, field, text)

    def descendants(self, uid):
        result, pending = set(), [uid]
        while pending:
            current = pending.pop()
            if current in result:
                raise ValueError("Die Node-Struktur enthält einen Kreis.")
            result.add(current)
            pending.extend(key for key, row in self.nodes.items() if row["parent_uid"] == current)
        return result

    def _available_path(self, label, parent_uid, rows):
        prefix = self.nodes[parent_uid]["path"] + "/" if parent_uid else ""
        stem = prefix + path_component(label)
        path, index = stem, 2
        existing = {row["path"] for row in rows.values()}
        while path in existing:
            path, index = f"{stem}_{index}", index + 1
        return path

    def add_node(self, label, parent_uid=None):
        if not label.strip():
            raise ValueError("Bitte eine Bezeichnung eingeben.")
        uid = str(uuid4())
        self.nodes[uid] = dict(uid=uid, project_uid=self.project["uid"],
                               path=self._available_path(label, parent_uid, self.nodes), parent_uid=parent_uid,
                               vehicle_uid=self.nodes[parent_uid]["vehicle_uid"] if parent_uid else None,
                               label=label.strip(), state=None, ordinal=len(self.nodes))
        self._path_baselines[0][uid] = self.nodes[uid].copy()
        return uid

    def add_device(self, type_id, node_uid):
        if type_id not in self.types:
            raise ValueError("Der Gerätetyp ist nicht im Katalog vorhanden.")
        if node_uid not in self.nodes:
            raise ValueError("Bitte zuerst einen Node auswählen.")
        uid = str(uuid4())
        self.devices[uid] = dict(uid=uid, project_uid=self.project["uid"],
                                 path=self._available_path(type_id, node_uid, self.devices), node_uid=node_uid,
                                 type_id=type_id, label=None, pingable=None, ip="", connection_overrides="{}",
                                 commissioning_overrides="{}", installation_position=None, track_start=None,
                                 track_end=None, ordinal=len(self.devices))
        self._path_baselines[1][uid] = self.devices[uid].copy()
        return uid

    def move(self, kind, uid, parent_uid):
        if kind == "nodes" and parent_uid in self.descendants(uid):
            raise ValueError("Ein Node kann nicht unter sich selbst eingeordnet werden.")
        if parent_uid is not None and parent_uid not in self.nodes:
            raise ValueError("Der Ziel-Node fehlt.")
        if kind == "devices" and parent_uid is None:
            raise ValueError("Ein Gerät benötigt einen Node.")
        row = self.row(kind, uid)
        field = "parent_uid" if kind == "nodes" else "node_uid"
        previous = copy.deepcopy((self.nodes, self.devices))
        row[field] = parent_uid
        try:
            self._rebuild_paths()
        except ValueError:
            self.nodes, self.devices = previous
            raise

    def _rebuild_paths(self):
        refresh_paths(self.nodes, self.devices, *self._path_baselines)
        pending = set(self.nodes)
        while pending:
            ready = [uid for uid in pending if self.nodes[uid]["parent_uid"] not in pending]
            if not ready:
                raise ValueError("Die Node-Struktur enthält einen Kreis.")
            for uid in ready:
                row = self.nodes[uid]
                parent = self.nodes.get(row["parent_uid"])
                # Vorhandene Fahrzeugwurzeln behalten ihre fachliche Zuordnung.
                old = self.original[1].get(uid)
                old_parent = self.original[1].get(old["parent_uid"]) if old else None
                is_vehicle_root = old and old["vehicle_uid"] and (
                    old_parent is None or old_parent["vehicle_uid"] != old["vehicle_uid"])
                if not is_vehicle_root:
                    row["vehicle_uid"] = parent["vehicle_uid"] if parent else None
                pending.remove(uid)

    def remove(self, kind, uid):
        if kind == "nodes":
            if len(self.descendants(uid)) > 1 or any(r["node_uid"] == uid for r in self.devices.values()):
                raise ValueError("Bitte zuerst die untergeordneten Nodes und Geräte verschieben oder entfernen.")
            row = self.nodes[uid]
            if row["vehicle_uid"] and row["parent_uid"] is None:
                raise ValueError("Dieser Node gehört zu einem bestehenden Fahrzeug und bleibt erhalten.")
        del getattr(self, kind)[uid]

    def save(self):
        if not self.dirty:
            return self.project["uid"]
        if not self.project["project_id"].strip():
            raise ValueError("Bitte eine Projektkennung eingeben.")
        for kind, rows in (("projects", [self.project]), ("nodes", self.nodes.values()), ("devices", self.devices.values())):
            for row in rows:
                for field in FIELDS[kind]:
                    value = row[field]
                    row[field] = parse_field(kind, field, "" if value is None else str(value))
                    if kind == "devices" and field in RCOAX_FIELDS:
                        role = self.parameters.get(row["uid"], {}).get("role")
                        previous = self.original[2].get(row["uid"], {}).get(field)
                        if row[field] is not None and row[field] != previous and not device_field_available(field, role):
                            raise ValueError("Beginn und Ende RCoax gehören ausschließlich zu Access Points.")
        self._rebuild_paths()
        for uid, device in self.devices.items():
            for key, value in self.documentation.get(uid, {}).items():
                definition = self.field_definitions[key]
                if definition["type_id"] != device["type_id"]:
                    raise ValueError("Dokumentationsfeld passt nicht zum Gerätetyp.")
                self.documentation[uid][key] = parse_documentation_value(definition, value)
        with write_transaction(self.source, self.base_uid) as connection:
            for table in ("nodes", "devices"):
                original = self.original[1 if table == "nodes" else 2]
                for uid in original:
                    connection.execute(f"UPDATE {table} SET path=? WHERE uid=?", (f"~{uid}", uid))
            self._store(connection, "projects", self.project)
            for row in sorted(self.nodes.values(), key=lambda r: r["path"].count("/")):
                self._store(connection, "nodes", row)
            for row in self.devices.values():
                self._store(connection, "devices", row)
            for uid in self.devices:
                values = self.parameters.get(uid, {})
                previous = self.original[3].get(uid, {})
                for name in values.keys() | previous.keys():
                    if values.get(name) == previous.get(name):
                        continue
                    if values.get(name) is None:
                        connection.execute("DELETE FROM device_parameters WHERE device_uid=? AND name=?", (uid, name))
                    else:
                        connection.execute("INSERT OR REPLACE INTO device_parameters VALUES (?,?,?)",
                                           (uid, name, json.dumps(values[name])))
                values = self.documentation.get(uid, {})
                previous = self.original[4].get(uid, {})
                for key in values.keys() | previous.keys():
                    if values.get(key) == previous.get(key):
                        continue
                    if values.get(key) is None:
                        connection.execute("DELETE FROM device_field_values WHERE device_uid=? AND field_uid=?", (uid, key))
                    else:
                        connection.execute("INSERT OR REPLACE INTO device_field_values VALUES (?,?,?)",
                                           (uid, key, json.dumps(values[key], ensure_ascii=False)))
            for uid in self.original[2].keys() - self.devices.keys():
                connection.execute("DELETE FROM device_parameters WHERE device_uid=?", (uid,))
                connection.execute("DELETE FROM devices WHERE uid=?", (uid,))
            removed_nodes = self.original[1].keys() - self.nodes.keys()
            for uid in sorted(removed_nodes, key=lambda key: self.original[1][key]["path"].count("/"), reverse=True):
                connection.execute("DELETE FROM nodes WHERE uid=?", (uid,))
        self.__init__(self.source, self.project["uid"])
        return self.project["uid"]

    @staticmethod
    def _store(connection, table, row):
        columns = list(row)
        assignments = ",".join(f"{key}=excluded.{key}" for key in columns if key != "uid")
        connection.execute(f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' for _ in columns)}) "
                           f"ON CONFLICT(uid) DO UPDATE SET {assignments}", list(row.values()))


class CatalogDraft:
    def __init__(self, source):
        self.source = source
        with connect(source) as connection:
            connection.execute("BEGIN")
            self.base_uid = connection.execute("SELECT uid FROM database_info").fetchone()[0]
            self.types, self.categories = read_catalog(connection)
            self.fields = load_definitions(connection)
        self.assignments = {key: definition.get("category") for key, definition in self.types.items()}
        self.original = copy.deepcopy((self.categories, self.assignments, self.fields))

    @property
    def dirty(self):
        return (self.categories, self.assignments, self.fields) != self.original

    def add_category(self, label):
        label = label.strip()
        if not label or label.casefold() in {name.casefold() for name in self.categories.values()}:
            raise ValueError("Bitte eine neue, eindeutige Kategoriebezeichnung eingeben.")
        uid = str(uuid4())
        self.categories[uid] = label
        return uid

    def save(self):
        labels = list(self.categories.values())
        if any(not label.strip() for label in labels) or len({label.casefold() for label in labels}) != len(labels):
            raise ValueError("Kategorien benötigen eindeutige, nicht leere Bezeichnungen.")
        names = set()
        for uid, field in self.fields.items():
            name = (field["type_id"], field["name"].strip().casefold())
            if not name[1] or name in names or field["value_type"] not in FIELD_TYPES or field["type_id"] not in self.types:
                raise ValueError("Dokumentationsfelder benötigen je Gerätetyp eindeutige Namen und einen gültigen Datentyp.")
            if uid in self.original[2] and field["value_type"] != self.original[2][uid]["value_type"]:
                raise ValueError("Der Datentyp eines gespeicherten Dokumentationsfelds bleibt unverändert.")
            names.add(name)
        with write_transaction(self.source, self.base_uid) as connection:
            # Namen können auch zwischen Kategorien getauscht werden.
            for key in self.original[0]:
                connection.execute("UPDATE device_categories SET label=? WHERE id=?", (f"~{key}", key))
            for key, label in self.categories.items():
                connection.execute("INSERT INTO device_categories VALUES (?,?) "
                                   "ON CONFLICT(id) DO UPDATE SET label=excluded.label", (key, label))
            for key, category in self.assignments.items():
                connection.execute("UPDATE device_types SET category_id=? WHERE id=?", (category, key))
            for uid in self.original[2]:
                connection.execute("UPDATE device_field_definitions SET name=? WHERE uid=?", (f"~{uid}", uid))
            for uid, field in self.fields.items():
                connection.execute("INSERT INTO device_field_definitions VALUES (?,?,?,?) "
                                   "ON CONFLICT(uid) DO UPDATE SET name=excluded.name",
                                   (uid, field["type_id"], field["name"].strip(), field["value_type"]))
        self.__init__(self.source)
