# Guide avancé D4 — profils, capture et rechargement

Public : utilisateurs avancés qui veulent ajouter ou corriger un modèle sans
reconstruire l’add-on. Le parcours de base (installation, appairage,
intégration) ne change pas.

## Prérequis

- Home Assistant OS ou Supervised : l’add-on a besoin du Supervisor.
  HA Container et HA Core ne peuvent pas héberger l’add-on ; l’intégration et
  le pairer supposent un broker joignable en HTTPS 2004 et MQTT 2001.
- Broker ≥ 1.1.3, intégration ≥ 2.4.6, pairer ≥ 2.0.8.

## Activer le mode avancé

Dans **Paramètres → Appareils et services → Meross Local Cloud → Configurer** :

- `profile_backend` : charge le catalogue côté intégration, expose les
  diagnostics (révision, signature, correspondances).
- `profile_entities` : crée les entités issues des profils (switch, light,
  sensor, binary_sensor, cover, number, button, update). Elles coexistent
  avec les entités historiques et portent des identifiants distincts jusqu’à
  D5 : attendez-vous à des doublons fonctionnels pendant la transition.

## Catalogue et surcharges

- Catalogue livré : `device_profiles/` dans l’add-on.
- Surcharges : `/data/device_profiles/*.yaml` (même dossier `/data` que la
  base et les certificats). Un fichier avec le même `id` remplace le profil
  livré ; un nouvel `id` l’ajoute.
- Un fichier invalide est signalé et ignoré ; le profil livré reste actif.

### Boucle de travail

1. Copier un profil livré comme base.
2. Ajuster `profile`, `match`, `payloads`, `entities` (voir
   [PROFILE-AUTHORING.md]../specs/PROFILE-AUTHORING.md et
   [device-profiles.schema.json](../device-profiles.schema.json)).
3. Déposer le fichier dans `/data/device_profiles`.
4. Le broker détecte le changement à la prochaine lecture du catalogue
   (révision recalculée) ; l’intégration vérifie la révision toutes les 60 s
   et recharge son entrée automatiquement.
5. Pour forcer immédiatement : `POST /_admin_/profiles/reload` (ingress
   Supervisor) renvoie `added`, `removed`, `changed`, `revision`, `errors`.

Aucun redémarrage de Home Assistant n’est nécessaire.

## Catalogue signé

- Le broker signe le catalogue en Ed25519 ; la clé privée reste dans
  `/data/profile_signing.key` (0600), la clé publique est exposée par
  `/v1/Device/profiles/pubkey`.
- L’intégration vérifie la signature. Un catalogue signé invalide est refusé
  et le backend passe en erreur ; un catalogue non signé (broker ancien) est
  accepté et signalé.
- Diagnostics : `catalog_signature` (`valid`/`invalid`/`absent`),
  `catalog_key_fingerprint`, `catalog_revision`, `profiles_overridden`.

## Capture et brouillon

API d’administration, accessible uniquement via l’ingress Supervisor :

- `POST /_admin_/capture/start` : `{"uuid": "...", "type": "mrs100", "duration_s": 300, "max_bytes": 2000000}`.
- `GET /_admin_/capture/status`, `POST /_admin_/capture/stop`.
- `POST /_admin_/capture/draft` : `{"type": "mrs100"}` génère
  `/data/capture/<session>/draft.yaml`.

Les sessions sont limitées (durée, taille, nombre de trames), écrites en
0600 dans `/data/capture` (0700). Les secrets sont retirés et les
identifiants pseudonymisés ; `sign` et `messageId` ne sont jamais conservés.
Le brouillon agrège les namespaces, méthodes et formes de champs observés :
il faut ensuite écrire les entités, puis déposer le profil dans
`/data/device_profiles`.

## Entités update

Avec `profile_entities`, chaque appareil et sous-appareil expose une entité
`update` : titre du profil, version installée/dernière, description, et une
action « installer » qui recharge l’entrée pour réappliquer le catalogue.

## Validation D5 — backend profils obligatoire

L’intégration 3.0 est profile-only : il n’existe plus d’options ni de repli
historique.

1. Installer la pré-release `3.0.0-beta.1`, recharger l’entrée.
2. Dans les diagnostics, vérifier `connected`, la signature valide,
   `devices_matched`, `devices_unmatched` et l’absence d’erreurs de compilation.
3. Vérifier chaque appareil couvert : volet (ouvrir/fermer/position/stop,
   durées, calibration), prises et éclairages, thermostat, ventilateur,
   capteurs et sous-appareils.
4. Vérifier les cas dégradés : appareil hors ligne, redémarrage broker,
   redémarrage HA, reload, appareil sans profil et Unbind.
5. Les identifiants historiques sont conservés : automatisations et tableaux
   de bord restent valides.
6. En cas de problème bloquant, réinstaller la stable 2.4.6 dans HACS.

Checklist détaillée : `docs/testing/D5-VALIDATION.md` du dépôt intégration.

## Dépannage

| Symptôme                     | Vérifier                                                        |
| ---------------------------- | --------------------------------------------------------------- |
| Profil ignoré                | `errors` dans `/profiles/reload`, schéma, chemins               |
| Surcharge sans effet         | `id` identique, fichier `.yaml`, révision changée               |
| `catalog_signature: invalid` | clé `/data/profile_signing.key` altérée ou catalogue modifié    |
| Entités absentes             | `profile_entities` actif, appareil apparié, backend `connected` |
| Doublons d’entités           | attendu tant que les entités historiques existent (D5)          |
