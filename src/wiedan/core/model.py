"""Stammdaten laden. Daten sind read-only und liegen im Paket (auch in der .exe)."""
from dataclasses import dataclass
from functools import cache
from importlib.resources import files

import yaml


@dataclass(frozen=True)
class Device:
    id: str  # Pfad, z. B. "fzg_03/inverter" oder "central/iso_ups1"
    vehicle: str | None  # None = Zentrale
    label: str
    type: str
    pingable: bool
    connection: dict
    commissioning_connection: dict | None = None
    category: str | None = None  # inverter, plc, comms, io; None = nicht zugeordnet


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

    def add(vehicle, name, d):
        dev_id = f"{vehicle or 'central'}/{name}"
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

    for name, d in raw["central"]["devices"].items():
        add(None, name, d)
    for vid, v in raw["vehicles"].items():
        for name, d in v["devices"].items():
            add(vid, name, d)
    return Project(
        id=raw["id"],
        name=raw["name"],
        full_name=raw.get("full_name", ""),
        credentials=raw.get("credentials", {}),
        devices=devices,
        live=raw.get("live", False),
        vehicles={vid: v.get("label", vid) for vid, v in raw["vehicles"].items()},
        control=raw["control"],
        product=raw["product"],
        vehicle_products={vid: v.get("product", raw["product"]) for vid, v in raw["vehicles"].items()},
    )
