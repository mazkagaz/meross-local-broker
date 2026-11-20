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

- Broker : 74 tests unitaires (`TESTING.md`).
- Intégration : 61 tests unitaires, build Angular vert, release HACS.
