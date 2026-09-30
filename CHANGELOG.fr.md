# Journal des modifications

Toutes les évolutions notables de SimpleLog sont listées dans ce fichier.

## [Non publié]

### Ajouté
- Journal des modifications, disponible en 5 langues et dans l'application (Aide → Nouveautés).
- Quand une nouvelle version est disponible, la fenêtre de mise à jour liste les changements depuis votre version.

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
