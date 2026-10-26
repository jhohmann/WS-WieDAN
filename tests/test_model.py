from wiedan.core.model import list_projects, load_project


def test_xuzhou():
    assert "CK Xuzhou" in list_projects()
    project = load_project("xuzhou")
    assert len(project.devices) == 255
    assert list(project.central.walk_devices())
    assert project.uid
    assert project.database_path.suffix == ".sqlite"
    assert project.schema_version == 1
