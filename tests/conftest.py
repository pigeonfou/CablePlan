import pytest
from fastapi.testclient import TestClient
from app.db import migrate
from app.main import create_app, create_user


@pytest.fixture
def environment(tmp_path, monkeypatch):
    monkeypatch.setenv("CABLEPLAN_DATA", str(tmp_path))
    monkeypatch.setenv("CABLEPLAN_PROXY_MODE", "nginx")
    migrate()
    for name, role in [("admin", "admin"), ("alice", "user"), ("bob", "user")]:
        create_user(name, "test-password-12345", role)
    return tmp_path


@pytest.fixture
def client(environment):
    with TestClient(create_app(), headers={"X-CablePlan-Access-Channel": "lan"}) as c:
        r = c.post("/api/login", json={"username": "admin", "password": "test-password-12345"})
        assert r.status_code == 200
        c.headers["X-CSRF-Token"] = r.json()["csrf"]
        yield c


def reference_model():
    from app.models import Assembly, Connector, Pin, Connection, Endpoint, Conductor, Shield, Sheath

    j1 = Connector(reference="J1", side="left", pins=[Pin(name=n) for n in "ABCDEF"])
    j2 = Connector(reference="J2", side="right", pins=[Pin(name=n) for n in "ABCDEF"])
    edges = []
    for name, color_name, color in [
        ("A", "Blanc", "#eeeeee"),
        ("B", "Rouge", "#df3434"),
        ("F", "Noir", "#202733"),
        ("C", "Bleu", "#2977cc"),
    ]:
        p1, p2 = next(p for p in j1.pins if p.name == name), next(p for p in j2.pins if p.name == name)
        edges.append(
            Connection(
                start=Endpoint(connector_id=j1.id, pin_id=p1.id),
                end=Endpoint(connector_id=j2.id, pin_id=p2.id),
                conductor=Conductor(color_name=color_name, color=color, awg=22, length=350),
            )
        )
    return Assembly(
        connectors=[j1, j2],
        connections=edges,
        shields=[Shield(start=Endpoint(connector_id=j1.id), end=Endpoint(connector_id=j2.id))],
        sheaths=[Sheath()],
    )
