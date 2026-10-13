# Journal des modifications

Toutes les évolutions notables de SimpleLog sont listées dans ce fichier.

## [Non publié]

### Ajouté
- Journal des modifications, disponible en 5 langues et dans l'application (Aide → Nouveautés).
- Quand une nouvelle version est disponible, la fenêtre de mise à jour liste les changements depuis votre version.

### Modifié
- SSH : l'empreinte de la clé du serveur est désormais affichée pour confirmation à la première connexion à un hôte, et une clé modifiée est refusée.
- Les identifiants et profils enregistrés ne sont désormais lisibles que par votre compte utilisateur.

### Corrigé
- macOS : la mise à jour intégrée pouvait supprimer tout le dossier Applications au lieu de remplacer seulement SimpleLog. Elle ne remplace désormais que l'app SimpleLog, et conserve l'ancienne en cas de problème. La mise à jour s'exécutant depuis la version déjà installée, la 1.0.8 et les versions antérieures ne peuvent plus se mettre à jour toutes seules sur macOS : téléchargez la nouvelle version une fois depuis le site ou avec Homebrew.
- Kubernetes : les logs apparaissent immédiatement au lieu de seulement après 200 lignes.
- Loki, GCP, Datadog et Fly.io : les mêmes lignes de log ne réapparaissent plus en boucle pendant le suivi d'une source.
- Loki, Datadog et Elasticsearch : le chargement initial affiche désormais les logs les plus récents au lieu des plus anciens de la période. GCP ne saute plus d'entrées lors des pics d'activité.
- Un court problème réseau n'interrompt plus le suivi d'une source avec une fenêtre d'erreur : SimpleLog réessaie, et ne signale une erreur qu'après plusieurs échecs consécutifs.
- Appuyer sur Entrée dans un champ de texte (recherche, filtre, formulaires) n'insère plus de ligne de séparation dans le log courant.
- Ouvrir un log en panneau divisé alors que l'onglet contient déjà 9 panneaux affiche maintenant un message, au lieu de lancer en silence un log qui n'est jamais affiché.
- Ouvrir de nombreuses connexions enregistrées ne ralentit plus l'application au fil du temps : leurs fenêtres, minuteurs et connexions SSH sont libérés à la fermeture.
- Fichiers locaux : le suivi d'un fichier continue de fonctionner après sa rotation ou son vidage, les lignes écrites en deux fois ne sont plus coupées et les caractères accentués ne sont plus corrompus.

## [1.0.8] - 2026-09-30

### Ajouté
- Rouvrir une connexion enregistrée la reconnecte automatiquement et restaure la cible sélectionnée (log group, projet, service, pod, worker…) et les options, pour tous les fournisseurs. Il suffit de cliquer sur Ouvrir.

### Corrigé
- AWS CloudWatch : les identifiants enregistrés sont désormais pré-remplis à la réouverture d'une connexion.

## [1.0.7] - 2026-08-19

### Corrigé
- macOS : les builds de release fonctionnent à nouveau (ils échouaient depuis la 1.0.4).
- Les liens et la vérification des mises à jour pointent vers la nouvelle organisation GitHub simple-log-app.

## [1.0.6] - 2026-07-29

### Corrigé
- La molette de la souris ne modifie plus par erreur les listes déroulantes pendant le défilement.

## [1.0.5] - 2026-07-29

### Ajouté
- Menu clic droit pour copier les lignes de log sélectionnées.

## [1.0.4] - 2026-07-29

### Corrigé
- Plusieurs lignes de log peuvent désormais être sélectionnées en même temps.

## [1.0.3] - 2026-05-25

### Corrigé
- macOS : correction d'un crash au lancement.

## [1.0.2] - 2026-05-25

### Corrigé
- macOS : correction d'un crash au lancement.

## [1.0.1] - 2026-05-21

### Modifié
- Nettoyage interne et meilleure couverture de tests.

## [1.0.0] - 2026-05-20

### Ajouté
- Première version : visualiseur de logs pour fichiers locaux, stdin, AWS CloudWatch, SSH, Docker, Kubernetes, Vercel, Google Cloud, Azure, Loki, Datadog, Elasticsearch, Railway, Fly.io et Cloudflare Workers.
