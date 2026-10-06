# Cloudflare Tunnel

Créer CablePlan dans Cloudflare Zero Trust, hostname `cableplan.pigeonfou.com`, service HTTP `127.0.0.1:8081`. Le DNS doit pointer vers le tunnel choisi (configuration du hostname dans l’interface). Vérifier qu’HTTPS public est imposé. Le token appartient au service cloudflared, jamais à CablePlan ni au dépôt.

L’administrateur active volontairement l’accès depuis le LAN. Le bouton ne contacte aucune API Cloudflare : il modifie un booléen SQLite. Il n’arrête pas cloudflared. L’indicateur tunnel de l’application indique configuration déclarée et état de connexion inconnu ; `systemctl is-active cloudflared` et le tableau de bord Cloudflare servent au diagnostic réel.

Parcours : false → LAN utilisable et public 403 ; true après confirmation → login public ; utilisateur standard → modification réseau refusée ; false → public immédiatement 403. Vérifier la même valeur après redémarrage et déploiement. Un appel HTTP au listener tunnel avec un header `lan` doit rester bloqué lorsque false : Nginx écrase ce header.
