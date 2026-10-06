# Sécurité et confidentialité

Mot de passe Argon2id, tokens de session aléatoires stockés sous forme SHA-256, session de 8 h, cookie HttpOnly/SameSite Strict et Secure lorsque HTTPS. Vérification CSRF pour les mutations authentifiées et contrôle d’origine sur login. Limitation des tentatives de connexion. Le backend contrôle tous les droits ; un utilisateur accède à ses projets, l’administrateur à tous.

CSP self, requêtes SQLite paramétrées, SVG échappé, filtrage des fichiers statiques, aucune commande shell exécutée depuis une entrée Web. Les exports CSV neutralisent les cellules susceptibles d’être interprétées comme formules. La base, la configuration et les sauvegardes restent locales ; les secrets ne sont pas versionnés.

Deux listeners Nginx écrasent le header de canal reçu. CablePlan fait confiance uniquement à ce proxy sur la socket Unix en production ; le mode direct localhost ignore le header client. L’entrée tunnel est loopback. Un accès Internet au listener LAN contournerait par définition le choix tunnel : aucun NAT/WAN ne doit l’exposer. Le test réel Nginx est nécessaire avant mise en service.

L’autorisation tunnel est false au premier démarrage. Sa modification est réservée à l’administrateur, requiert une confirmation pour passer de false à true et génère une entrée d’audit. Même actif, le tunnel ne dispense pas de l’authentification. Toutes les routes, y compris statiques et health, sont bloquées par le canal tunnel désactivé.

Le service applicatif est isolé par systemd, sans droits root, et les connexions IP sortantes sont limitées à localhost. GitHub Runner et cloudflared restent des services réseau séparés. Le runner peut uniquement appeler le helper de déploiement root préinstallé ; aucun script reçu depuis son workspace n’est exécuté comme root. L’accès en lecture au Git privé est une clé de déploiement spécifique.

L’accès distant activé implique le transit du contenu consulté par Cloudflare. Le fonctionnement offline concerne l’usage métier sans tunnel ; les installations et mises à jour téléchargent leurs dépendances. Un administrateur doit protéger les fichiers système, utiliser HTTPS sur les réseaux non fiables et réserver les droits d’écriture Git aux personnes autorisées à déployer.
