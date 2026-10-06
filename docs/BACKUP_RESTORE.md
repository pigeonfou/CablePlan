# Sauvegarde et restauration

`sudo cableplan-backup` crée un dossier privé daté dans `/var/backups/cableplan` : copie SQLite cohérente via l’API backup, configuration, chemin de release. Pendant un déploiement, l’application est arrêtée pour que cette base précède exactement les migrations. La restauration valide l’intégrité SQLite.

`sudo cableplan-restore /var/backups/cableplan/<dossier>` restaure une sauvegarde précise ; `sudo cableplan-rollback` choisit la plus récente. Une sauvegarde de l’état actif est créée avant restauration. Les fichiers WAL/SHM anciens sont supprimés service arrêté. Les données plus récentes que le snapshot ne figurent plus dans la base active.

Les releases associées restent conservées. Ne pas supprimer une release encore référencée par une sauvegarde. La configuration sauvegardée contient potentiellement la clé privée Git : protéger les copies hors serveur et les chiffrer.

Rotation disponible : `sudo bash scripts/rotate-backups.sh`. Elle garde au moins 10 sauvegardes et toutes celles datant de moins de 30 jours. La planifier après validation d’une restauration. Vérifier régulièrement l’espace libre ; le serveur n’est pas une sauvegarde contre la perte de disque. Conserver une copie locale externe chiffrée.
