import json
from fastapi.testclient import TestClient
from app.db import connect, migrate
from app.main import create_app
from conftest import reference_model


def project(client):
    r = client.post("/api/projects", json={"name": "Cable test ZN2219", "client": "Atelier"})
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    aid = client.get(f"/api/projects/{pid}/assemblies").json()[0]["id"]
    return pid, aid


def test_reference_persistence_exports_revision_and_conflict(client):
    pid, aid = project(client)
    model = reference_model().model_dump(mode="json")
    model["drawing"]["drawing_number"] = "PLAN-001"
    payload = {"name": "ZN2219", "version": 1, "data": model}
    r = client.put(f"/api/assemblies/{aid}", json=payload)
    assert r.status_code == 200, r.text
    loaded = client.get(f"/api/assemblies/{aid}").json()
    assert loaded["data"] == model and loaded["version"] == 2
    assert client.put(f"/api/assemblies/{aid}", json=payload).status_code == 409
    svg = client.get(f"/api/assemblies/{aid}/export/svg").text
    assert all(s in svg for s in ["J1", "J2", "Blindage", "PLAN-001", "#df3434"])
    pdf = client.get(f"/api/assemblies/{aid}/export/pdf?page=A3")
    assert pdf.content.startswith(b"%PDF-") and len(pdf.content) > 1000
    assert "J1;A;J2;A" in client.get(f"/api/assemblies/{aid}/export/csv").text
    assert len(client.get(f"/api/assemblies/{aid}/bom").json()) == 8
    assert (
        client.post(
            f"/api/assemblies/{aid}/revisions", json={"code": "A", "description": "Création"}
        ).status_code
        == 201
    )
    assert client.get(f"/api/assemblies/{aid}").json()["data"]["drawing"]["revision"] == "A"
    with connect() as db:
        assert len(json.loads(db.execute("SELECT snapshot FROM revisions").fetchone()[0])["connections"]) == 4
    clone = client.post(f"/api/projects/{pid}/duplicate").json()["id"]
    assert len(client.get(f"/api/projects/{clone}/assemblies").json()) == 1
    assert client.delete(f"/api/projects/{pid}").status_code == 400
    assert client.delete(f"/api/projects/{pid}?confirm=true").status_code == 200
    assert client.get(f"/api/assemblies/{aid}").status_code == 404


def test_auth_csrf_and_ownership(client):
    _, aid = project(client)
    with TestClient(create_app(), headers={"X-CablePlan-Access-Channel": "lan"}) as c:
        assert c.get("/api/projects").status_code == 401
        assert (
            c.post(
                "/api/login",
                headers={"Origin": "https://evil.invalid"},
                json={"username": "alice", "password": "test-password-12345"},
            ).status_code
            == 403
        )
        r = c.post("/api/login", json={"username": "alice", "password": "test-password-12345"})
        assert r.status_code == 200 and "HttpOnly" in r.headers["set-cookie"]
        assert c.post("/api/projects", json={"name": "Alice"}).status_code == 403
        c.headers["X-CSRF-Token"] = r.json()["csrf"]
        assert c.get(f"/api/assemblies/{aid}").status_code == 404
        assert c.get("/api/settings/network").status_code == 403
        assert (
            c.put(
                "/api/settings/network", json={"allow_tunnel_access": True, "confirm_internet": True}
            ).status_code
            == 403
        )
        assert c.post("/api/projects", json={"name": "Alice"}).status_code == 201
        assert len(c.get("/api/projects").json()) == 1
        assert c.post("/api/logout").status_code == 200
        assert c.get("/api/me").status_code == 401


def test_network_default_toggle_persistence_audit(client):
    assert client.get("/health").status_code == 200
    for path in ["/", "/health", "/static/app.js", "/api/projects"]:
        r = client.get(path, headers={"X-CablePlan-Access-Channel": "tunnel"})
        assert r.status_code == 403 and "ZN2219" not in r.text
    assert client.get("/health", headers={"X-CablePlan-Access-Channel": "unknown"}).status_code == 403
    assert client.put("/api/settings/network", json={"allow_tunnel_access": True}).status_code == 400
    assert (
        client.put(
            "/api/settings/network",
            json={
                "allow_tunnel_access": True,
                "confirm_internet": True,
                "public_url": "https://cableplan.pigeonfou.com",
            },
        ).status_code
        == 200
    )
    assert client.get("/health", headers={"X-CablePlan-Access-Channel": "tunnel"}).status_code == 200
    migrate()
    assert client.get("/api/settings/network").json()["allow_tunnel_access"] is True
    with TestClient(create_app(), headers={"X-CablePlan-Access-Channel": "tunnel"}) as c:
        assert c.get("/health").status_code == 200
    assert client.put("/api/settings/network", json={"allow_tunnel_access": False}).status_code == 200
    assert client.get("/health", headers={"X-CablePlan-Access-Channel": "tunnel"}).status_code == 403
    assert client.get("/health").status_code == 200
    with connect() as db:
        logs = list(db.execute("SELECT detail FROM audit_log WHERE action='network.access'"))
        assert len(logs) == 2 and json.loads(logs[0][0]) == {"old": False, "new": True}


def test_direct_mode_ignores_untrusted_channel(environment, monkeypatch):
    monkeypatch.setenv("CABLEPLAN_PROXY_MODE", "direct")
    with TestClient(create_app()) as c:
        assert c.get("/health", headers={"X-CablePlan-Access-Channel": "tunnel"}).status_code == 200


def test_library_reuse_does_not_modify_instances(client):
    _, aid = project(client)
    model = reference_model().model_dump(mode="json")
    r = client.post(
        "/api/library", json={"kind": "connector", "name": "6 contacts", "data": model["connectors"][0]}
    )
    assert r.status_code == 201
    assert (
        client.put(f"/api/assemblies/{aid}", json={"name": "Cable", "version": 1, "data": model}).status_code
        == 200
    )
    assert client.delete("/api/library/" + r.json()["id"]).status_code == 200
    assert (
        client.get(f"/api/assemblies/{aid}").json()["data"]["connectors"][0]["pins"]
        == model["connectors"][0]["pins"]
    )


def test_login_rate_limit(environment):
    with TestClient(create_app(), headers={"X-CablePlan-Access-Channel": "lan"}) as c:
        for _ in range(10):
            assert c.post("/api/login", json={"username": "alice", "password": "wrong"}).status_code == 401
        assert c.post("/api/login", json={"username": "alice", "password": "wrong"}).status_code == 429
