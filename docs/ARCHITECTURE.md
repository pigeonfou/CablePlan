# Architecture

L’application s’exécute sous `cableplan`, SQLite dans `/var/lib/cableplan`, releases dans `/opt/cableplan/releases/<SHA>`, lien courant `/opt/cableplan/current`. Nginx utilise la socket Unix `/run/cableplan/app.sock` accessible au groupe www-data. Aucun port backend n’est exposé en production.

Tables relationnelles : users, sessions, projects, assemblies, library, revisions, site_settings, audit_log, login_attempts et migrations. Les assemblages sont des documents JSON strictement validés par Pydantic ; c’est un choix V0.1 pour sauvegarder atomiquement un graphe, conserver les snapshots et permettre l’export/import futur. Les identifiants métier sont UUID, distincts des libellés utilisateur.

Project → plusieurs CableAssembly. Chaque assemblage contient ConnectorInstance et Pin ; une ConnectorDefinition provient de la bibliothèque et est copiée dans l’instance pour éviter les changements rétroactifs. Connection associe deux Endpoint et un Conductor. Shield contient zéro, un ou deux Endpoint ; `pin_id=null` désigne le boîtier. Sheath et Accessory sont indépendants. Une épissure peut être documentée comme accessoire et la dérivation comme plusieurs connexions avec pins partagées autorisées ; le nœud d’épissure intermédiaire dédié reste une évolution.

`properties` permet des extensions techniques locales. Le contrat JSON refuse les propriétés non déclarées hors de cet espace. Drawing décrit le cartouche et les cotes. Revision conserve un instantané complet. La modification d’un assemblage utilise une version atomique (409 si conflit). Les migrations SQL embarquées sont appliquées une seule fois ; elles ne réinitialisent jamais site_settings.

SVG et PDF partagent un calcul de placement déterministe. Les conducteurs sont des objets techniques, avec une bordure foncée pour les couleurs claires. PDF produit des tracés et textes vectoriels avec ReportLab. Les ressources navigateur sont locales ; aucun appel externe n’est présent dans l’application.
