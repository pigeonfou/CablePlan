# CI/CD

Tests s’exécute sur push main et pull request, avec Python 3.12/3.14 : installation du package, compilation, lint, pytest, syntaxe shell et JavaScript.

Deploy est déclenché par workflow_run Tests réussi, uniquement pour un push main du dépôt courant. Il ne checkout aucun script à exécuter comme root. Le runner `cableplan-runner` appelle `/usr/local/sbin/cableplan-deploy SHA`.

Le helper root a été installé et examiné lors de l’installation initiale. Il verrouille le déploiement, récupère main dans le miroir root et vérifie le SHA. Installation de la release/venv/pip sous l’utilisateur cableplan, puis arrêt, sauvegarde, migration sous cableplan, changement de lien courant, redémarrage et contrôle health. Si migration ou contrôle échoue, restauration automatique base, configuration et release. Une sauvegarde qui échoue entraîne le redémarrage de la version existante.

Le paramètre tunnel en SQLite n’est jamais réinitialisé. Seul le commit dans l’environnement est mis à jour. Un nouveau commit qui arrive entre les tests et le déploiement rend l’ancien obsolète : le helper le refuse, le workflow du nouveau commit le remplacera après tests.

Les helpers root, systemd et Nginx ne sont pas remplacés automatiquement par un push pour éviter l’exécution automatique de code de dépôt avec privilèges système. Leur mise à jour nécessite une installation administrative explicite et revue. Les fonctionnalités applicatives ordinaires passent bien automatiquement par GitHub → tests → runner → déploiement.
