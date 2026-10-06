import argparse
import getpass
import json
import os
import sqlite3
from pathlib import Path

from .db import connect, data_dir, migrate


def main():
    parser = argparse.ArgumentParser(prog="cableplan")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("migrate")
    user = commands.add_parser("create-user")
    user.add_argument("username")
    user.add_argument("--role", choices=["admin", "user"], default="admin")
    reset = commands.add_parser("reset-password")
    reset.add_argument("username")
    backup = commands.add_parser("backup")
    backup.add_argument("destination")
    commands.add_parser("diagnose")
    serve = commands.add_parser("serve")
    serve.add_argument("--uds")
    serve.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    migrate()
    if args.command in ("create-user", "reset-password"):
        from .main import create_user, hasher

        password = getpass.getpass("Mot de passe (12 caractères minimum) : ")
        if password != getpass.getpass("Confirmation : "):
            parser.error("Les mots de passe diffèrent")
        if args.command == "create-user":
            create_user(args.username, password, args.role)
        else:
            if len(password) < 12:
                parser.error("12 caractères minimum")
            with connect() as db:
                result = db.execute(
                    "UPDATE users SET password_hash=? WHERE username=?",
                    (hasher.hash(password), args.username),
                )
                if result.rowcount != 1:
                    parser.error("Utilisateur introuvable")
                db.execute(
                    "DELETE FROM sessions WHERE user_id=(SELECT id FROM users WHERE username=?)",
                    (args.username,),
                )
        print("Compte mis à jour.")
    elif args.command == "backup":
        dest = Path(args.destination)
        dest.parent.mkdir(parents=True, exist_ok=True)
        with connect() as source, sqlite3.connect(dest) as target:
            source.backup(target)
        os.chmod(dest, 0o600)
        print("Sauvegarde créée.")
    elif args.command == "diagnose":
        with connect() as db:
            print(
                json.dumps(
                    {
                        "database": db.execute("PRAGMA quick_check").fetchone()[0],
                        "storage": os.access(data_dir(), os.W_OK),
                    }
                )
            )
    elif args.command == "serve":
        import uvicorn

        uvicorn.run(
            "app.main:create_app",
            factory=True,
            host="127.0.0.1",
            port=args.port,
            uds=args.uds,
            proxy_headers=False,
        )


if __name__ == "__main__":
    main()
