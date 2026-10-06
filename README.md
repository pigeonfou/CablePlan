# CablePlan

Application web de conception locale de plans de câblage. Vous définissez les connecteurs, les pins et les conducteurs ; CablePlan construit le plan SVG et ses exports PDF/CSV.

## V0.1

- Projets et assemblages multiples ; duplication, archivage, recherche et tri.
- Connecteurs gauche/droite/libres, pins alphanumériques, bibliothèque locale.
- Création de liaisons par clic sur deux pins ou formulaire ; tableau éditable.
- AWG, mm², couleurs, longueurs, dénudages, références, isolation et terminaison.
- Dérivations explicitement autorisées, blindages boîtier/pin et gaines/accessoires.
- Cartouche, cotes, révisions avec instantanés, nomenclature.
- PDF vectoriel A4/A3 paysage, SVG, CSV et export des données JSON.
- Authentification locale Argon2id, rôles, audit et contrôle d’accès aux projets.

## Architecture

Python 3.12+ / FastAPI / SQLite / HTML-CSS-JavaScript / SVG / ReportLab. Pas de Docker, Node, CDN, service cloud ou accès Internet requis pour l’usage métier. L’installation et les mises à jour téléchargent des paquets ; le runner GitHub et cloudflared sont des services séparés.

Production : Nginx rejoint CablePlan par une socket Unix. Une entrée LAN injecte `lan` et une entrée locale `127.0.0.1:8081` dédiée à cloudflared injecte `tunnel`. L’accès distant est **désactivé par défaut**, persistant en SQLite et modifiable uniquement par un administrateur avec confirmation. Lorsqu’il est activé, les communications publiques passent par Cloudflare.

## Installation

Suivre [docs/INSTALL_UBUNTU.md](docs/INSTALL_UBUNTU.md) pour Ubuntu 24.04/26.04, le compte admin, le runner, la clé de déploiement et le tunnel. La mise en service sur ces OS et les tests publics doivent être validés sur votre serveur ; la compatibilité Python seule ne valide pas une installation Ubuntu entière.

## Développement

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
cableplan migrate
cableplan create-user admin
cableplan serve
```

Ouvrir `http://127.0.0.1:8000`. Le mode direct ignore tout header de canal reçu et n’écoute que localhost. Ne pas l’utiliser pour un reverse proxy public ; systemd active le mode `nginx` via la socket Unix.

```bash
python -m ruff check --isolated --select E4,E7,E9,F app tests
python -m pytest -q
```

Voir les limites de la V0.1 et le suivi de validation dans [docs/STATUS.md](docs/STATUS.md).
