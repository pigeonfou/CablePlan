# Développement

Python 3.12 minimum. Créer une venv, installer `pip install -e '.[test]'`, lancer `cableplan migrate`, créer un utilisateur par CLI puis `cableplan serve`.

`CABLEPLAN_DATA` définit le dossier SQLite local ; valeur par défaut `.runtime`. `CABLEPLAN_PROXY_MODE=nginx` est réservé au déploiement derrière le proxy local de confiance. `CABLEPLAN_COMMIT` est informatif. Ne pas exposer le serveur de développement.

Les tests utilisent des bases temporaires et des comptes uniquement de test. Le test de référence couvre J1/J2, pins A..F, conducteurs blanc/rouge/noir/bleu AWG22 350 mm, blindage boîtier et gaine. `scripts/e2e-local.py` constitue un parcours de navigateur reproductible après `pip install playwright` et `python -m playwright install chromium` ; il crée une base temporaire, lance localhost, puis la supprime après le test.

Ne jamais injecter les fixtures dans la base de production. Ajouter une migration SQL numérotée pour changer le schéma. Les snapshots de révision préservent le contrat JSON à leur date ; une future évolution doit définir explicitement comment les relire.
