"""Stammdaten laden. Daten sind read-only und liegen im Paket (auch in der .exe)."""
from dataclasses import dataclass, field
from functools import cache
from importlib.resources import files

import yaml


@dataclass(frozen=True)
class Device:
    id: str  # Pfad, z. B. "fzg_03/inverter" oder "central/metering/iso_ups1"
    vehicle: str | None  # None = Zentrale
    label: str
    type: str
    pingable: bool
    connection: dict
    commissioning_connection: dict | None = None
    category: str | None = None  # inverter, plc, comms, io; None = nicht zugeordnet


_NODE_KEYS = {"label", "state", "devices"}


@dataclass
class Node:
    """Strukturknoten (Gruppe) im Projektbaum. Blätter sind immer Geräte."""
    id: str  # Pfad, z. B. "central/network"
    label: str
    state: str | None = None  # z. B. operational
    children: list["Node"] = field(default_factory=list)
    devices: list[str] = field(default_factory=list)  # Geräte-IDs dieses Knotens

    def walk_devices(self):
        """Alle Geräte-IDs dieses Knotens und aller Unterknoten."""
        yield from self.devices
        for child in self.children:
            yield from child.walk_devices()


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    full_name: str
    credentials: dict
    devices: dict[str, Device]
    live: bool  # Live-Betrieb in diesem Projekt realisiert
    vehicles: dict[str, str]  # Fahrzeug-ID -> Label
    control: str  # Steuerungstyp, z. B. HIMA
    product: str  # Produkttyp der Fahrzeuge, z. B. CoasterKart
    vehicle_products: dict[str, str]  # Fahrzeug-ID -> Produkttyp
    central: "Node"  # Strukturbaum der Zentrale (aus YAML)
    vehicle_nodes: dict[str, "Node"]  # Fahrzeug-ID -> Strukturbaum des Fahrzeugs

    def find(self, type=None, vehicle=None, central=None):
        """Geräte filtern. central=True: nur Zentrale, central=False: nur Fahrzeuge."""
        return [
            d for d in self.devices.values()
            if (type is None or d.type == type)
            and (vehicle is None or d.vehicle == vehicle)
            and (central is None or (d.vehicle is None) == central)
        ]


def _data(*parts: str):
    path = files("wiedan") / "data"
    for part in parts:
        path = path / part
    return path


def project_photo(project_id: str) -> bytes | None:
    """Projektfoto `projects/<id>.jpg` oder `.png`, falls vorhanden."""
    for ext in ("jpg", "png"):
        path = _data("projects", f"{project_id}.{ext}")
        if path.is_file():
            return path.read_bytes()
    return None


def _read_yaml(*parts: str) -> dict:
    return yaml.safe_load(_data(*parts).read_text(encoding="utf-8"))


@cache
def _load_device_type(type_id: str) -> dict:
    return _read_yaml("library", "device_types", f"{type_id}.yaml")["device_type"]


def list_projects() -> list[str]:
    return sorted(p.name[:-5] for p in _data("projects").iterdir() if p.name.endswith(".yaml"))


def load_project(project_id: str) -> Project:
    raw = _read_yaml("projects", f"{project_id}.yaml")
    devices = {}

    def add(vehicle, dev_id, d):
        t = _load_device_type(d["type"])
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
        )

    def build(vehicle, path, key, raw_node):
        """Knoten aus YAML lesen: Alles ausser label/state/devices mit dict-Wert ist ein Unterknoten."""
        path = (*path, key)
        node = Node(
            id="/".join(path),
            label=raw_node.get("label", key),
            state=raw_node.get("state"),
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
    )
