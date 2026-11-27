# Notes de version — 1.6.2

## 1.6.2 — MSL610 : luminosité et couleur fiables

- Profil MSL610 **2026.11.4** : luminosité en `capacity: 4` ; température de
  couleur en `capacity: 6` avec la luminosité courante, sans retomber à 1 %.
- Suppression du polling `GET`/`GETACK` du MSL610 : les timeouts après reload
  disparaissent, l’état vient des `PUSH`.
- Moteur de profils **2.6.0** synchronisé avec l’intégration, jeton
  `$brightness` et chemins de provenance corrigés.
- Nécessite l’intégration **4.0.7** pour le MSL610 ; aucun changement pour
  les autres appareils.
- Tests : **227 passed**, 34 subtests ; lint des profils à 0 erreur.

# Notes de version — 1.6.1

## 1.6.1 — correctif de démarrage Web UI

- La Web UI est de nouveau générée directement dans `/var/www` avec
  `assets/env.js`, au lieu de `/var/www/browser`.
- Corrige l'échec du cont-init, le timeout s6 et le conteneur qui ne démarre
  pas en 1.6.0.
- Garde-fou CI sur la disposition Web UI, plus un smoke test qui démarre
  réellement l'image construite.
- E2E Docker et Supervisor utilisent désormais cette image courante.
- Aucun changement du profil MSL610 ni de l'API broker.

# Notes de version — 1.6.0

## 1.6.0 — Web UI Angular 22

- Web UI migrée d'Angular 11 à **Angular 22.3** et Angular Material 22.
- Material MDC, builder `application`, layouts CSS sans flex-layout, nouvelle
  librairie QR.
- Outillage dev legacy supprimé : Protractor, TSLint/codelyzer, Stylelint,
  HTMLHint, Hads et ngx-rocket.
- `write:env` remplacé par un script local sans dépendance.
- Audit npm à **0 vulnérabilité**.
- 61 specs Karma validées ; profil MSL610 et API broker inchangés.

# Notes de version — 1.5.2

## 1.5.2 — support MSL610

- Profil bundled **`meross.msl610`** : luminosité, température de couleur et
  on/off via `ToggleX`.
- L'intégration **4.0.6** expose la température de couleur en 2700–6500 K.
- Tests golden frames à partir des captures de la télécommande : luminosité,
  chaud/froid/mix, mise en veille et `TriggerX`.
- Catalogue porté à **20 profils**.
- Minuterie `TriggerX` non exposée pour l'instant.
- Aucun changement de schéma ; les installations existantes sont compatibles.

# Notes de version — 1.5.1

## 1.5.1 — datations UTC et dette technique

- Datations unifiées en UTC : stockage naïf dans SQLite, valeurs aware dans
  l'application, sérialisation tuning en ISO 8601 `Z`.
- Correction de l'âge du cache Ability et des caches device de plus de 24 h.
- Zéro warning pytest côté broker, SQLAlchemy passé en 1.4.54, CLI Supervisor
  `apps`, métadonnées Docker nettoyées.
- Web UI validée sous **Node 22** : build Angular et 61 specs Karma.
- Tests : **221 passed, 1 skipped**, 33 subtests, rejoués sous `Europe/Paris`
  et `America/New_York`.
- Aucun changement de schéma ; les anciennes valeurs de cache peuvent refléter
  l'ancien fuseau et se rafraîchissent naturellement.
- Intégration **4.0.4+** et pairer inchangés.

# Notes de version — 1.5.0

## 1.5.0 — broker autonome pour Home Assistant Container

- Nouveau mode **autonome** (Docker sans Supervisor), détecté par l'absence de
  `SUPERVISOR_TOKEN` ou forcé avec `MEROSS_STANDALONE=1`.
- Admin liée par défaut à `127.0.0.1:2003` (`ADMIN_BIND`, `ADMIN_PORT`,
  `ADMIN_ALLOW_CIDR`), sans authentification propre : tunnel SSH ou reverse
  proxy recommandé.
- Certificat TLS : SAN supplémentaires via `TLS_SAN_EXTRA` et détection des
  IPv4 de l'hôte avec `TLS_SAN_AUTO` ; ports MQTT 2001 et HTTPS 2004.
- Bundle `deploy/` : compose en réseau hôte, `.env.example`, `install.sh` qui
  prépare les données, démarre le broker et affiche les valeurs à saisir.
- Intégration **4.0.4+** : les ports 2004/2001 sont préremplis dans le formulaire manuel.
- Tests : helpers de mode autonome et priorité des options ; **209 tests**
  (1 ignoré), lint et parité moteur inchangés.
- Parcours add-on (HA OS/Supervised) inchangé ; l'add-on reste recommandé.

# Notes de version — 1.4.8

## 1.4.8 — présence et réglages du volet

- Profil MRS100 `2026.11.4` : entité **Position** en curseur (0–100 %) et
  durées d’ouverture/fermeture en champ de saisie avec unité `s` et flèches,
  bornées à 10–120 secondes.
- Le champ de profil `mode: slider|box` choisit la présentation par entité ;
  le moteur passe en **2.5.1**. Installer l’intégration **3.2.2** pour en
  profiter ; les versions antérieures gardent le curseur.
- CI : pin de l’intégration 3.2.2 et provenance moteur régénérée.
- Aucun changement d’API ; pairer 2.0.9 inchangé.

# Notes de version — 1.4.7

## 1.4.7 — correctif CI et provenance du moteur

- Aucun changement fonctionnel par rapport à 1.4.6.
- Le workflow de test épingle désormais l’intégration **3.2.1** (`22e489b`) ;
  `profile_engine/UPSTREAM.md` est régénéré avec le commit et les hashes du
  moteur 2.5. La vérification de parité moteur repasse au vert.
- L’image est reconstruite pour publier un tag dont la CI est verte.

# Notes de version — 1.4.6

## 1.4.6 — icônes de volet et profil MRS100 2026.11.3

- Le profil MRS100 déclare un état auxiliaire `movement` alimenté par
  `Appliance.RollerShutter.State` : flèche haut à l’ouverture, flèche bas à la
  fermeture, puis icône volet ouvert (`position = 100`), fermé (`0`) ou partiel
  à l’arrêt. Aucune entité supplémentaire n’est créée.
- Les PUSH `State` réels (`state`, `timestamp`, `stoppedBy`) sont documentés
  dans le profil ; le moteur partagé passe en **2.5** et accepte `movement`
  sur une entité. Les moteurs antérieurs ignorent ce champ.
- Cette version sert un nouveau profil, donc l’intégration **3.2.0+** (3.2.1
  conseillée) détecte la mise à jour, affiche une notification persistante et
  propose l’installation manuelle depuis l’entité `update`.
- Aucun changement d’API ; pairer 2.0.9 inchangé.

# Notes de version — 1.4.5

## 1.4.5 — capture des trames réparée

- La capture était pilotée par le processus API tandis que les trames étaient
  observées par l’agent : chaque processus avait son propre état, d’où une
  session « active » mais toujours **0 frame**. La session est maintenant
  décrite sur disque (`/data/capture/current.json`) et l’agent l’enregistre
  lui-même ; l’API calcule le statut depuis les mêmes fichiers.
- Seules les trames de l’appareil capturé sont conservées, y compris les PUSH
  déclenchés à l’interrupteur ; les limites de durée et de taille sont
  appliquées côté agent.
- Nouveau bouton **Download ZIP** (et `GET /_admin_/tuning/capture/export`) :
  archive avec `session.json`, `frames.jsonl` et le brouillon, déjà assainis,
  pour partager une capture avec la communauté.
- Aucun changement de profil ni de rupture d’API.

# Notes de version — 1.4.4

## 1.4.4 — récupération automatique de l’ability

- Les appareils publient leurs réponses sur le topic `header.from`. La demande
  d’ability de l’agent repart donc sur `/_agent`, où l’agent est abonné, et le
  GETACK y est maintenant traité et stocké. Les profils se remplissent seuls
  dès qu’un appareil est en ligne, sans clic.
- Le chemin « topic de publication » reste supporté via un helper commun ;
  les documents vides et les réponses sans origine appareil sont ignorés.
- Le reste de 1.4.3 est inchangé : refresh manuel de secours, polling du
  tuning, colonne Profile sur l’accueil.

# Notes de version — 1.4.3

## 1.4.3 — profils détectés automatiquement et visibles sur l’accueil

- L’ability est maintenant récupérée automatiquement dès qu’un appareil est en
  ligne : plus de cooldown consommé hors ligne, réinitialisation à la
  déconnexion et requête avec une origine app.
- Le tuning se rafraîchit seul (listes toutes les 20 s) et recharge la fiche
  sélectionnée dès que son profil apparaît ; le bouton Refresh ability reste
  disponible en secours.
- Le panneau principal affiche, en mode avancé, une colonne **Profile** avec la
  version appliquée et un badge **Custom** lorsque le profil vient de
  `/data/device_profiles`.
- Matching partagé entre l’admin et le tuning ; profils et API inchangés.

# Notes de version — 1.4.2

## 1.4.2 — rafraîchir l’ability depuis le tuning

- Nouveau bouton **Refresh ability** dans la fiche appareil du tuning (et
  `POST /_admin_/tuning/devices/{uuid}/ability`) : le broker demande
  `Appliance.System.Ability` avec une identité app, comme l’intégration, puis
  enregistre le document. Les profils sont associés immédiatement.
- L’agent demande à nouveau l’ability si le document en cache est vide,
  incomplet ou corrompu, et n’enregistre plus un document vide.
- Aucun changement de profil ni de rupture d’API.

# Notes de version — 1.4.1

## 1.4.1 — matching des profils et confort du tuning

- L’agent demande `Appliance.System.Ability` aux appareils quand le document
  manque ou date de plus de 24 h (cooldown 5 min). Les profils qui déclarent
  des capacités (MRS100, etc.) sont maintenant associés dans le tuning, donc
  les commandes typées sont disponibles.
- Tuning : à défaut de profil associé, un message explicatif remplace le
  snackbar ; la révision et les hashes sont tronqués avec tooltip et copie.
- Tuning : la liste des profils affiche les profils détectés par défaut, avec
  recherche et option « Show all » persistée.
- Compatibilité et profils inchangés ; aucune rupture d’API.

# Notes de version — 1.4.0

## 1.4.0 — page de tuning et commandes typées

- Page **Device tuning** dans le panneau du broker, réservée à l’ingress
  Supervisor : éditeur YAML (CodeMirror 6 épinglé), validation continue avec
  diff, application de surcharges avec backup et rollback, import/export
  YAML/ZIP et audit.
- Onglet Appareils : descripteur, entités attendues, plan de polling, cache
  volet, simulation de trames, GET live en lecture seule et capture avec
  brouillon injecté dans l’éditeur.
- Commandes typées : catalogue dérivé du profil, payload généré (jamais saisi
  en brut), confirmation à usage unique, une commande à la fois, cooldown et
  audit avec snapshots avant/après.
- Moteur de profils partagé avec l’intégration, copie épinglée et contrôle de
  parité en CI.
- Compatibilité : aucune rupture d’API, catalogue inchangé (19 profils) ;
  intégration 3.1.0 minimum, pairer 2.0.9 minimum. La mise à jour redémarre le
  conteneur : les appareils se reconnectent automatiquement.

# Notes de version — 1.3.1

## 1.3.1 — maintien d’état du volet

- Profil MRS100 `2026.11.2` : plus de GET sur
  `Appliance.RollerShutter.Adjust` (SET-only). Le statut de calibration est
  reçu via SETACK/PUSH.
- L’intégration 3.1.1 amorce position et statut depuis le cache P3 : pas de
  retour à « inconnu » après un reload ou un redémarrage de Home Assistant.
- Compatibilité : intégration 3.1.0 minimum, **3.1.1 recommandée** ; pairer
  2.0.9 inchangé. Aucun changement d’API.

# Notes de version — 1.3.0

## 1.3.0 — catalogue D2b complet

- 19 profils : multiprises MSS425/MSP844, capteurs MS200/MS400/MS600, GS559,
  garages MSG/RSG, purificateur MAP100, sprinkler MST100, compteurs EM/EM06,
  diffuseur MSXH0, HP110, MTS9 ; MTS200/MTS300 séparés (échelle corrigée).
- Entités par canal découvert (`channel: $channels`), sélection d’état par clé
  (`state.select`, liste ou objet), mapping booléen `on_values`, routage des
  sous-appareils par `id` ou `subId`, quirk `garage_door`.
- Les profils MSH300 et garage exigent le moteur 2.4 : installer
  **l’intégration 3.1.0 ou plus récente avant ce broker**, sinon le hub et le
  garage ne sont pas appariés.
- Aucun changement d’API ; routage ACK et compatibilité pairer 2.0.9 inchangés.
- Testeurs recherchés pour toutes les familles hors MRS100 (modèle, firmware,
  fonctions observées).

# Notes de version — 1.2.2

## 1.2.2 — routage ACK

- Les ACK (`GETACK`, `SETACK`, `ERROR`) sont livrés uniquement sur le topic
  applicatif demandeur (`/app/<userId>-<appId>/subscribe`).
- Les PUSH restent sur `/app/<userId>/subscribe`.
- Repli sur le topic utilisateur uniquement si le topic demandeur est absent
  ou invalide.
- Suppression de l’option `legacy_user_topic_acks` et de la double publication.
- Aucun changement d’API ; l’intégration 3.0 et le pairer 2.0.9 restent
  compatibles.

# Notes de version — 1.2.1

## 1.2.1 — volets MRS100

- Profils MRS100 et `mrs` alignés sur les trames réelles : listes
  `position`/`state`/`config`/`adjust`, commandes Position/Config/Adjust sous
  la clé du namespace.
- Ouvrir, fermer, stop et position utilisent désormais
  `Appliance.RollerShutter.Position`.
- Durées et calibration relisent les bons chemins ; arrêt de calibration
  avec `value=2`.
- Aucun changement d’API. Intégration 3.0 : rechargement automatique à la
  nouvelle révision du catalogue.

# Notes de version — 1.2.0

## 1.2.0 — socle profils et outillage

- Catalogue de profils servi par le broker, signé Ed25519, avec révision,
  surcharges `/data/device_profiles`, rechargement à chaud et diff.
- Mode capture avec assainissement, brouillon de profil et limites.
- Endpoint de configuration volet pour le cache côté intégration.
- Contrats API versionnés et tests ; broker sans dépendance `meross_iot`.
- Branche `dev` et workflows de test pour préparer les prochaines étapes.

Le reste du document décrit les évolutions depuis le fork (1.0.0).

# Notes de version — 1.0.0

Ce document récapitule les évolutions du fork depuis son premier commit
(alpha54) et sert de notes pour la version stable. Les détails successifs
restent dans [CHANGELOG.md](meross_local_broker/CHANGELOG.md).

## Le montage

| Brique                  | Rôle                                         | Version |
| ----------------------- | -------------------------------------------- | ------- |
| **Meross Local Broker** | add-on : MQTT/TLS, API HTTPS, panneau web    | 1.0.0   |
| **Meross Local Cloud**  | intégration Home Assistant (HACS)            | 2.3.2   |
| **Meross Local Pairer** | appairage Android (Wi-Fi AP et Bluetooth LE) | 2.0.8   |

## Évolutions depuis le fork

### MRS100 et volets roulants

- Découverte du canal volet (digest, ability ou type d'appareil).
- Persistance et réapplication des durées d'ouverture/fermeture, comme le cloud.
- Cache des positions, états et résultats de calibration.
- Entités : cover, deux durées (10–120 s), boutons de calibration et statut.

### TLS et certificat

- CA locale valide (`CA:TRUE`), passphrase aléatoire persistée.
- Certificat serveur avec les IP LAN dans ses SAN, re-signé quand elles changent.
- HTTPS obligatoire pour l'intégration et le pairer ; CA épinglée par
  l'intégration ; options « ignorer la validation » supprimées.
- Régénération automatique des CA legacy ou proches de l'expiration, avec
  sauvegarde.

### Sécurité

- Comptes locaux en Argon2id, migration des anciens hachages.
- Sessions hachées, expirantes (inactivité et durée absolue), limitation des
  tentatives de connexion.
- ACL MQTT dynamiques : chaque appareil limité à ses topics, chaque compte
  applicatif à ses propres appareils.
- Contrôle d'intégrité des publications (signature, fraîcheur, anti-rejeu) en
  mode `observe` par défaut, `enforce` disponible.
- API d'administration limitée à l'ingress du Supervisor ; CORS restreint.
- Aucun port de débogage publié.

### Protocole et compatibilité

- Accusés de réception acceptés sur les topics applicatifs du broker.
- `devList` : `bindTime` entier, ability et métadonnées volet.
- Horodatages de signature numériques acceptés (pairer, `meross_iot`).
- Retry de la connexion TLS de l'agent sans sonde TCP brut.
- mDNS : seuls le broker MQTT et l'API HTTPS sont annoncés.

### Cycle de vie des appareils

- Oubli avec révocation du MAC jusqu'au réappairage ; UUID conservé.
- Publication `Appliance.Control.Unbind` vers Home Assistant (au plus tard
  60 s, ou à la reconnexion de l'agent).
- Déconnexion d'un appareil déjà oublié traitée proprement.
- Intégration : suppression immédiate sur Unbind, réconciliation du registre et
  réparation après 48 h d'absence.

### Timezone et mesure

- `device_timezone` pousse le fuseau et les règles d'heure d'été aux appareils.
- Rafraîchissement périodique des appareils dont les informations sont
  périmées après un redémarrage.

### Interface web

- Thème Home Assistant, diodes d'état par service.
- Liste des appareils, renommage, oubli.
- Page **Journaux** pleine page : onglets par service, recherche avec
  surlignage, filtre de niveau, copie, téléchargement, pause et retour à la
  ligne.

### Fiabilité et CI

- nginx attend l'API avant de démarrer.
- Interface servie sans cache (mises à jour visibles immédiatement).
- Images amd64/aarch64 uniquement, Web UI construite avant l'image, workflows
  builder maintenus.

## Changements cassants et migration

- **HTTPS obligatoire côté LAN** : le port 2003 est réservé à l'ingress Home
  Assistant ; utilisez `https://…:2004`. L'intégration doit être en 2.x et le
  pairer en 2.0.8 ou plus récent.
- **CA valide** : après mise à jour, réinitialisez le certificat épinglé dans
  le pairer si nécessaire ; l'intégration récupère la nouvelle CA seule.
- **Options supprimées** : `enable_https` (HTTPS toujours actif),
  `auto_regenerate_legacy_ca` (régénération automatique). La page Configuration
  ne les affiche plus.
- **Débogage** : `debug_mode` active uniquement les journaux détaillés ; debugpy
  et le mode debug Flask ont été retirés.
- **Intégrité MQTT** : `off` n'est plus accepté ; seuls `observe` et `enforce`
  existent.

## Mise à jour recommandée

1. Mettre à jour l'add-on (dernière version).
2. Mettre à jour l'intégration via HACS (2.3.2+), puis redémarrer Home
   Assistant.
3. Mettre à jour le pairer (2.0.8+).
4. Vérifier le compte local, l'API HTTPS 2004 et le port MQTT 2001.
5. Après un oubli, contrôler que les entités disparaissent dans la minute.

## Limites connues

- MRS100 principalement testé ; les autres modèles sont testés par la
  communauté.
- Volets multi-canaux non couverts (canal 0).
- `mqtt_integrity_mode` doit rester en `observe` tant que des écarts
  apparaissent dans les journaux.

## Vérifications

- Broker : 74 tests unitaires (`docs/testing/TESTING.md`).
- Intégration : 61 tests unitaires, build Angular vert, release HACS.
