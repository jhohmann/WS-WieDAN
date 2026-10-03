"""Stammdaten laden. Daten sind read-only und liegen im Paket (auch in der .exe)."""
from dataclasses import dataclass
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


@dataclass(frozen=True)
class Project:
    id: str
    name: str
    credentials: dict
    devices: dict[str, Device]
    live: bool  # Live-Betrieb in diesem Projekt realisiert
    vehicles: dict[str, str]  # Fahrzeug-ID -> Label

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


def _read_yaml(*parts: str) -> dict:
    return yaml.safe_load(_data(*parts).read_text(encoding="utf-8"))


def list_projects() -> list[str]:
    return sorted(p.name[:-5] for p in _data("projects").iterdir() if p.name.endswith(".yaml"))


def load_project(project_id: str) -> Project:
    raw = _read_yaml("projects", f"{project_id}.yaml")
    devices = {}

    def add(vehicle, name, d):
        dev_id = f"{vehicle or 'central'}/{name}"
        t = _read_yaml("library", "device_types", f"{d['type']}.yaml")["device_type"]
        comm = t.get("commissioning_connection")
        devices[dev_id] = Device(
            id=dev_id,
            vehicle=vehicle,
            label=d.get("label", t["label"]),
            type=d["type"],
            pingable=d.get("pingable", t["pingable"]),
            connection={**t["connection"], "ip": d["ip"]},
            commissioning_connection={**comm, "ip": d["ip"]} if comm else None,
        )

    for name, d in raw["central"]["devices"].items():
        add(None, name, d)
    for vid, v in raw["vehicles"].items():
        for name, d in v["devices"].items():
            add(vid, name, d)
    return Project(
        id=raw["id"],
        name=raw["name"],
        credentials=raw.get("credentials", {}),
        devices=devices,
        live=raw.get("live", False),
        vehicles={vid: v.get("label", vid) for vid, v in raw["vehicles"].items()},
    )
