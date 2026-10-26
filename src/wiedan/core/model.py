"""Gemeinsames Projektmodell mit lesendem SQLite-Zugriff."""
from dataclasses import dataclass, field
from pathlib import Path


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
    uid: str = ""  # Dauerhafte Identität; id bleibt der lesbare Pfad für die bestehende UI.
    installation_position: float | None = None  # Meter relativ zum Strecken-Nullpunkt
    track_start: float | None = None
    track_end: float | None = None
    parameters: dict = field(default_factory=dict)
    documentation: dict = field(default_factory=dict)  # Feld-UUID -> Wert; keine Geräteparameter.


@dataclass
class Node:
    """Strukturknoten (Gruppe) im Projektbaum. Blätter sind immer Geräte."""
    id: str  # Pfad, z. B. "central/network"
    label: str
    state: str | None = None  # z. B. operational
    children: list["Node"] = field(default_factory=list)
    devices: list[str] = field(default_factory=list)  # Geräte-IDs dieses Knotens
    uid: str = ""
    vehicle: str | None = None

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
    central: "Node"  # Strukturbaum der Zentrale
    vehicle_nodes: dict[str, "Node"]  # Fahrzeug-ID -> Strukturbaum des Fahrzeugs
    uid: str = ""
    database_path: Path | None = None
    schema_version: int = 0
    data_version: str = ""
    database_uid: str = ""
    display_name: str = ""
    root_nodes: list[Node] = field(default_factory=list)
    device_field_definitions: dict = field(default_factory=dict)

    def find(self, type=None, vehicle=None, central=None):
        """Geräte filtern. central=True: nur Zentrale, central=False: nur Fahrzeuge."""
        return [
            d for d in self.devices.values()
            if (type is None or d.type == type)
            and (vehicle is None or d.vehicle == vehicle)
            and (central is None or (d.vehicle is None) == central)
        ]


def project_photo(project_id: str) -> bytes | None:
    from wiedan.core.project_database import project_photo as read_photo

    return read_photo(project_id)


def list_projects() -> list[str]:
    from wiedan.core.project_database import list_projects as stored_projects

    return stored_projects()


def load_project(project_id: str) -> Project:
    from wiedan.core.project_database import load_project as stored_project

    return stored_project(project_id)
