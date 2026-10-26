"""Lokaler Projektbestand mit getrennten Lesezugriffen und Schreibtransaktionen."""

import json
import math
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.resources import files
from pathlib import Path
from uuid import UUID, uuid4

from wiedan.core.settings import load_settings, save_settings

FORMAT_VERSION = 4
SUPPORTED_FORMATS = (1, 2, 3, 4)
APPLICATION_ID = int.from_bytes(b"WIDM", "big")


class ProjectDatabaseError(ValueError):
    """Die gewählte Stammdatenbank fehlt, ist beschädigt oder inkompatibel."""


def local_directory():
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "WieDAN"


def database_path():
    configured = load_settings().get("database_path")
    if configured:
        return Path(configured)
    destination = local_directory() / "stammdaten.sqlite"
    if not destination.exists():
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.tmp")
        try:
            temporary.write_bytes((files("wiedan") / "data" / "stammdaten.sqlite").read_bytes())
            inspect_database(temporary)
            # Windows rename refuses an existing destination, including a concurrent first start.
            try:
                temporary.rename(destination)
            except FileExistsError:
                pass
        finally:
            temporary.unlink(missing_ok=True)
    return destination


@contextmanager
def connect(path=None):
    """Lesezugriff; Änderungen laufen ausschließlich über write_transaction."""
    path = Path(path) if path is not None else database_path()
    connection = None
    try:
        connection = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA query_only=ON")
        if connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
            raise ProjectDatabaseError("Keine WieDAN-Stammdatenbank (Einzelprojektdateien sind nicht kompatibel).")
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        if version > FORMAT_VERSION:
            raise ProjectDatabaseError(f"Datenbankformat {version} benötigt eine neuere WieDAN-Version "
                                       f"(unterstützt: {FORMAT_VERSION}).")
        if version not in SUPPORTED_FORMATS:
            raise ProjectDatabaseError(f"Unbekanntes Datenbankformat {version}. Die Datei bleibt unverändert.")
        yield connection
    except sqlite3.Error as exc:
        raise ProjectDatabaseError(f"Stammdatenbank {path.name}: {exc}") from exc
    finally:
        if connection is not None:
            connection.close()


CATEGORY_LABELS = {"inverter": "Umrichter", "plc": "SPS", "comms": "Kommunikation", "io": "I/O"}


def read_catalog(connection):
    """Technische Definitionen bleiben Daten; Kategorien sind ab Format 3 relational."""
    modern = connection.execute("PRAGMA user_version").fetchone()[0] >= 3
    definitions = {}
    for row in connection.execute("SELECT * FROM device_types ORDER BY id"):
        definition = json.loads(row["definition_json"])
        if modern:
            definition["category"] = row["category_id"]
        definitions[row["id"]] = definition
    if modern:
        categories = dict(connection.execute("SELECT id,label FROM device_categories ORDER BY label"))
    else:
        categories = {d["category"]: CATEGORY_LABELS.get(d["category"], d["category"])
                      for d in definitions.values() if d.get("category")}
    return definitions, categories


def migrate_schema(connection):
    """Additive Migration in der Schreibtransaktion; vorhandene UUIDs bleiben bestehen."""
    version = connection.execute("PRAGMA user_version").fetchone()[0]
    if version < 2:
        connection.execute("CREATE TABLE device_parameters (device_uid TEXT NOT NULL REFERENCES devices(uid), "
                           "name TEXT NOT NULL, value_json TEXT NOT NULL, PRIMARY KEY(device_uid,name))")
    if version < 3:
        definitions, categories = read_catalog(connection)
        connection.execute("CREATE TABLE device_categories (id TEXT PRIMARY KEY, label TEXT NOT NULL UNIQUE)")
        connection.execute("ALTER TABLE device_types ADD COLUMN category_id TEXT REFERENCES device_categories(id)")
        connection.executemany("INSERT INTO device_categories VALUES (?,?)", categories.items())
        connection.executemany("UPDATE device_types SET category_id=? WHERE id=?",
                               [(definition.get("category"), key) for key, definition in definitions.items()])
    if version < 4:
        connection.execute("CREATE TABLE device_field_definitions (uid TEXT PRIMARY KEY, "
                           "type_id TEXT NOT NULL REFERENCES device_types(id), "
                           "name TEXT NOT NULL CHECK (length(trim(name)) > 0), "
                           "value_type TEXT NOT NULL CHECK (value_type IN ('text','number','boolean')), UNIQUE(type_id,name))")
        connection.execute("CREATE TABLE device_field_values ("
                           "device_uid TEXT NOT NULL REFERENCES devices(uid) ON DELETE CASCADE, "
                           "field_uid TEXT NOT NULL REFERENCES device_field_definitions(uid), "
                           "value_json TEXT NOT NULL, PRIMARY KEY(device_uid,field_uid))")
    connection.execute(f"PRAGMA user_version={FORMAT_VERSION}")


@contextmanager
def write_transaction(path, expected_uid):
    """Atomar speichern; veraltete Bearbeitungsstände niemals still überschreiben."""
    path = Path(path).resolve()
    connection = None
    try:
        info = inspect_database(path)
        if info["schema_version"] < FORMAT_VERSION:
            backup = path.with_name(f"{path.stem}.vor-format-{FORMAT_VERSION}-{uuid4().hex[:8]}.sqlite")
            with connect(path) as source:
                destination = sqlite3.connect(backup)
                try:
                    source.backup(destination)
                finally:
                    destination.close()
        connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("BEGIN IMMEDIATE")
        if (connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID
                or connection.execute("PRAGMA user_version").fetchone()[0] not in SUPPORTED_FORMATS):
            raise ProjectDatabaseError("Die Datenbank wurde inzwischen ersetzt. Bitte neu öffnen.")
        if connection.execute("SELECT uid FROM database_info").fetchone()[0] != expected_uid:
            raise ProjectDatabaseError("Der Datenbestand wurde inzwischen geändert. Bitte Änderungen sichern "
                                       "oder notieren und den Editor neu öffnen.")
        migrate_schema(connection)
        yield connection
        if connection.execute("PRAGMA foreign_key_check").fetchone():
            raise ProjectDatabaseError("Ungültige Zuordnung. Die Änderungen wurden nicht gespeichert.")
        _validate_contents(connection)
        now = datetime.now(timezone.utc).isoformat()
        connection.execute("UPDATE database_info SET uid=?,data_version=?,created_at=?",
                           (str(uuid4()), now, now))
        connection.commit()
    except sqlite3.Error as exc:
        raise ProjectDatabaseError(f"Änderungen konnten nicht gespeichert werden: {exc}") from exc
    finally:
        if connection is not None:
            connection.rollback()
            connection.close()


def inspect_database(path=None):
    with connect(path) as connection:
        if connection.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ProjectDatabaseError("Die Stammdatenbank ist beschädigt.")
        if connection.execute("PRAGMA foreign_key_check").fetchone():
            raise ProjectDatabaseError("Die Stammdatenbank enthält ungültige Zuordnungen.")
        rows = connection.execute("SELECT * FROM database_info").fetchall()
        if len(rows) != 1:
            raise ProjectDatabaseError("Datenbankkennung fehlt oder ist mehrdeutig.")
        _validate_contents(connection)
        return {**dict(rows[0]), "schema_version": connection.execute("PRAGMA user_version").fetchone()[0],
                "project_count": connection.execute("SELECT count(*) FROM projects").fetchone()[0]}


def select_database(path):
    """Nur die Verbindungseinstellung ändern, niemals die gewählte SSOT-Datei."""
    path = Path(path).resolve()
    info = inspect_database(path)
    settings = load_settings()
    settings["database_path"] = str(path)
    save_settings(settings)
    return info


def list_projects(*, path=None):
    with connect(path) as connection:
        return [row[0] for row in connection.execute("SELECT display_name FROM projects ORDER BY display_name")]


def _project(connection, identifier):
    row = connection.execute("SELECT * FROM projects WHERE display_name=? OR project_id=? OR uid=?",
                             (identifier, identifier, identifier)).fetchone()
    if row is None:
        raise ProjectDatabaseError(f"Projekt nicht im gewählten Datenstand vorhanden: {identifier}")
    return row


def load_project(identifier, *, path=None):
    from wiedan.core.device_fields import load_definitions
    from wiedan.core.model import Device, Node, Project

    path = Path(path) if path is not None else database_path()
    with connect(path) as connection:
        project = _project(connection, identifier)
        project_uid = project["uid"]
        info = connection.execute("SELECT * FROM database_info").fetchone()
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        parameters = {}
        documentation = {}
        field_definitions = load_definitions(connection)
        if version >= 4:
            for row in connection.execute("SELECT v.* FROM device_field_values v JOIN devices d ON d.uid=v.device_uid "
                                          "WHERE d.project_uid=?", (project_uid,)):
                documentation.setdefault(row["device_uid"], {})[row["field_uid"]] = json.loads(row["value_json"])
        if version >= 2:
            for row in connection.execute("SELECT p.* FROM device_parameters p JOIN devices d ON d.uid=p.device_uid "
                                          "WHERE d.project_uid=?", (project_uid,)):
                parameters.setdefault(row["device_uid"], {})[row["name"]] = json.loads(row["value_json"])
        types, _categories = read_catalog(connection)
        vehicles = list(connection.execute("SELECT * FROM vehicles WHERE project_uid=? ORDER BY ordinal", (project_uid,)))
        vehicle_paths = {row["uid"]: row["path"] for row in vehicles}
        node_rows = list(connection.execute("SELECT * FROM nodes WHERE project_uid=? ORDER BY ordinal", (project_uid,)))
        nodes = {row["uid"]: Node(row["path"], row["label"], row["state"], uid=row["uid"],
                                  vehicle=vehicle_paths.get(row["vehicle_uid"])) for row in node_rows}
        node_vehicles = {row["uid"]: vehicle_paths.get(row["vehicle_uid"]) for row in node_rows}
        central = None
        root_nodes = []
        vehicle_nodes = {}
        for row in node_rows:
            node = nodes[row["uid"]]
            if row["parent_uid"] is None:
                root_nodes.append(node)
            if row["vehicle_uid"] and (not row["parent_uid"] or
                    nodes[row["parent_uid"]].vehicle != node.vehicle):
                vehicle_nodes[vehicle_paths[row["vehicle_uid"]]] = node
            if row["parent_uid"]:
                nodes[row["parent_uid"]].children.append(node)
            elif row["vehicle_uid"]:
                vehicle_nodes[vehicle_paths[row["vehicle_uid"]]] = node
            elif row["path"] == "central" or central is None:
                central = node
        if central is None:
            central = Node("central", "Zentrale")  # Kompatibilität für ältere Aufrufer.
        devices = {}
        for row in connection.execute("SELECT * FROM devices WHERE project_uid=? ORDER BY ordinal,path", (project_uid,)):
            definition = types[row["type_id"]]
            comm = definition.get("commissioning_connection")
            device = Device(
                id=row["path"], uid=row["uid"], vehicle=node_vehicles[row["node_uid"]], type=row["type_id"],
                label=row["label"] if row["label"] is not None else definition["label"],
                pingable=bool(row["pingable"] if row["pingable"] is not None else definition["pingable"]),
                category=definition.get("category"),
                connection={**definition["connection"], **json.loads(row["connection_overrides"]), "ip": row["ip"]},
                commissioning_connection={**comm, **json.loads(row["commissioning_overrides"]), "ip": row["ip"]} if comm else None,
                installation_position=row["installation_position"], track_start=row["track_start"], track_end=row["track_end"],
                parameters=parameters.get(row["uid"], {}),
                documentation=documentation.get(row["uid"], {}),
            )
            devices[device.id] = device
            nodes[row["node_uid"]].devices.append(device.id)
        return Project(
            id=project["project_id"], uid=project_uid, name=project["name"], full_name=project["full_name"],
            credentials={row["name"]: json.loads(row["values_json"]) for row in connection.execute(
                "SELECT * FROM credentials WHERE project_uid=?", (project_uid,))},
            devices=devices, live=bool(project["live"]), control=project["control"], product=project["product"],
            vehicles={row["path"]: row["label"] for row in vehicles},
            vehicle_products={row["path"]: row["product"] for row in vehicles},
            central=central, vehicle_nodes=vehicle_nodes, database_path=path, schema_version=version,
            data_version=info["data_version"], database_uid=info["uid"], display_name=project["display_name"],
            root_nodes=root_nodes,
            device_field_definitions=field_definitions,
        )


def project_photo(identifier, *, path=None):
    with connect(path) as connection:
        project = _project(connection, identifier)
        row = connection.execute("SELECT content FROM assets WHERE project_uid=? AND name='project_photo'",
                                 (project["uid"],)).fetchone()
        return bytes(row[0]) if row else None


def _validate_contents(connection):
    try:
        if connection.execute("PRAGMA user_version").fetchone()[0] >= 4:
            from wiedan.core.device_fields import FIELD_TYPES, load_definitions, parse_documentation_value

            definitions = load_definitions(connection)
            names = set()
            for uid, definition in definitions.items():
                UUID(uid)
                name = (definition["type_id"], definition["name"].strip().casefold())
                if not name[1] or name in names or definition["value_type"] not in FIELD_TYPES:
                    raise ValueError("Ungültiges oder doppeltes Dokumentationsfeld")
                names.add(name)
            for row in connection.execute("SELECT v.*,d.type_id FROM device_field_values v JOIN devices d ON d.uid=v.device_uid"):
                definition = definitions[row["field_uid"]]
                if definition["type_id"] != row["type_id"]:
                    raise ValueError("Dokumentationsfeld passt nicht zum Gerätetyp")
                value = json.loads(row["value_json"])
                parsed = parse_documentation_value(definition, value)
                if parsed is None or type(parsed) is not type(value):
                    raise ValueError("Ungültiger Wert im Dokumentationsfeld")
        if connection.execute("PRAGMA user_version").fetchone()[0] >= 3:
            for row in connection.execute("SELECT id,label FROM device_categories"):
                if not all(isinstance(value, str) and value.strip() for value in row):
                    raise ValueError("Ungültige Gerätekategorie")
            connection.execute("SELECT category_id FROM device_types").fetchall()
        if connection.execute("PRAGMA user_version").fetchone()[0] >= 2:
            from wiedan.core.working_configuration import available_parameters, configuration_errors

            entries = {}
            for row in connection.execute("SELECT p.*,d.type_id FROM device_parameters p JOIN devices d ON d.uid=p.device_uid"):
                if row["name"] == "ip" or row["name"] not in available_parameters(row["type_id"]):
                    raise ValueError("Parameter passt nicht zum Gerätetyp")
                value = json.loads(row["value_json"])
                if type(value) not in {str, int}:
                    raise ValueError("Ungültiger Parameterwert")
                entry = entries.setdefault(row["device_uid"], {"type": row["type_id"], "parameters": {}})
                entry["parameters"][row["name"]] = value
            if any(configuration_errors(entry) for entry in entries.values()):
                raise ValueError("Ungültige Gerätekonfiguration im Datenstamm")
        metadata = connection.execute("SELECT * FROM database_info").fetchone()
        UUID(metadata["uid"])
        if not isinstance(metadata["data_version"], str) or not metadata["data_version"].strip():
            raise ValueError("Datenstand fehlt")
        for table in ("projects", "vehicles", "nodes", "devices"):
            for row in connection.execute(f"SELECT uid FROM {table}"):
                UUID(row[0])
        for table, column in (("credentials", "values_json"), ("device_types", "definition_json"),
                              ("logging_sets", "definition_json"),
                              ("devices", "connection_overrides"), ("devices", "commissioning_overrides")):
            for row in connection.execute(f"SELECT {column} FROM {table}"):
                if not isinstance(json.loads(row[0]), dict):
                    raise TypeError("Ungültige Objektdaten")
        for row in connection.execute("SELECT definition_json FROM device_types"):
            definition = json.loads(row[0])
            if (not isinstance(definition.get("label"), str)
                    or not isinstance(definition.get("connection"), dict)
                    or not isinstance(definition.get("pingable"), bool)
                    or (definition.get("commissioning_connection") is not None
                        and not isinstance(definition["commissioning_connection"], dict))):
                raise ValueError("Ungültige Gerätetypdefinition")
        projects = list(connection.execute("SELECT uid FROM projects"))
        for project in projects:
            nodes = {row["uid"]: row for row in connection.execute("SELECT * FROM nodes WHERE project_uid=?", (project[0],))}
            legacy = connection.execute("PRAGMA user_version").fetchone()[0] < 3
            if legacy and sum(row["parent_uid"] is None and row["vehicle_uid"] is None for row in nodes.values()) != 1:
                raise ValueError("Zentrale fehlt oder ist mehrfach vorhanden")
            vehicles = {row[0] for row in connection.execute("SELECT uid FROM vehicles WHERE project_uid=?", (project[0],))}
            roots = [row["vehicle_uid"] for row in nodes.values() if row["parent_uid"] is None and row["vehicle_uid"]]
            if legacy and (len(roots) != len(vehicles) or set(roots) != vehicles):
                raise ValueError("Fahrzeugstruktur fehlt oder ist mehrfach vorhanden")
            for row in nodes.values():
                if legacy and row["parent_uid"] and nodes[row["parent_uid"]]["vehicle_uid"] != row["vehicle_uid"]:
                    raise ValueError("Widersprüchliche Fahrzeugzuordnung im Strukturbaum")
            for uid in nodes:
                visited = set()
                while uid is not None:
                    if uid in visited:
                        raise ValueError("Zyklische Projektstruktur")
                    visited.add(uid)
                    uid = nodes[uid]["parent_uid"]
        for row in connection.execute("SELECT installation_position,track_start,track_end FROM devices"):
            if any(value is not None and (type(value) not in {int, float} or not math.isfinite(value)) for value in row):
                raise ValueError("Ungültige Positionsangabe")
    except (ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ProjectDatabaseError(f"Ungültiger Datenstamm: {exc}") from exc
