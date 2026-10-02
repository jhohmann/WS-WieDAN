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

    def find(self, type=None, vehicle=None, central=None):
        """Geräte filtern. central=True: nur Zentrale, central=False: nur Fahrzeuge."""
        return [
            d for d in self.devices.values()
            if (type is None or d.type == type)
            and (vehicle is None or d.vehicle == vehicle)
            and (central is None or (d.vehicle is None) == central)
        ]


def list_projects() -> list[str]:
    folder = files("wiedan") / "data" / "projects"
    return sorted(p.name[:-5] for p in folder.iterdir() if p.name.endswith(".yaml"))


def load_project(project_id: str) -> Project:
    text = (files("wiedan") / "data" / "projects" / f"{project_id}.yaml").read_text(encoding="utf-8")
    raw = yaml.safe_load(text)
    devices = {}

    def add(vehicle, name, d):
        dev_id = f"{vehicle or 'central'}/{name}"
        devices[dev_id] = Device(
            id=dev_id, vehicle=vehicle, label=d["label"], type=d["type"],
            pingable=d["pingable"], connection=d["connection"],
            commissioning_connection=d.get("commissioning_connection"),
        )

    for name, d in raw["central"]["devices"].items():
        add(None, name, d)
    for vid, v in raw["vehicles"].items():
        for name, d in v["devices"].items():
            add(vid, name, d)
    return Project(raw["id"], raw["name"], raw.get("credentials", {}), devices)
