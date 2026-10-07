import hashlib
import json
import os
import secrets
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from . import __version__, drawing
from .db import connect, data_dir, migrate, setting
from .models import Assembly

hasher = PasswordHasher()
STATIC = Path(__file__).parent / "static"


def now():
    return datetime.now(UTC).isoformat()


def audit(db, user_id, action, detail):
    db.execute(
        "INSERT INTO audit_log(date,user_id,action,detail) VALUES(?,?,?,?)",
        (now(), user_id, action, json.dumps(detail, ensure_ascii=False)),
    )


def hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()


def create_user(username, password, role="user"):
    if len(password) < 12:
        raise ValueError("Mot de passe : 12 caractères minimum")
    if role not in ("admin", "user") or not username.strip():
        raise ValueError("Identifiant ou rôle invalide")
    with connect() as db:
        db.execute(
            "INSERT INTO users(username,password_hash,role) VALUES(?,?,?)",
            (username.strip(), hasher.hash(password), role),
        )


def identity(request: Request):
    token = request.cookies.get("cableplan_session", "")
    with connect() as db:
        row = db.execute(
            "SELECT u.id,u.username,u.role,s.csrf FROM sessions s JOIN users u ON "
            "u.id=s.user_id WHERE s.token_hash=? AND s.expires>? AND u.active=1",
            (hash_token(token), time.time()),
        ).fetchone()
    if not row:
        raise HTTPException(401, "Connexion requise")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), row["csrf"]):
            raise HTTPException(403, "Jeton CSRF invalide")
    return dict(row)


def admin(user=Depends(identity)):
    if user["role"] != "admin":
        raise HTTPException(403, "Réservé aux administrateurs")
    return user


def project_access(db, pid, user):
    row = db.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    if not row or (row["owner_id"] != user["id"] and user["role"] != "admin"):
        raise HTTPException(404, "Projet introuvable")
    return dict(row)


def assembly_access(db, aid, user):
    row = db.execute("SELECT * FROM assemblies WHERE id=?", (aid,)).fetchone()
    if not row:
        raise HTTPException(404, "Assemblage introuvable")
    project = project_access(db, row["project_id"], user)
    return dict(row), project


class Login(BaseModel):
    username: str = Field(max_length=100)
    password: str = Field(max_length=1024)


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    reference: str = Field(default="", max_length=120)
    client: str = Field(default="", max_length=120)
    description: str = Field(default="", max_length=4000)
    archived: bool = False


class SaveAssembly(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    version: int = Field(ge=1)
    data: Assembly


class NetworkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    allow_tunnel_access: bool
    confirm_internet: bool = False
    public_url: str = Field(default="", max_length=200)


class LibraryInput(BaseModel):
    kind: str = Field(pattern=r"^(connector|contact|wire|cable|sheath|shield|accessory)$")
    name: str = Field(min_length=1, max_length=120)
    data: dict


class UserInput(Login):
    role: str = Field(default="user", pattern=r"^(admin|user)$")


class RevisionInput(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    description: str = Field(min_length=1, max_length=2000)


def create_app():
    migrate()
    base = os.environ.get("CABLEPLAN_BASE_PATH", "").rstrip("/")
    if base and (not base.startswith("/") or any(c not in "/abcdefghijklmnopqrstuvwxyz0123456789_-" for c in base)):
        raise ValueError("CABLEPLAN_BASE_PATH invalide")
    api = FastAPI(root_path=base, title="CablePlan", version=__version__, docs_url=None, redoc_url=None, openapi_url=None)
    # This is a trusted reverse-proxy deployment using a Unix socket. No public backend port.
    trusted_channel = os.environ.get("CABLEPLAN_PROXY_MODE", "direct") == "nginx"

    @api.middleware("http")
    async def boundary(request, call_next):
        channel = request.headers.get("x-cableplan-access-channel") if trusted_channel else "lan"
        if channel not in ("lan", "tunnel"):
            response = JSONResponse({"detail": "Canal proxy invalide"}, status_code=403)
        else:
            with connect() as db:
                blocked = channel == "tunnel" and setting(db, "allow_tunnel_access") != "true"
            if blocked:
                response = JSONResponse(
                    {
                        "detail": "Accès distant désactivé. L’application reste disponible "
                        "depuis le réseau local."
                    },
                    status_code=403,
                )
            elif (
                request.headers.get("content-length", "0").isdigit()
                and int(request.headers.get("content-length", "0")) > 8_000_000
            ):
                response = JSONResponse({"detail": "Document trop volumineux"}, status_code=413)
            else:
                response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
            "frame-ancestors 'none'; form-action 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @api.get("/")
    def index():
        return HTMLResponse((STATIC / "index.html").read_text().replace("__BASE_PATH__", base))

    @api.get("/static/{filename}")
    def static(filename: str):
        if filename not in ("app.js", "style.css"):
            raise HTTPException(404)
        return FileResponse(STATIC / filename)

    @api.get("/health")
    def health():
        try:
            with connect() as db:
                ok = db.execute("PRAGMA quick_check").fetchone()[0] == "ok"
            storage = os.access(data_dir(), os.W_OK)
            return JSONResponse(
                {
                    "web": True,
                    "database": ok,
                    "storage": storage,
                    "offline_dependencies": True,
                    "version": __version__,
                    "commit": os.environ.get("CABLEPLAN_COMMIT", "development"),
                },
                status_code=200 if ok and storage else 503,
            )
        except Exception:
            return JSONResponse({"web": True, "database": False}, status_code=503)

    @api.post("/api/login")
    def login(body: Login, request: Request, response: Response):
        # Login CSRF protection: reject browser requests from another origin.
        origin = request.headers.get("origin")
        host = request.headers.get("host", "")
        if origin and origin not in ("http://" + host, "https://" + host):
            raise HTTPException(403, "Origine invalide")
        key = hashlib.sha256(
            (
                body.username
                + "|"
                + request.headers.get("x-real-ip", request.client.host if request.client else "local")
            ).encode()
        ).hexdigest()
        limited = False
        with connect() as db:
            attempt = db.execute("SELECT * FROM login_attempts WHERE key=?", (key,)).fetchone()
            t = time.time()
            count = attempt["count"] if attempt and t - attempt["window"] < 300 else 0
            start = attempt["window"] if count else t
            if count >= 10:
                limited = True
            else:
                db.execute("INSERT OR REPLACE INTO login_attempts VALUES(?,?,?)", (key, count + 1, start))
            row = db.execute("SELECT * FROM users WHERE username=? AND active=1", (body.username,)).fetchone()
        if limited:
            raise HTTPException(429, "Réessayez dans quelques minutes")
        valid = False
        if row:
            try:
                valid = hasher.verify(row["password_hash"], body.password)
            except VerificationError:
                pass
        else:
            # Equal password-work cost for unknown accounts.
            hasher.hash(body.password)
        if not valid:
            raise HTTPException(401, "Identifiants invalides")
        token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
        with connect() as db:
            db.execute("DELETE FROM login_attempts WHERE key=?", (key,))
            db.execute("DELETE FROM sessions WHERE expires<?", (time.time(),))
            db.execute(
                "INSERT INTO sessions VALUES(?,?,?,?)",
                (hash_token(token), row["id"], csrf, time.time() + 8 * 3600),
            )
            audit(db, row["id"], "login", {})
        secure = request.url.scheme == "https" or (
            trusted_channel and request.headers.get("x-forwarded-proto") == "https"
        )
        response.set_cookie(
            "cableplan_session",
            token,
            max_age=8 * 3600,
            httponly=True,
            secure=secure,
            samesite="strict",
            path=base + "/",
        )
        return {"username": row["username"], "role": row["role"], "csrf": csrf}

    @api.post("/api/logout")
    def logout(request: Request, response: Response, user=Depends(identity)):
        with connect() as db:
            db.execute(
                "DELETE FROM sessions WHERE token_hash=?",
                (hash_token(request.cookies.get("cableplan_session", "")),),
            )
        response.delete_cookie("cableplan_session", path=base + "/")
        return {"ok": True}

    @api.get("/api/me")
    def me(user=Depends(identity)):
        return user

    @api.get("/api/projects")
    def projects(user=Depends(identity)):
        with connect() as db:
            rows = db.execute(
                "SELECT * FROM projects WHERE owner_id=? OR ?='admin' ORDER BY updated DESC",
                (user["id"], user["role"]),
            ).fetchall()
            return [dict(r) for r in rows]

    @api.post("/api/projects", status_code=201)
    def add_project(body: ProjectInput, user=Depends(identity)):
        pid, aid = str(uuid4()), str(uuid4())
        with connect() as db:
            db.execute(
                "INSERT INTO projects VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    pid,
                    user["id"],
                    body.name,
                    body.reference,
                    body.client,
                    body.description,
                    int(body.archived),
                    now(),
                    now(),
                ),
            )
            db.execute(
                "INSERT INTO assemblies VALUES(?,?,?,1,?)",
                (aid, pid, "Câble 1", Assembly().model_dump_json()),
            )
            audit(db, user["id"], "project.create", {"id": pid})
        return {"id": pid}

    @api.put("/api/projects/{pid}")
    def update_project(pid: str, body: ProjectInput, user=Depends(identity)):
        with connect() as db:
            project_access(db, pid, user)
            db.execute(
                "UPDATE projects SET name=?,reference=?,client=?,description=?,archived=?,updated=? "
                "WHERE id=?",
                (body.name, body.reference, body.client, body.description, int(body.archived), now(), pid),
            )
        return {"ok": True}

    @api.delete("/api/projects/{pid}")
    def delete_project(pid: str, confirm: bool = False, user=Depends(identity)):
        if not confirm:
            raise HTTPException(400, "Confirmation requise")
        with connect() as db:
            project_access(db, pid, user)
            db.execute("DELETE FROM projects WHERE id=?", (pid,))
            audit(db, user["id"], "project.delete", {"id": pid})
        return {"ok": True}

    @api.post("/api/projects/{pid}/duplicate", status_code=201)
    def duplicate_project(pid: str, user=Depends(identity)):
        new = str(uuid4())
        with connect() as db:
            p = project_access(db, pid, user)
            db.execute(
                "INSERT INTO projects VALUES(?,?,?,?,?,?,?,?,?)",
                (
                    new,
                    user["id"],
                    p["name"] + " — copie",
                    p["reference"],
                    p["client"],
                    p["description"],
                    0,
                    now(),
                    now(),
                ),
            )
            for a in db.execute("SELECT * FROM assemblies WHERE project_id=?", (pid,)).fetchall():
                db.execute(
                    "INSERT INTO assemblies VALUES(?,?,?,1,?)", (str(uuid4()), new, a["name"], a["data"])
                )
        return {"id": new}

    @api.get("/api/projects/{pid}/assemblies")
    def assemblies(pid: str, user=Depends(identity)):
        with connect() as db:
            project_access(db, pid, user)
            return [
                dict(r)
                for r in db.execute("SELECT id,name,version FROM assemblies WHERE project_id=?", (pid,))
            ]

    @api.post("/api/projects/{pid}/assemblies", status_code=201)
    def add_assembly(pid: str, body: ProjectInput, user=Depends(identity)):
        aid = str(uuid4())
        with connect() as db:
            project_access(db, pid, user)
            db.execute(
                "INSERT INTO assemblies VALUES(?,?,?,1,?)",
                (aid, pid, body.name, Assembly().model_dump_json()),
            )
        return {"id": aid}

    @api.get("/api/assemblies/{aid}")
    def get_assembly(aid: str, user=Depends(identity)):
        with connect() as db:
            row, project = assembly_access(db, aid, user)
            row["data"] = json.loads(row["data"])
            row["project"] = project
            return row

    @api.put("/api/assemblies/{aid}")
    def save_assembly(aid: str, body: SaveAssembly, user=Depends(identity)):
        with connect() as db:
            row, _ = assembly_access(db, aid, user)
            result = db.execute(
                "UPDATE assemblies SET name=?,data=?,version=version+1 WHERE id=? AND version=?",
                (body.name, body.data.model_dump_json(), aid, body.version),
            )
            if result.rowcount != 1:
                raise HTTPException(409, "Cet assemblage a changé ailleurs. Rechargez avant de sauvegarder.")
            db.execute("UPDATE projects SET updated=? WHERE id=?", (now(), row["project_id"]))
            audit(db, user["id"], "assembly.save", {"id": aid, "version": body.version + 1})
        return {"version": body.version + 1}

    @api.get("/api/assemblies/{aid}/export/{format}")
    def export(aid: str, format: str, page: str = "A4", user=Depends(identity)):
        with connect() as db:
            row, project = assembly_access(db, aid, user)
        model = Assembly.model_validate_json(row["data"])
        headers = {"Content-Disposition": f'attachment; filename="cableplan.{format}"'}
        if format == "svg":
            return Response(drawing.svg(model, project), media_type="image/svg+xml", headers=headers)
        if format == "pdf":
            if page not in ("A4", "A3"):
                raise HTTPException(400, "Format A4 ou A3 requis")
            return Response(drawing.pdf(model, project, page), media_type="application/pdf", headers=headers)
        if format == "csv":
            return Response(drawing.csv_export(model), media_type="text/csv", headers=headers)
        if format == "json":
            return Response(model.model_dump_json(indent=2), media_type="application/json", headers=headers)
        raise HTTPException(404)

    @api.get("/api/assemblies/{aid}/drawing")
    def live_drawing(aid: str, user=Depends(identity)):
        with connect() as db:
            row, project = assembly_access(db, aid, user)
        return Response(
            drawing.svg(Assembly.model_validate_json(row["data"]), project), media_type="image/svg+xml"
        )

    @api.get("/api/assemblies/{aid}/bom")
    def get_bom(aid: str, user=Depends(identity)):
        with connect() as db:
            row, _ = assembly_access(db, aid, user)
        return drawing.bom(Assembly.model_validate_json(row["data"]))

    @api.get("/api/assemblies/{aid}/revisions")
    def revisions(aid: str, user=Depends(identity)):
        with connect() as db:
            assembly_access(db, aid, user)
            return [
                dict(r)
                for r in db.execute(
                    "SELECT r.id,r.code,r.date,r.description,u.username FROM revisions r "
                    "JOIN users u ON u.id=r.user_id WHERE assembly_id=? ORDER BY date DESC",
                    (aid,),
                )
            ]

    @api.post("/api/assemblies/{aid}/revisions", status_code=201)
    def revision(aid: str, body: RevisionInput, user=Depends(identity)):
        with connect() as db:
            row, _ = assembly_access(db, aid, user)
            data = json.loads(row["data"])
            data["drawing"]["revision"] = body.code
            snapshot = Assembly.model_validate(data).model_dump_json()
            db.execute(
                "INSERT INTO revisions VALUES(?,?,?,?,?,?,?)",
                (str(uuid4()), aid, body.code, now(), user["id"], body.description, snapshot),
            )
            db.execute("UPDATE assemblies SET data=?,version=version+1 WHERE id=?", (snapshot, aid))
            audit(db, user["id"], "revision.create", {"assembly": aid, "code": body.code})
        return {"ok": True}

    @api.get("/api/library")
    def library(user=Depends(identity)):
        with connect() as db:
            rows = [dict(r) for r in db.execute("SELECT * FROM library ORDER BY kind,name")]
        for r in rows:
            r["data"] = json.loads(r["data"])
        return rows

    @api.post("/api/library", status_code=201)
    def add_library(body: LibraryInput, user=Depends(identity)):
        if body.kind == "connector":
            from .models import Connector

            Connector.model_validate(body.data)
        lid = str(uuid4())
        with connect() as db:
            db.execute(
                "INSERT INTO library VALUES(?,?,?,?)", (lid, body.kind, body.name, json.dumps(body.data))
            )
        return {"id": lid}

    @api.delete("/api/library/{lid}")
    def delete_library(lid: str, user=Depends(admin)):
        with connect() as db:
            db.execute("DELETE FROM library WHERE id=?", (lid,))
        return {"ok": True}

    @api.get("/api/settings/network")
    def network(user=Depends(admin)):
        with connect() as db:
            return {
                "allow_tunnel_access": setting(db, "allow_tunnel_access") == "true",
                "public_url": setting(db, "public_url"),
                "tunnel_configured": bool(os.environ.get("CABLEPLAN_TUNNEL_CONFIGURED")),
                "tunnel_status": "unknown",
                "version": __version__,
                "commit": os.environ.get("CABLEPLAN_COMMIT", "development"),
            }

    @api.put("/api/settings/network")
    def set_network(body: NetworkInput, user=Depends(admin)):
        if body.public_url and not body.public_url.startswith("https://"):
            raise HTTPException(400, "Adresse publique HTTPS requise")
        with connect() as db:
            previous = setting(db, "allow_tunnel_access") == "true"
            if body.allow_tunnel_access and not previous and not body.confirm_internet:
                raise HTTPException(400, "Confirmez le transit des communications par Cloudflare")
            value = "true" if body.allow_tunnel_access else "false"
            db.execute("UPDATE site_settings SET value=? WHERE key='allow_tunnel_access'", (value,))
            db.execute("UPDATE site_settings SET value=? WHERE key='public_url'", (body.public_url,))
            audit(db, user["id"], "network.access", {"old": previous, "new": body.allow_tunnel_access})
        return {"ok": True}

    @api.get("/api/admin/audit")
    def get_audit(user=Depends(admin)):
        with connect() as db:
            return [dict(r) for r in db.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 200")]

    @api.get("/api/admin/users")
    def users(user=Depends(admin)):
        with connect() as db:
            return [dict(r) for r in db.execute("SELECT id,username,role,active FROM users")]

    @api.post("/api/admin/users", status_code=201)
    def add_user(body: UserInput, user=Depends(admin)):
        try:
            create_user(body.username, body.password, body.role)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(409, "Identifiant indisponible") from exc
        return {"ok": True}

    return api

