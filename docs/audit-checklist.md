# Audit SimpleLog : checklist

Légende : `[x]` fait · `[~]` partiellement fait · `[ ]` à faire.
Origine : *mesuré* (reproduit par un script), *code* (lu dans le code), *probable* (à confirmer sur un vrai service).

## 🔴 Urgent

- [x] **Mise à jour auto macOS : `rm -rf /Applications`** (`main_window.py`, `_apply_update`). Le chemin de l'app est calculé avec 3 `..` au lieu de 2, donc le script supprime `/Applications` puis copie l'app dans `/`.
  - [x] Corriger le calcul du bundle (2 niveaux) et refuser tout chemin qui ne finit pas par `.app`.
  - [x] Copier la nouvelle app **avant** de supprimer l'ancienne (et restaurer l'ancienne si la copie échoue).
  - [x] Monter le DMG avec `-mountpoint` : `awk '{print $NF}'` casse sur « SimpleLog 1.0.9 » (espace dans le nom du volume).
  - [x] Renommer l'asset macOS en `SimpleLog-macOS-universal.dmg` partout (release.yml, README, install.sh, html, update_tap.sh, build_macos.sh, `_auto_update_asset_url`) : les anciennes versions (≤ 1.0.8) obtiendront un 404 au lieu d'exécuter l'ancien script dangereux.
  - [x] Tests pour le script et le calcul du bundle.

## 🔴 Bugs de gravité haute

1. [x] **Kubernetes** : rien ne s'affiche avant 200 lignes (tampon d'historique vidé trop tard). *(code)*
2. [x] **Lignes en double à chaque poll** : Loki (ms vs ns), GCP (filtre `>=` à la seconde), Datadog (borne incluse), Fly.io (point de départ non mis à jour après l'historique). *(code/probable)*
3. [x] **L'historique montre les événements les plus anciens**, pas les plus récents (Datadog, Loki, Elastic, requête Azure par défaut) ; GCP perd des lignes au-delà de 200 entrées par intervalle. *(code)*
4. [x] **Une erreur réseau passagère arrête le tail** définitivement (boîte d'erreur + gel de 3 s). *(code)*
5. [x] **Entrée dans n'importe quel champ texte insère une ligne de séparation** dans le log actif (raccourci « Return » global). *(mesuré)*
6. [x] **10ᵉ panneau en split** : jamais affiché mais son worker tourne en arrière-plan. *(mesuré)*
7. [x] **Fuite des dialogues de connexion** : dialogue + timer 200 ms jamais libérés (+ connexion SSH ouverte). *(mesuré)*
8. [x] **Suivi de fichier** : fichier tronqué/renommé (logrotate) non suivi ; ligne écrite en deux fois coupée ; caractère accentué coupé en `�`. *(code)*

## 🟠 Bugs de gravité moyenne

- [x] 9. Recherche : surlignage rose opaque (`#AARRGGBB` mal lu) ; mal placé sur les lignes à retour à la ligne ; lignes JSON comptées mais jamais surlignées ; AND/OR ignorés ; saut vers le 1ᵉʳ résultat toutes les 300 ms en tail. *(mesuré/code)*
- [x] 10. Clic droit (et fin de sélection à la souris) sur une ligne JSON la déplie/replie. *(mesuré)*
- [x] 11. Ctrl+W ferme tous les onglets sans confirmation.
- [x] 12. `simplelog app.log` lancé depuis un autre dossier avec une instance ouverte : chemin relatif non résolu, rien ne s'ouvre.
- [x] 13. Gels à l'arrêt des workers : fermer un onglet fige l'UI ~3 s, quitter 2 s par worker ; un onglet stdin ne peut pas être arrêté. *(mesuré)*
- [x] 14. Appels réseau dans le fil de l'interface : CloudWatch (log groups, streams à chaque ↓), Docker (`docker ps`), SSH (2ᵉ connexion, navigateur SFTP), restauration des onglets SSH/GCP/Azure.
- [x] 15. Heures affichées en UTC sans l'indiquer → désormais en heure locale.
- [x] 16. Cocher/décocher « timestamps » ne recalcule pas la hauteur des lignes.
- [x] 17. `write_private` non atomique : un crash laisse un JSON tronqué → profils effacés à la sauvegarde suivante.
- [x] 18. Elastic : tri sur `_id` refusé par défaut depuis Elasticsearch 8. *(probable)*
- [x] 19. Mise à jour : pas de contrôle d'intégrité avant `pkexec dpkg -i`, et `pkexec` dans le fil de l'UI.

## 🟡 Bugs de gravité basse

- [ ] 20. Railway : handler rebranché à chaque sélection ; ensemble `_seen` illimité ; tous les logs retéléchargés à chaque poll.
- [ ] 21. Azure : filtre de temps inséré après la 1ʳᵉ ligne (mauvais si requête sur une ligne ou `take`/`limit` avant).
- [ ] 22. CloudWatch : événements arrivés en retard perdus (pas de chevauchement). *(probable)*
- [ ] 23. Cloudflare : description du worker fausse (HTTP/2, wrangler jamais utilisés).
- [ ] 24. ~120 textes visibles en dur (statuts des workers, « Save as profile… », « Profile name: », erreurs) : à passer par `i18n`.

## ⚡ Performances (mesures : 2 000 lignes une par une = 26 s ; 1 ligne à 10 000 lignes = 250 ms ; fichier 300 000 lignes = 18,8 s)

Cause principale : `LogDelegate.sizeHint` (72 % du temps) recalculé pour **toutes** les lignes à chaque ajout.

- [x] P1. Workers de flux (SSH, Docker, K8s, stdin, fichier) : émettre par paquets (~50 ms / 500 lignes) au lieu d'un signal par ligne.
- [x] P2. `LogViewer` : regrouper les ajouts (timer 50–100 ms) et ne défiler qu'une fois par paquet.
- [x] P3. Mettre en cache la hauteur de chaque ligne (invalider si largeur / police / timestamps changent).
- [x] P4. Log plein : supprimer les plus anciennes lignes par tranches de 10 % au lieu de reconstruire tout le modèle à chaque ajout.
- [x] P5. Ne pas réappliquer le filtre s'il n'a pas changé (changement d'onglet, clic dans un panneau).
- [x] P6. Retarder (~100 ms) le recalcul au redimensionnement.
- [x] P7. Option « sans retour à la ligne » (lignes de hauteur fixe).
- [x] P8. Dessin : mettre en cache niveau, heure formatée, couleurs, police des badges (5 regex par ligne à chaque dessin).
- [x] P9. Recherche incrémentale (nouvelles lignes seulement).
- [x] P10. Arrêt immédiat des workers (attente interruptible, plus de `wait()` dans l'UI).
- [x] P11. Borner l'historique (CloudWatch sans limite ; fichier : 500 000 lignes demandées pour 10 000 gardées) et réécrire `_read_last_n_lines` (18,8 s → < 0,2 s).
- [x] P12. Appels réseau des panneaux dans `BackgroundWorker` (cf. bug 14).
- [x] P13. Corriger la fuite des dialogues (cf. bug 7).
- [x] P14. Import paresseux de boto3 / paramiko (~0,2 s au démarrage).

## 🧹 Refactoring

- [ ] R1. Registre unique des fournisseurs (remplace `_REMOTE_PROVIDERS`, `_PROVIDER_ORDER`, `_get_subtitle`, `_SOURCE_COLORS`, les 15 `open_*_tab`, `_configs`).
- [ ] R2. Vraie interface `ProviderPanel` (connecter, connecté ?, ouvrir, lire/charger profil) à la place des ~60 attributs privés lus par `_configs`.
- [ ] R3. Base `PollingWorker` pour les 9 workers de polling (doublons, arrêt, erreurs avec retry, historique borné).
- [ ] R4. Base `StreamWorker` pour les flux (paquets, arrêt propre, stderr lu au fil de l'eau).
- [ ] R5. Supprimer le code mort (~550 lignes) : `AddRemoteDialog`, `_PROVIDER_FIELDS` / `_make_form_fields` / `get_form_data`, code HTTP/2 de `cloudflare_utils.py`, fonctions utilisées seulement par les tests, `_update_*_badge` vides, 3 copies du bloc `_HAS_SVG`.
- [ ] R6. Factoriser la sauvegarde de profil (13 copies) dans `ProviderPanel`, avec i18n.
- [ ] R7. Un seul module d'écriture des fichiers de config (atomique, `0600`).
- [ ] R8. Générer le menu Langue depuis `locales/*.json`.

## Ordre conseillé

1. Urgent macOS + renommage de l'asset, avant toute release.
2. Bugs haute gravité 1–8.
3. Performances P1–P6 et P10.
4. `PollingWorker` / `StreamWorker` (R3, R4).
5. Bugs moyens, puis registre des fournisseurs (R1, R2) et code mort (R5).
