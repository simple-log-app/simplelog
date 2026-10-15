# Journal des modifications

Toutes les évolutions notables de SimpleLog sont listées dans ce fichier.

## [Non publié]

## [2.2.1] - 2026-10-15

### Corrigé
- Les boîtes de message (À propos, mise à jour, erreurs, confirmations) perdent elles aussi la barre de titre du système, comme les autres dialogues.

## [2.2.0] - 2026-10-15

### Modifié
- Les fenêtres de dialogue n'ont plus la barre de titre du système : plus de boutons réduire / agrandir et elles ne se déplacent plus ; fermez-les avec ✕ ou Échap.

## [2.1.3] - 2026-10-15

### Corrigé
- Linux : « Ajouter » et les connexions enregistrées fonctionnent de nouveau dans l'application installée (elles ne faisaient rien en 2.1.2).
- Le menu Auto / Jour / Nuit n'est plus sombre en mode Jour.

## [2.1.2] - 2026-10-15

### Modifié
- Réorganisation interne de l'application ; rien ne change dans l'apparence ni le fonctionnement de SimpleLog.

## [2.1.1] - 2026-10-15

### Corrigé
- Le curseur de souris « chargement » ne reste plus affiché plusieurs secondes quand vous cliquez sur « Ajouter » ou ouvrez une connexion enregistrée (Linux/GNOME).

## [2.1.0] - 2026-10-14

### Ajouté
- Le thème peut désormais suivre le réglage clair / sombre de votre système : choisissez « Auto » avec la flèche à côté du bouton Jour / Nuit.
- Filtre par niveau : affichez ou masquez les lignes ERROR, WARN, INFO, DEBUG et TRACE avec les pastilles de l'onglet Filtre.
- Recherche et filtre : nouvelles options « respecter la casse » et « expression régulière », et vos termes récents sont proposés pendant la saisie (↓ dans un champ vide pour les lister).
- Règles de coloration (menu Édition) : colorez dans tous vos logs les mots qui comptent pour vous, avec respect de la casse et expressions régulières en option.
- Marque-pages : repérez des lignes avec Ctrl+B (ou le menu clic droit) et passez de l'une à l'autre avec F2 / Maj+F2, ou retirez-les tous d'un coup (Ctrl+Maj+B).
- Export : enregistrez dans un fichier les lignes affichées (après vos filtres) ou seulement la sélection, depuis le menu Fichier (Ctrl+Maj+E) ou le menu clic droit.
- Vue fusionnée (menu Édition ou clic droit) : affichez plusieurs logs ouverts dans un seul onglet, par ordre chronologique, chaque ligne indiquant sa source.
- Les onglets distants affichent leur état de connexion (pastille de couleur sur le logo) et se reconnectent tout seuls quand le flux se coupe, sans dupliquer de lignes ; désactivable dans le menu Fichier.
- Nouvelles sources de logs : le journal systemd local, Heroku, Render, Splunk, Better Stack et Sentry (événements d'erreur).

### Modifié
- Ajout d'une connexion : les choix « Split » de « Ouvrir comme » sont grisés tant qu'aucun log n'est ouvert, puisqu'il n'y a encore rien à scinder.

### Corrigé
- Le curseur de souris « chargement » ne reste plus affiché environ 12 secondes au lancement de SimpleLog (Linux/GNOME).

## [2.0.0] - 2026-10-14

### Ajouté
- Recherche : F3 passe au résultat suivant et Maj+F3 au précédent ; les raccourcis sont indiqués dans l'infobulle des boutons.
- Mode Jour / Nuit : changez de thème avec le bouton à droite de la barre de menus (ou avec Ctrl+Maj+L) ; votre choix est mémorisé.

### Modifié
- Nouveau look : palette sombre repensée avec un accent citron vert, pour une meilleure lisibilité.
- Sources distantes : la liste n'affiche plus que les services pour lesquels vous avez des connexions enregistrées, avec un lien « + Nouvelle connexion » et une suppression en deux étapes.
- Ajout d'une connexion : un sélecteur filtrable sur 4 colonnes avec le logo officiel de chaque service, et un formulaire de connexion plus clair.
- Les logos des services apparaissent sur les onglets, et le choix « Ouvrir comme » tient sur une seule ligne.

### Corrigé
- Le bouton ET / OU entre les termes de recherche et de filtre s'affiche désormais dans votre langue.

## [1.0.9] - 2026-10-13

### Ajouté
- Journal des modifications, disponible en 5 langues et dans l'application (Aide → Nouveautés).
- Quand une nouvelle version est disponible, la fenêtre de mise à jour liste les changements depuis votre version.
- Nouvelle option « Retour ligne » dans la barre du log : désactivez-la pour afficher chaque log sur une seule ligne (défilement horizontal pour les longues), ce qui est plus rapide sur de très gros logs.

### Modifié
- SSH : l'empreinte de la clé du serveur est désormais affichée pour confirmation à la première connexion à un hôte, et une clé modifiée est refusée.
- Les identifiants et profils enregistrés ne sont désormais lisibles que par votre compte utilisateur.
- Beaucoup plus rapide avec les flux de logs soutenus (SSH, Docker, Kubernetes, stdin, fichiers) : les lignes sont ajoutées par groupes, et les longs logs restent fluides pendant le suivi, le redimensionnement ou le changement d'onglet.
- Ctrl+W ferme désormais l'onglet courant ; fermer tous les logs se fait avec Ctrl+Maj+W.
- Les horodatages de la vue des logs s'affichent désormais en heure locale au lieu de l'UTC.
- Démarrage plus rapide, et l'ouverture d'un gros fichier avec un très grand nombre de lignes est désormais quasi instantanée.
- Les cartes de fournisseurs de « Ajouter une connexion » affichent désormais une courte description de chaque source au survol.
- Les messages d'état, erreurs de connexion et infobulles qui étaient toujours en anglais suivent désormais la langue choisie.
- Les mises à jour sont désormais vérifiées avec l'empreinte publiée avec la version, et un téléchargement corrompu est supprimé.

### Corrigé
- CloudWatch : une connexion basée sur un profil AWS utilise désormais la région définie pour ce profil dans `~/.aws/config`.
- L'application ne plante plus quand une connexion échoue juste après la fermeture de son onglet, ni quand votre fichier de configuration AWS contient un profil en double.
- Fichier → Ouvrir (Ctrl+O) n'ouvre plus le fichier en double.
- Les logs Docker, Kubernetes, SSH et ceux reçus par pipe ne s'arrêtent plus silencieusement sur une ligne contenant des caractères invalides.
- Charger un très gros lot de lignes (par exemple `cat gros.log | simplelog`) ne laisse plus de lignes fantômes dans la vue.
- Fly.io : un token invalide ou une application inconnue affichent désormais une erreur au lieu d'un log vide sans fin.
- Azure : les conditions supplémentaires de votre requête (par exemple sur la sévérité) sont conservées pendant le suivi, et les lignes ingérées en retard ne sont plus manquées.
- Kubernetes : un pod qui affiche beaucoup d'avertissements ne bloque plus le flux de logs.
- La mise à jour automatique sous Linux (AppImage) fonctionne désormais quand le chemin d'installation contient une apostrophe.
- Une mise à jour est refusée quand les sommes de contrôle publiées ne listent pas le fichier téléchargé.
- Le titre « Erreur » et les boutons « Préc./Suiv. » et « + clé=val » suivent désormais la langue choisie.
- Les filtres clé=valeur sont environ 2× plus rapides sur les logs JSON.
- macOS : la mise à jour intégrée pouvait supprimer tout le dossier Applications au lieu de remplacer seulement SimpleLog. Elle ne remplace désormais que l'app SimpleLog, et conserve l'ancienne en cas de problème. La mise à jour s'exécutant depuis la version déjà installée, la 1.0.8 et les versions antérieures ne peuvent plus se mettre à jour toutes seules sur macOS : téléchargez la nouvelle version une fois depuis le site ou avec Homebrew.
- Kubernetes : les logs apparaissent immédiatement au lieu de seulement après 200 lignes.
- Loki, GCP, Datadog et Fly.io : les mêmes lignes de log ne réapparaissent plus en boucle pendant le suivi d'une source.
- Loki, Datadog et Elasticsearch : le chargement initial affiche désormais les logs les plus récents au lieu des plus anciens de la période. GCP ne saute plus d'entrées lors des pics d'activité.
- Un court problème réseau n'interrompt plus le suivi d'une source avec une fenêtre d'erreur : SimpleLog réessaie, et ne signale une erreur qu'après plusieurs échecs consécutifs.
- Appuyer sur Entrée dans un champ de texte (recherche, filtre, formulaires) n'insère plus de ligne de séparation dans le log courant.
- Ouvrir un log en panneau divisé alors que l'onglet contient déjà 9 panneaux affiche maintenant un message, au lieu de lancer en silence un log qui n'est jamais affiché.
- Ouvrir de nombreuses connexions enregistrées ne ralentit plus l'application au fil du temps : leurs fenêtres, minuteurs et connexions SSH sont libérés à la fermeture.
- Fichiers locaux : le suivi d'un fichier continue de fonctionner après sa rotation ou son vidage, les lignes écrites en deux fois ne sont plus coupées et les caractères accentués ne sont plus corrompus.
- Recherche : les résultats sont surlignés en jaune translucide, au bon endroit sur les lignes qui passent à la ligne ; le ET / OU entre les termes est respecté ; les lignes JSON qui correspondent sont surlignées ; et la vue ne revient plus au premier résultat pendant le suivi d'un log.
- Un clic droit ou une sélection à la souris sur une ligne JSON ne la déplie ou ne la replie plus ; seul un simple clic le fait.
- Ouvrir un fichier avec `simplelog fichier.log` depuis un autre dossier alors que SimpleLog est déjà lancé fonctionne désormais.
- Fermer un onglet ou quitter ne fige plus l'application pendant plusieurs secondes.
- Activer ou désactiver les horodatages redimensionne maintenant correctement les lignes qui passent à la ligne.
- Les connexions et identifiants enregistrés ne peuvent plus être perdus si l'application plante pendant l'enregistrement.
- Elasticsearch 8 et suivants : le suivi des logs refonctionne (il utilisait un tri que les versions récentes refusent).
- Mises à jour : un téléchargement incomplet est détecté, et l'installation d'une mise à jour .deb ne fige plus la fenêtre.
- CloudWatch, Docker et SSH : lister les groupes de logs, les flux et les conteneurs, et ouvrir un log SSH, ne figent plus l'application pendant l'attente du réseau.
- Le navigateur de fichiers SFTP, les sessions SSH / GCP / Azure restaurées et la liste des clusters Kubernetes ne figent plus l'application pendant l'attente du réseau.
- Le badge de source dans la barre du log affichait un libellé interne comme « src_ssh » ; il affiche désormais le nom de la source.
- Les connexions Google Cloud enregistrées affichent désormais leur projet à côté de leur nom.
- Azure : le suivi en direct fonctionne aussi avec une requête écrite sur une seule ligne ou avec une limite de lignes (`take`/`limit`) avant le filtre.
- CloudWatch : les événements qui arrivent avec quelques secondes de retard ne sont plus manqués pendant le suivi.
- Railway : le suivi d'un service ne garde plus toutes les lignes en mémoire, et sélectionner plusieurs services à la suite n'ouvre plus de connexions en trop.
- Azure : le chargement initial d'une table ou d'une requête qui limite ses lignes affiche désormais les lignes les plus récentes au lieu des plus anciennes.
- Railway : le suivi d'un service ne récupère plus que les nouvelles lignes au lieu de retélécharger tous ses logs à chaque actualisation.

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
