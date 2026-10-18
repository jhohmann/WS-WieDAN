"""Hardwareunabhängige Konfigurationssätze. Nur explizite Vorgaben werden gespeichert."""

import copy
import hashlib
import ipaddress
import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from wiedan.core.model import Project

W700 = "siemens_scalance_w700"
DEVICE_TYPES = {W700: "SCALANCE W700", "siemens_scalance_xc206": "SCALANCE XC-206"}


@dataclass(frozen=True)
class Parameter:
    label: str
    kind: str = "text"
    wireless: bool = False
    minimum: int = 0
    maximum: int = 0
    choices: tuple[str, ...] = ()
    hint: str = ""


# Fachliche Vorgaben, keine CLI-Befehle oder angenommenen Firmware-Defaults.
PARAMETERS = {
    "role": Parameter("Geräterolle", choices=("Access Point", "Client"), wireless=True),
    "system_name": Parameter("Gerätename", hint="1–63 Zeichen: Buchstaben, Ziffern, Punkt, _ oder -"),
    "netmask": Parameter("Subnetzmaske", "netmask", hint="z. B. 255.255.255.0"),
    "gateway": Parameter("Gateway", "ip"),
    "vlan": Parameter("Management-VLAN", "integer", minimum=1, maximum=4094),
    "ssid": Parameter("SSID", wireless=True, hint="1–32 Bytes (UTF-8)"),
    "channel": Parameter("Kanal", "integer", True, 1, 196, hint="Zulässigkeit hängt von Modell und Länderprofil ab"),
    "country": Parameter("Länderkennung", wireless=True, hint="Zwei Großbuchstaben, z. B. ME"),
    "band": Parameter("Frequenzband", wireless=True, choices=("2.4", "5")),
    "radio": Parameter("WLAN-Schnittstelle", wireless=True, hint="z. B. 0/1"),
    "beacon_interval": Parameter("Beacon-Intervall (ms)", "integer", True, 1, 65535),
    "hw_retries": Parameter("Hardware-Wiederholungen", "integer", True, 0, 255),
    "max_tx_power": Parameter("Max. Sendeleistung (dBm)", "integer", True, -100, 100),
    "ipcf": Parameter("iPCF", wireless=True, choices=("Ein", "Aus")),
    "ipcf_cycle_time": Parameter("iPCF-Zykluszeit (ms)", "integer", True, 1, 65535),
}


def project_devices(project: Project):
    return sorted((d for d in project.devices.values()
                   if d.type.startswith("siemens_") and d.category == "comms"),
                  key=lambda d: (d.type, d.id))


def available_parameters(device_type: str) -> dict[str, Parameter]:
    return {key: spec for key, spec in PARAMETERS.items() if not spec.wireless or device_type == W700}


def new_set(project: Project) -> dict:
    return {"schema_version": 2, "project": project.id, "name": "Neuer Satz", "devices": {}}


def blank_configuration(device_type: str) -> dict:
    return {"type": device_type, "parameters": {"role": ""} if device_type == W700 else {}}


def parse_value(key: str, text: str):
    if PARAMETERS[key].kind == "integer":
        try:
            return int(text)
        except ValueError:
            pass  # Unvollständige Eingaben bleiben als Entwurf speicherbar.
    return text


def configuration_errors(entry: dict) -> list[str]:
    values = entry["parameters"]
    errors = []
    if entry["type"] == W700 and not values.get("role"):
        errors.append("Geräterolle auswählen")
    for key, value in values.items():
        spec = PARAMETERS[key]
        valid = True
        if spec.choices:
            valid = value in spec.choices
        elif spec.kind == "integer":
            valid = type(value) is int and spec.minimum <= value <= spec.maximum
        elif spec.kind in {"ip", "netmask"}:
            try:
                if spec.kind == "ip":
                    ipaddress.IPv4Address(str(value))
                else:
                    valid = bool(re.fullmatch(r"\d+\.\d+\.\d+\.\d+", str(value)))
                    ipaddress.IPv4Network(f"0.0.0.0/{value}")
            except ValueError:
                valid = False
        elif key == "system_name":
            valid = bool(re.fullmatch(r"[A-Za-z0-9_.-]{1,63}", str(value)))
        elif key == "ssid":
            valid = isinstance(value, str) and 1 <= len(value.encode("utf-8")) <= 32
        elif key == "country":
            valid = bool(re.fullmatch(r"[A-Z]{2}", str(value)))
        elif key == "radio":
            valid = bool(re.fullmatch(r"\d+/\d+", str(value)))
        if not valid:
            errors.append(f"{spec.label}: Wert fehlt oder ist ungültig")
    if values.get("role") == "Client" and "channel" in values:
        errors.append("Kanal ist eine Vorgabe für Access Points; beim Client entfernen")
    return errors


def configuration_status(entry: dict | None) -> str:
    if entry is None:
        return "Keine Konfiguration"
    return "Entwurf" if configuration_errors(entry) else "Konfiguration hinterlegt"


def apply_template(data: dict, project: Project, device_ids: list[str], source: dict) -> None:
    """Eigenständige Kopien; individuelle Namen und Projektadressen nicht übertragen."""
    if any(project.devices[key].type != source["type"] for key in device_ids):
        raise ValueError("Die Vorlage passt nicht zu allen ausgewählten Gerätetypen.")
    for key in device_ids:
        previous = data["devices"].get(key, {}).get("parameters", {})
        entry = copy.deepcopy(source)
        entry["parameters"].pop("system_name", None)
        if "system_name" in previous:
            entry["parameters"]["system_name"] = previous["system_name"]
        data["devices"][key] = entry


def user_directory() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "WieDAN" / "scalance"


def project_directory(project_id: str) -> Path:
    name = re.sub(r"[^a-zA-Z0-9_-]", "_", project_id)[:48]
    digest = hashlib.sha256(project_id.encode()).hexdigest()[:8]
    return user_directory() / f"{name}-{digest}"


def set_path(project_id: str, name: str) -> Path:
    name = name.strip()
    if (not name or len(name) > 80 or re.search(r'[<>:"/\\|?*\x00-\x1f]', name)
            or name.endswith(".")
            or re.fullmatch(r"(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?", name)):
        raise ValueError("Bitte einen gültigen Satznamen ohne Pfadzeichen verwenden.")
    return project_directory(project_id) / f"{name}.yaml"


def list_sets(project_id: str) -> list[str]:
    return sorted(p.stem for p in project_directory(project_id).glob("*.yaml"))


def read_set(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as exc:
        raise ValueError("Die Datei enthält kein gültiges YAML.") from exc
    if not isinstance(data, dict) or data.get("schema_version") != 2:
        raise ValueError("Unbekanntes Konfigurationsformat (erwartet: Schema 2).")
    if not isinstance(data.get("project"), str) or not isinstance(data.get("name"), str):
        raise ValueError("Projekt oder Satzname fehlt.")  # noqa: TRY004 - ungültiges Dateiformat
    entries = data.get("devices")
    if not isinstance(entries, dict):
        raise ValueError("Gerätezuordnung fehlt.")  # noqa: TRY004 - ungültiges Dateiformat
    for device_id, entry in entries.items():
        if (not isinstance(device_id, str) or not isinstance(entry, dict)
                or not isinstance(entry.get("type"), str) or entry["type"] not in DEVICE_TYPES
                or not isinstance(entry.get("parameters"), dict)):
            raise ValueError("Ungültige Gerätekonfiguration.")
        allowed = available_parameters(entry["type"])
        for key, value in entry["parameters"].items():
            if key not in allowed or type(value) not in {str, int}:
                raise ValueError(f"Unbekannter Parameter oder falsches Datenformat: {key}")
    return data


def load_set(project: Project, name: str) -> dict:
    data = read_set(set_path(project.id, name))
    if data["project"] != project.id:
        raise ValueError("Dieser Satz gehört zu einem anderen Projekt. Bitte als Vorlage laden.")
    for key, entry in data["devices"].items():
        if key in project.devices and project.devices[key].type != entry["type"]:
            raise ValueError(f"Gerätetyp hat sich geändert: {key}")
    return data  # Nicht mehr vorhandene Geräte bleiben beim erneuten Speichern erhalten.


def save_set(data: dict, name: str) -> Path:
    path = set_path(data["project"], name)
    payload = {**data, "name": name.strip()}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".yaml.tmp")
    try:
        temporary.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    data["name"] = payload["name"]
    return path
