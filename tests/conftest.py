"""Jeder Test bekommt eine eigene lokale Projektablage."""

import shutil
import sqlite3
import tempfile
from pathlib import Path
from uuid import uuid4

import pytest

from wiedan.core.project_database import database_path


@pytest.fixture
def database_release():
    """Einen neuen Datenstand außerhalb der lesenden App-Anbindung simulieren."""
    def create(destination, *, data_version):
        shutil.copyfile(database_path(), destination)
        connection = sqlite3.connect(destination)
        try:
            with connection:
                connection.execute("UPDATE database_info SET uid=?, data_version=?", (str(uuid4()), data_version))
        finally:
            connection.close()
        return destination

    return create


@pytest.fixture(autouse=True)
def storage(monkeypatch):
    root = Path(tempfile.gettempdir()).resolve()
    directory = root / f"wiedan-test-{uuid4().hex}"
    directory.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(directory))
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")
    yield directory
    assert directory.resolve().parent == root and directory.name.startswith("wiedan-test-")
    shutil.rmtree(directory)
