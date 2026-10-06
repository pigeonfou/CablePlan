# État V0.1

## Validé dans l’environnement de développement

- 15 tests automatisés : graphe, AWG/unités, persistance SQLite, conflit de version, suppression protégée, bibliothèque, révisions, auth/CSRF/permissions, exports et règles tunnel/audit.
- Parcours réel Chromium : login, création projet, J1/J2 A..F, quatre connexions par clic sur les pins, blanc/rouge/noir/bleu AWG22 350 mm, blindage boîtier, gaine, accessoire, longueur modifiée et persistante après rechargement, zoom, téléchargement PDF, activation réseau.
- PDF ouvert/rasterisé et examiné : plan vectoriel avec pins, conducteurs, blindage, cartouche, cotes et tableau.
- Compilation Python, lint, syntaxe JavaScript et shell. Package wheel construit avec migrations et ressources locales.

## À valider sur le serveur Ubuntu

L’environnement de développement n’est pas votre serveur. Installation Ubuntu 24.04/26.04, systemd, permissions socket, Nginx réel, runner, clé Git, déploiement/rollback/restauration et DNS/tunnel ne sont pas encore validés ici. La CI GitHub doit réussir pour le commit courant. Ces critères restent ouverts jusqu’au test réel.

Parcours serveur attendu : créer `Cable test ZN2219`, J1 et J2 pins A..F, liens A-A blanc, B-B rouge, F-F noir, C-C bleu, AWG22 350 mm ; blindage boîtier-boîtier ; sauvegarder/recharger ; examiner SVG/PDF ; tester utilisateur standard. Puis tunnel false → 403 et LAN disponible ; true après confirmation → login public ; false → 403 immédiat. Vérifier le header de canal falsifié via Nginx, la persistance après restart et après un nouveau déploiement, puis tester une restauration sur base de test.

## Limites identifiées

- Les vues connecteurs sont génériques. Les photos et placements physiques de pins circulaires personnalisés ne sont pas encore éditables graphiquement.
- Positions libres par coordonnées ; pas de routage automatique anticollision ni placement par glisser-déposer des connecteurs.
- Les dérivations utilisent plusieurs connexions partageant une pin, avec autorisation explicite. Nœuds d’épissure et sous-faisceaux dédiés restent à ajouter.
- PDF vectoriel complet pour les petits assemblages ; les très grands graphes nécessiteront une pagination de la partie graphique. Le tableau est paginé.
- Bibliothèque spécialisée pour connecteurs ; les autres catégories ont un formulaire de propriétés JSON.
- Révisions avec snapshot conservé ; interface de comparaison/restauration d’une révision, import JSON et XLSX à ajouter.
- Paramètres réseau, thème local et cartouche présents ; logo d’entreprise et paramètres généraux complets restent à ajouter.
- Le statut tunnel n’est pas sondé par l’application et reste explicitement inconnu.

Aucune donnée d’exemple n’est injectée dans la production ; `examples/zn2219.json` est une fixture explicite.
