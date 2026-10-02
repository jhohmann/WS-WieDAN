from wiedan.core.model import list_projects, load_project


def test_xuzhou():
    assert "xuzhou" in list_projects()
    p = load_project("xuzhou")
    assert len(p.devices) == 64
    assert len(p.find(central=True)) == 4
    assert len(p.find(type="nidec_m700")) == 20
    assert len(p.find(vehicle="fzg_03")) == 3
    assert p.devices["fzg_03/inverter"].connection["ip"] == "192.168.196.32"
    assert p.devices["fzg_03/plc"].commissioning_connection["protocol"] == "modbus_tcp"
