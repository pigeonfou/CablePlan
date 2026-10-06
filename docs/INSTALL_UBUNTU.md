# Installation Ubuntu 24.04 / 26.04

Cible : machine x86_64, installation native, LAN privé. Garder la session SSH ouverte pendant l’installation. Aucun mot de passe par défaut n’est fourni.

## 1. Préparer Ubuntu et l’accès au dépôt privé

```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y git gh
 gh auth login --hostname github.com --git-protocol https --web
 gh auth setup-git
 git clone https://github.com/pigeonfou/CablePlan.git "$HOME/CablePlan"
 cd "$HOME/CablePlan"
```

`gh auth login` demande une validation dans votre navigateur. Ne communiquez pas vos tokens dans la conversation. Si le répertoire existe déjà, utiliser `git pull --ff-only` plutôt que le recréer.

## 2. Installer l’application

```bash
cd "$HOME/CablePlan"
sudo bash scripts/install-ubuntu.sh
```

Saisir l’adresse IPv4 LAN du serveur. Le script crée l’utilisateur `cableplan`, SQLite, l’environnement Python, systemd, Nginx et les outils de déploiement. Il préserve les paramètres existants. L’entrée tunnel est sur `127.0.0.1:8081`, l’entrée LAN sur votre IP port 80.

Sur un serveur déjà utilisé, examiner les sites Nginx avant l’installation. CablePlan ne remplace pas les sites existants. Ne pas rediriger le port LAN depuis la box Internet. Pour un LAN non fiable, ajouter un certificat local et HTTPS au listener LAN : les cookies sont Secure sur HTTPS, mais HTTP LAN ne chiffre pas les mots de passe.

## 3. Créer le premier administrateur

```bash
sudo -u cableplan env CABLEPLAN_DATA=/var/lib/cableplan /opt/cableplan/current/.venv/bin/cableplan create-user admin
```

Mot de passe demandé deux fois, 12 caractères minimum. Puis ouvrir `http://IP_LAN/`. L’application ne crée aucun utilisateur ni projet d’exemple automatiquement.

Vérifier :

```bash
sudo /usr/local/sbin/cableplan-diagnose
curl -i http://127.0.0.1:8081/health
```

Résultat tunnel initial attendu : HTTP 403 ; le LAN fonctionne.

## 4. Autoriser les mises à jour du dépôt privé

```bash
sudo bash scripts/setup-github-deployment.sh
```

Copier **la clé publique affichée** dans [CablePlan / Settings / Deploy keys](https://github.com/pigeonfou/CablePlan/settings/keys). Laisser l’autorisation d’écriture décochée.

```bash
sudo bash scripts/setup-github-deployment.sh --verify
```

La clé privée reste dans `/etc/cableplan/git`, accessible uniquement à root. La connexion Git utilise SSH sur port 443 avec empreinte serveur vérifiée. Après validation, vous pouvez déconnecter `gh` du compte utilisateur si cet accès personnel n’est plus utile.

## 5. Runner GitHub

Dans [Settings / Actions / Runners](https://github.com/pigeonfou/CablePlan/settings/actions/runners), choisir New self-hosted runner, Linux x64 et obtenir le token temporaire.

```bash
sudo bash scripts/install-runner.sh
```

Coller le token dans la saisie masquée. Le script installe le runner sous `cableplan-runner`, labels `self-hosted, linux, x64, cableplan`, et le service systemd officiel. S’il n’existe pas de checksum publié pour le binaire, le script s’arrête : suivre alors les instructions et checksum affichés par GitHub, dans `/home/cableplan-runner/actions-runner`, sous `cableplan-runner`.

## 6. Cloudflare

Dans Cloudflare Zero Trust, créer un tunnel cloudflared nommé CablePlan. Ajouter le hostname `cableplan.pigeonfou.com`, service **HTTP `127.0.0.1:8081`**. Activer HTTPS côté public ; ne jamais cibler le listener LAN.

```bash
sudo bash scripts/install-cloudflared.sh
```

Le token reste sur le serveur. Si cloudflared existe déjà pour une autre application, ajouter CablePlan au tunnel existant et conserver le service. Renseigner alors `CABLEPLAN_TUNNEL_CONFIGURED=1` dans `/etc/cableplan/cableplan.env` et redémarrer CablePlan. Cette valeur indique seulement que le tunnel est configuré ; elle n’affirme pas qu’il est connecté.

Le tunnel peut être connecté tout en renvoyant 403. Depuis le LAN, se connecter comme admin : Administration → Réseau et accès → adresse publique → autoriser l’accès distant → confirmer. Tester le login public. Désactiver depuis le LAN : le public doit immédiatement revenir à 403.

## 7. Première mise à jour

Un push sur main lance Tests sur GitHub (Python 3.12 et 3.14). Deploy ne s’exécute qu’après succès pour un push de ce dépôt sur main. Le runner appelle le helper root déjà installé, avec le SHA exact. Le helper refuse un SHA qui n’est plus le head de main.

Si le premier workflow Deploy a été exécuté avant l’installation du runner, reprendre son job depuis GitHub Actions après connexion du runner. Un runner absent ne déploie rien.

Vérifier le commit dans Administration et `/health`, puis créer le câble de référence décrit dans `docs/STATUS.md`. Redémarrer les services et vérifier la persistance de l’autorisation tunnel.

## 8. Sauvegardes et rollback

```bash
sudo /usr/local/sbin/cableplan-backup
sudo /usr/local/sbin/cableplan-rollback
```

Le rollback restaure code, base et configuration de la sauvegarde précédente : les modifications postérieures à cette sauvegarde ne sont pas conservées dans la base active, mais une sauvegarde de l’état courant est créée avant restauration. Voir `BACKUP_RESTORE.md`.

## Sources officielles consultées

- [Runner Linux et service](https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/configure-the-application?platform=linux)
- [Cloudflared et dépôt apt](https://pkg.cloudflare.com/index.html)
- [SSH GitHub sur port 443](https://docs.github.com/en/authentication/troubleshooting-ssh/using-ssh-over-the-https-port)
- [Empreintes SSH GitHub](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/githubs-ssh-key-fingerprints)
