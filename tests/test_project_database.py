import hashlib
import sqlite3
from pathlib import Path

import pytest

from tools.migrate_yaml import LegacySource, build_database, verify_migration
from wiedan.core.model import (
    list_projects,
    load_project,
    project_photo,
)
from wiedan.core.project_database import (
    FORMAT_VERSION,
    SUPPORTED_FORMATS,
    ProjectDatabaseError,
    connect,
    database_path,
    inspect_database,
    select_database,
)
from wiedan.core.scalance_config import W700, load_set, new_set, save_set
from wiedan.core.settings import load_settings

ARCHIVE = Path(__file__).resolve().parents[1] / "archive" / "yaml-data-2026-10-18"


def test_all_projects_share_one_ssot_without_data_loss():
    before = database_path().read_bytes()
    verify_migration(LegacySource(ARCHIVE), database_path())
    projects = [load_project(name) for name in list_projects()]
    assert len({project.database_path for project in projects}) == 1
    assert all(project.schema_version in SUPPORTED_FORMATS for project in projects)
    assert database_path().read_bytes() == before  # Öffnen migriert die mitgelieferte Datenbank nicht.
    assert len(list(database_path().parent.glob("*.sqlite"))) == 1


def test_application_connection_cannot_write():
    path = database_path()
    before = path.read_bytes()
    with pytest.raises(ProjectDatabaseError, match="readonly"), connect() as connection:
        connection.execute("PRAGMA query_only=OFF")
        connection.execute("UPDATE projects SET name='Should never happen'")
    assert path.read_bytes() == before
    with connect() as connection:
        assert connection.execute("PRAGMA query_only").fetchone()[0] == 1


def test_reading_and_configuration_work_do_not_mutate_ssot():
    project = load_project("xuzhou")
    before = hashlib.sha256(project.database_path.read_bytes()).digest()
    device = next(d for d in project.devices.values() if d.type == W700)
    data = new_set(project)
    data["devices"][device.id] = {"type": W700, "parameters": {"role": "Access Point", "channel": 165}}
    save_set(data, "Standard")
    assert load_set(project, "Standard")["devices"][device.id]["parameters"]["channel"] == 165
    project_photo(project.id)
    list_projects()
    assert hashlib.sha256(project.database_path.read_bytes()).digest() == before


def test_complete_database_can_be_replaced_by_selecting_new_local_release(storage, database_release):
    first = load_project("xuzhou")
    release = storage / "Stammdaten 2026-10.sqlite"
    database_release(release, data_version="2026.10")
    select_database(release)
    second = load_project("xuzhou")
    assert second.uid == first.uid
    assert second.database_uid != first.database_uid
    assert second.data_version == "2026.10"
    assert second.database_path == release
    assert all(second.devices[key].uid == device.uid for key, device in first.devices.items())
    assert len(list_projects()) == inspect_database()["project_count"]
    assert load_settings()["database_path"] == str(release.resolve())


def test_positions_and_device_identity_load_from_ssot(storage, database_release):
    project = load_project("xuzhou")
    device = next(d for d in project.devices.values() if d.type == W700)
    assert device.installation_position is None and device.track_start is None and device.track_end is None
    # Simulation eines bereitgestellten Datenstands, ausdrücklich außerhalb der App-Anbindung.
    release = storage / "release.sqlite"
    database_release(release, data_version="Mit Positionen")
    connection = sqlite3.connect(release)
    with connection:
        connection.execute("UPDATE devices SET path=?, label=?, installation_position=?, track_start=?, track_end=? WHERE uid=?",
                           ("central/network/RenamedAP", "AP neu", 120.5, 100, 240, device.uid))
    connection.close()
    select_database(release)
    renamed = load_project(project.id).devices["central/network/RenamedAP"]
    assert renamed.uid == device.uid
    assert (renamed.installation_position, renamed.track_start, renamed.track_end) == (120.5, 100, 240)


@pytest.mark.parametrize("version", [0, FORMAT_VERSION + 1])
def test_incompatible_database_is_rejected_without_modification(storage, version, database_release):
    current = database_path()
    release = storage / "future.sqlite"
    database_release(release, data_version="Future")
    connection = sqlite3.connect(release)
    connection.execute(f"PRAGMA user_version={version}")
    connection.close()
    before = release.read_bytes()
    with pytest.raises(ProjectDatabaseError, match="Datenbankformat"):
        select_database(release)
    assert database_path() == current
    assert release.read_bytes() == before


def test_invalid_content_does_not_change_connection_setting(storage, database_release):
    current = database_path()
    release = storage / "invalid.sqlite"
    database_release(release, data_version="Invalid")
    connection = sqlite3.connect(release)
    with connection:
        connection.execute("UPDATE device_types SET definition_json='invalid json'")
    connection.close()
    with pytest.raises(ProjectDatabaseError, match="Ungültiger Datenstamm"):
        select_database(release)
    assert database_path() == current


def test_builder_does_not_overwrite_a_published_database():
    current = database_path()
    before = current.read_bytes()
    with pytest.raises(ProjectDatabaseError, match="existiert"):
        build_database(current, source=ARCHIVE, data_version="Oops")
    assert current.read_bytes() == before


def test_running_application_reads_no_project_or_type_yaml(monkeypatch):
    import yaml

    project = load_project("xuzhou")

    def no_yaml(*args):
        pytest.fail("Laufender Betrieb muss vollständig aus der SSOT lesen")

    monkeypatch.setattr(yaml, "safe_load", no_yaml)
    assert load_project(project.id).devices == project.devices
    assert list_projects()
    assert project_photo(project.id)
