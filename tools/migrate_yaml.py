"""Einmalige Übernahme archivierter YAML-Stammdaten; kein Bestandteil der Anwendung."""

import argparse
import hashlib
import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

import yaml

from wiedan.core.model import Device, Node, Project
from wiedan.core.project_database import (
    APPLICATION_ID,
    FORMAT_VERSION,
    ProjectDatabaseError,
    connect,
    inspect_database,
    load_project,
    project_photo,
)

_NODE_KEYS = {"label", "state", "devices", "uid"}


def stable_uid(project_uid, kind, key):
    return str(uuid5(UUID(project_uid), f"{kind}:{key}"))


class LegacySource:
    def __init__(self, root):
        self.root = Path(root)
        self._types = {}

    def path(self, *parts):
        return self.root.joinpath(*parts)

    def read_yaml(self, *parts):
        return yaml.safe_load(self.path(*parts).read_text(encoding="utf-8"))

    def device_type(self, type_id):
        if type_id not in self._types:
            self._types[type_id] = self.read_yaml("library", "device_types", f"{type_id}.yaml")["device_type"]
        return self._types[type_id]

    def load_project(self, project_id: str) -> Project:
        """Unveränderliche Importvorlagen; nicht die Arbeitsdaten der Anwendung."""
        raw = self.read_yaml("projects", f"{project_id}.yaml")
        devices = {}

        def add(vehicle, dev_id, d):
            t = self.device_type(d["type"])
            comm = t.get("commissioning_connection")
            devices[dev_id] = Device(
                id=dev_id,
                vehicle=vehicle,
                label=d.get("label", t["label"]),
                type=d["type"],
                pingable=d.get("pingable", t["pingable"]),
                connection={**t["connection"], "ip": d["ip"]},
                commissioning_connection={**comm, "ip": d["ip"]} if comm else None,
                category=t.get("category"),
                installation_position=d.get("installation_position"),
                track_start=d.get("track_start"),
                track_end=d.get("track_end"),
                uid=d.get("uid", ""),
            )

        def build(vehicle, path, key, raw_node):
            """Knoten aus YAML lesen: Alles ausser label/state/devices mit dict-Wert ist ein Unterknoten."""
            path = (*path, key)
            node = Node(
                id="/".join(path),
                label=raw_node.get("label", key),
                state=raw_node.get("state"),
                uid=raw_node.get("uid", ""),
            )
            for name, d in (raw_node.get("devices") or {}).items():
                add(vehicle, "/".join((*path, name)), d)
                node.devices.append("/".join((*path, name)))
            for k, v in raw_node.items():
                if k not in _NODE_KEYS and isinstance(v, dict):
                    node.children.append(build(vehicle, path, k, v))
            return node

        central = build(None, (), "central", raw["central"])
        central.label = raw["central"].get("label", "Zentrale")
        vehicle_nodes = {vid: build(vid, (), vid, v) for vid, v in raw["vehicles"].items()}
        return Project(
            id=raw["id"],
            name=raw["name"],
            full_name=raw.get("full_name", ""),
            credentials=raw.get("credentials", {}),
            devices=devices,
            live=raw.get("live", False),
            central=central,
            vehicle_nodes=vehicle_nodes,
            vehicles={vid: v.get("label", vid) for vid, v in raw["vehicles"].items()},
            control=raw["control"],
            product=raw["product"],
            vehicle_products={vid: v.get("product", raw["product"]) for vid, v in raw["vehicles"].items()},
            uid=raw.get("uid", ""),
        )


def _insert_project(connection, source, source_name):
    project = source.load_project(source_name)
    project_uid = project.uid or str(uuid5(NAMESPACE_URL, f"wiedan:project:{project.id}"))
    connection.execute("INSERT INTO projects(uid,project_id,display_name,name,full_name,live,control,product) "
                       "VALUES(?,?,?,?,?,?,?,?)", (project_uid, project.id, source_name, project.name,
                                                  project.full_name, project.live, project.control, project.product))
    for name, values in project.credentials.items():
        connection.execute("INSERT INTO credentials VALUES (?,?,?)", (project_uid, name, json.dumps(values)))
    for order, (key, label) in enumerate(project.vehicles.items()):
        connection.execute("INSERT INTO vehicles VALUES (?,?,?,?,?,?)",
                           (stable_uid(project_uid, "vehicle", key), project_uid, key, label, project.vehicle_products[key], order))

    def insert_node(node, parent_uid=None, vehicle=None, order=0):
        node_uid = node.uid or stable_uid(project_uid, "node", node.id)
        vehicle_uid = stable_uid(project_uid, "vehicle", vehicle) if vehicle else None
        connection.execute("INSERT INTO nodes VALUES (?,?,?,?,?,?,?,?)",
                           (node_uid, project_uid, node.id, parent_uid, vehicle_uid, node.label, node.state, order))
        for position, path in enumerate(node.devices):
            device = project.devices[path]
            definition = source.device_type(device.type)
            overrides = {k: v for k, v in device.connection.items() if k != "ip" and definition["connection"].get(k) != v}
            comm = {k: v for k, v in (device.commissioning_connection or {}).items()
                    if k != "ip" and (definition.get("commissioning_connection") or {}).get(k) != v}
            connection.execute("INSERT INTO devices VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                               (device.uid or stable_uid(project_uid, "device", path), project_uid, path, node_uid,
                                device.type, device.label if device.label != definition["label"] else None,
                                device.pingable if device.pingable != definition["pingable"] else None,
                                device.connection["ip"], json.dumps(overrides), json.dumps(comm),
                                device.installation_position, device.track_start, device.track_end, position))
        for index, child in enumerate(node.children):
            insert_node(child, node_uid, vehicle, index)

    insert_node(project.central)
    for order, (vehicle, node) in enumerate(project.vehicle_nodes.items(), 1):
        insert_node(node, vehicle=vehicle, order=order)
    for suffix in ("jpg", "png"):
        image = source.path("projects", f"{source_name}.{suffix}")
        if image.is_file():
            connection.execute("INSERT INTO assets VALUES (?,'project_photo',?)", (project_uid, image.read_bytes()))
            break


def build_database(destination: Path, *, source: Path, data_version: str):
    """Explizites Bereitstellungswerkzeug, keine Stammdatenbearbeitung in der Anwendung."""
    source = LegacySource(source)

    if not data_version.strip():
        raise ValueError("Eine Datenstandsbezeichnung ist erforderlich.")
    destination = Path(destination)
    if destination.exists():
        raise ProjectDatabaseError("Zieldatei existiert bereits. Für einen neuen Datenstand eine neue Datei wählen.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
    connection = sqlite3.connect(temporary)
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(f"PRAGMA application_id={APPLICATION_ID}")
        connection.execute(f"PRAGMA user_version={FORMAT_VERSION}")
        connection.executescript((files("wiedan.core") / "project_schema.sql").read_text(encoding="utf-8"))
        with connection:
            connection.execute("INSERT INTO database_info VALUES(1,?,?,?)",
                               (str(uuid4()), data_version.strip(), datetime.now(timezone.utc).isoformat()))
            for directory, table, wrapper in (("device_types", "device_types", "device_type"),
                                               ("logging_sets", "logging_sets", None)):
                for entry in sorted(source.path("library", directory).glob("*.yaml")):
                    definition = source.read_yaml("library", directory, entry.name)
                    if wrapper:
                        definition = definition[wrapper]
                    connection.execute(f"INSERT INTO {table} (id,definition_json) VALUES (?,?)",
                                       (entry.stem, json.dumps(definition)))
                    if table == "device_types" and definition.get("category"):
                        from wiedan.core.project_database import CATEGORY_LABELS

                        category = definition["category"]
                        connection.execute("INSERT OR IGNORE INTO device_categories VALUES (?,?)",
                                           (category, CATEGORY_LABELS.get(category, category)))
                        connection.execute("UPDATE device_types SET category_id=? WHERE id=?", (category, entry.stem))
            for entry in sorted(source.path("projects").glob("*.yaml")):
                _insert_project(connection, source, entry.stem)
        connection.close()
        inspect_database(temporary)
        verify_migration(source, temporary)
        temporary.rename(destination)
    finally:
        connection.close()
        temporary.unlink(missing_ok=True)


def verify_migration(source, database):
    """Vor Freigabe Inhalte vergleichen, ohne Zugangsdaten in Meldungen auszugeben."""
    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).digest()

    def require(equal, description):
        if not equal:
            raise ProjectDatabaseError(f"Migration unvollständig: {description}")

    def without_uids(node):
        result = asdict(node)

        def strip(item):
            item.pop("uid")
            item.pop("vehicle", None)
            for child in item["children"]:
                strip(child)

        strip(result)
        return result

    names = sorted(entry.stem for entry in source.path("projects").glob("*.yaml"))
    with connect(database) as connection:
        stored_names = [row[0] for row in connection.execute("SELECT display_name FROM projects ORDER BY display_name")]
        require(names == stored_names, "Projektliste")
        for directory, table, wrapper in (("device_types", "device_types", "device_type"),
                                           ("logging_sets", "logging_sets", None)):
            originals = {}
            for entry in source.path("library", directory).glob("*.yaml"):
                data = source.read_yaml("library", directory, entry.name)
                originals[entry.stem] = data[wrapper] if wrapper else data
            stored = {row[0]: json.loads(row[1]) for row in connection.execute(f"SELECT * FROM {table}")}
            require(digest(originals) == digest(stored), directory)

    for name in names:
        original = source.load_project(name)
        stored = load_project(name, path=database)
        for field in ("id", "name", "full_name", "live", "control", "product", "vehicles", "vehicle_products", "credentials"):
            require(digest(getattr(original, field)) == digest(getattr(stored, field)), f"{name}: {field}")
        require(set(original.devices) == set(stored.devices), f"{name}: Gerätezuordnung")
        for key, device in original.devices.items():
            expected, actual = asdict(device), asdict(stored.devices[key])
            if not expected["uid"]:
                expected["uid"] = stable_uid(stored.uid, "device", key)
            require(digest(expected) == digest(actual), f"{name}: {key}")
        require(without_uids(original.central) == without_uids(stored.central), f"{name}: Zentrale")
        for key, node in original.vehicle_nodes.items():
            require(without_uids(node) == without_uids(stored.vehicle_nodes[key]), f"{name}: {key}")
        image = next((source.path("projects", f"{name}.{suffix}") for suffix in ("jpg", "png")
                      if source.path("projects", f"{name}.{suffix}").is_file()), None)
        require(project_photo(name, path=database) == (image.read_bytes() if image else None), f"{name}: Projektbild")


def main():
    parser = argparse.ArgumentParser(description="Archivierte YAML-Stammdaten einmalig nach SQLite übernehmen.")
    parser.add_argument("destination", type=Path)
    parser.add_argument("--source", type=Path, required=True, help="Ordner mit projects/ und library/")
    parser.add_argument("--data-version", required=True)
    args = parser.parse_args()
    build_database(args.destination, source=args.source, data_version=args.data_version)
    info = inspect_database(args.destination)
    print(f"Migration abgeschlossen: {info['project_count']} Projekte, Datenstand {info['data_version']}.")
    print(f"Stammdatenbank: {args.destination}")


if __name__ == "__main__":
    main()
