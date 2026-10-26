"""Typgebundene Dokumentationsfelder; unabhängig von Geräteparametern."""

import math

FIELD_TYPES = {"text": "Text", "number": "Zahl", "boolean": "Ja / Nein"}


def load_definitions(connection):
    if connection.execute("PRAGMA user_version").fetchone()[0] < 4:
        return {}
    return {row["uid"]: dict(row) for row in connection.execute(
        "SELECT * FROM device_field_definitions ORDER BY name")}


def parse_documentation_value(definition, value):
    if value is None or isinstance(value, str) and not value.strip():
        return None
    kind = definition["value_type"]
    if kind == "text":
        if not isinstance(value, str):
            raise ValueError(f"{definition['name']}: Bitte Text eingeben.")
        return value
    if kind == "number":
        try:
            number = float(str(value).strip().replace(",", "."))
            if not math.isfinite(number):
                raise ValueError
            return number
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{definition['name']}: Bitte eine endliche Zahl eingeben.") from exc
    if kind == "boolean" and type(value) is bool:
        return value
    raise ValueError(f"{definition['name']}: Bitte Ja oder Nein auswählen.")
