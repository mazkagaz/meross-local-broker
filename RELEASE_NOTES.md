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
