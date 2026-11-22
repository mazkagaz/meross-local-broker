# Page de tuning des appareils — plan V1 → V2

**Statut** : étapes 0 à 5 faites ; documentation faite, validation terrain en
attente.
**Objectif** : une page de l’UI broker (ingress uniquement) pour exporter,
importer, modifier et tester les profils et les réglages d’instance des
appareils. Livrer une V1 sûre, avec une architecture qui accepte la V2 sans
refonte.

## Décisions structurantes

- Page dans l’UI web du broker, accessible uniquement via l’ingress Supervisor.
- Deux périmètres visuellement séparés : **Profil** (type, partagé par tous les
  appareils qui matchent) et **Instance** (un appareil).
- **Moteur de profils partagé** entre l’intégration et le broker : code
  canonique épinglé et contrôle CI de parité.
- **Éditeur YAML** (CodeMirror 6 épinglé) ; parsing, validation et diff côté
  broker.
- V1 : lecture, simulation, GET, export/import et application des profils.
- V2 : SET typés et écritures d’instance.
- Hors périmètre : profils par appareil, publish MQTT brut, édition du
  catalogue livré, accès aux clés de signature.

## Étape 0 — Moteur partagé

0.1 Inventorier les modules purs de l’intégration (`paths`, `compiler`,
`runtime`, `match`, modèles).
0.2 Extraire un paquet canonique sans dépendance Home Assistant.
0.3 L’intégrer dans l’intégration puis dans le broker (copie vendorisée générée
ou sous-module épinglé).
0.4 Ajouter un contrôle CI de parité : mêmes profils, mêmes entités compilées,
mêmes résultats de simulation.
0.5 Tester tous les profils du catalogue : compilation et simulation
identiques dans les deux artefacts.

**Sortie** : un seul comportement de compilation entre HA et l’aperçu broker.

**État (2026-11-21)** : fait. Le broker embarque
`profile_engine/` (copie octet pour octet de l’intégration), le script
`tools/sync_profile_engine.py` et la provenance
`profile_engine/UPSTREAM.md`. La CI broker épingle l’intégration
`475c5d14065e3c792d426822d9ea13250c7cc967` et vérifie la parité avant les
tests. Les tests couvrent la compilation de tout le catalogue et des trames
MRS100 de référence.

## Étape 1 — Socle backend V1

1.1 Stockage des surcharges : écriture atomique, backup horodaté, révision +
hash, verrou optimiste.
1.2 Inventaire : profils livrés/surcharges, appareils associés, nombre
d’appareils impactés.
1.3 Validation : schéma, linter, YAML sécurisé (`safe_load`), limites de
taille/profondeur, erreurs avec ligne et colonne.
1.4 Diff serveur (unifié) entre livré, surcharge et brouillon.
1.5 Export YAML/ZIP avec manifeste ; import avec dry-run, détection de
doublons, protection Zip Slip et limites.
1.6 Application/rollback : backup, écriture, rechargement du catalogue,
propagation de révision.
1.7 Audit : utilisateur HA, date, hash avant/après, action.
1.8 Endpoints admin et contrats API.

**Tests** : YAML valide/invalide, conflit de révision, limites, import
malveillant, écriture partielle, rollback, permissions, rechargement.

**État (2026-11-21)** : fait. Le store (`tuning.py`) et le blueprint
(`blueprints/tuning.py`) sont enregistrés sous `/_admin_/`. Écritures atomiques
(temp + fsync + replace), backup horodaté avant chaque mutation (20 par
profil), verrou optimiste par hash, rechargement du catalogue et propagation de
révision, audit JSONL (acteur HA, date, hash avant/après), export YAML/ZIP avec
manifeste et import dry-run avec limites. La validation réutilise le schéma,
le linter et le moteur partagé, et renvoie un diff unifié contre la base
effective (`bundled`, `override` ou `none`). Tests : `test_tuning.py` (10),
`test_tuning_api.py` (5), suite broker complète verte.

## Étape 2 — Aperçu et test V1

2.1 Endpoint état d’un appareil : descripteur, profil/source/hash, valeurs
runtime, cache P3, timestamps, état en ligne.
2.2 Matching réel avec le moteur partagé, entités attendues, plan de polling,
erreurs isolées.
2.3 Simulation de trames `PUSH`/`GETACK` : valeurs extraites, champs ignorés,
erreurs.
2.4 GET live en lecture seule : namespace autorisé par le profil, rate-limit,
timeout, aucune mutation.
2.5 Intégration capture : démarrer/arrêter, brouillon injecté dans l’éditeur.

**Tests** : appareil absent/hors ligne, payload malformé, namespace inconnu,
canal absent, timeout, réponse vide.

**État (2026-11-22)** : fait côté backend. `GET /_admin_/tuning/devices/{uuid}`
expose le descripteur, le profil/source/hash, les entités attendues (canaux
`$channels` dépliés), les modèles de sous-appareils, le plan de polling, la
capacité et le cache volet (`status`/`config`/`adjust`). `POST /_admin_/profiles/{id}/preview` rejoue une trame `GETACK`/`SETACK`/`PUSH` dans
le moteur partagé sans toucher l’appareil et renvoie les valeurs extraites, les
canaux et sous-appareils. `POST /_admin_/tuning/devices/{uuid}/read` effectue un
GET signé en lecture seule via un client MQTT éphémère (identité app dérivée du
propriétaire), limité aux namespaces déclarés par le profil (plus
`Appliance.System.All`), avec cooldown par appareil, timeout borné et
`503`/`504` explicites. Les réponses sont assainies comme les captures.
Capture : start/stop/status/draft sous `/_admin_/tuning/capture`, le brouillon
étant renvoyé en YAML pour l’éditeur. Tests : `test_tuning.py`,
`test_tuning_api.py`, `test_tuning_probe.py`. Limite assumée : le broker ne
conserve pas d’état générique par namespace ; les valeurs d’instance exposées
sont `last_seen`, la capacité et le cache volet. Un cache générique pourra
suivre en V2.

## Étape 3 — UI V1

3.1 Module Angular `tuning`, route et entrée de navigation.
3.2 Liste appareils/profils avec source, révision, état et impact.
3.3 Onglet Profil : aperçu, éditeur YAML, validation continue, panneau de diff.
3.4 Import/export avec confirmation, backup et rollback visibles.
3.5 Onglet Instance en lecture seule : descripteur, valeurs, profil, capture.
3.6 Panneau simulation de trames et GET.
3.7 Tests composants et e2e : import → diff → apply → reload → rollback.

**Sortie V1** : comprendre, corriger, exporter, importer et appliquer un profil
sans manipuler les fichiers à la main dans `/data/device_profiles`.

**État (2026-11-22)** : fait. Module Angular `tuning` (route `/tuning`, icône
dans l'en-tête), onglets Profils / Appareils / Audit, éditeur CodeMirror 6
épinglé, validation continue avec diff, apply/revert/backups, import dry-run
puis confirmation, export YAML/ZIP, état d'instance, simulation, GET live,
commandes V2, capture et audit. Le brouillon de capture est injecté dans
l'éditeur. Tests : 51 specs Karma (service, éditeur, composant), build de
production vert.

## Étape 4 — Backend V2

4.1 Catalogue des commandes autorisées par profil (schéma typé : valeur,
canaux, contraintes).
4.2 GET live typé et rafraîchissement d’état.
4.3 SET typé : confirmation à usage unique, appareil en ligne, payload généré
par le profil, une commande à la fois, rate-limit.
4.4 Audit et snapshot avant/après pour les actions d’instance.
4.5 Écritures d’instance : durées, calibration et commandes déclarées, sans
modifier le YAML.
4.6 Tests dégradés : hors ligne, timeout, refus broker, jeton expiré, double
clic, réponse inattendue.

**État (2026-11-22)** : fait. `GET /_admin_/tuning/devices/{uuid}/commands`
dérive un catalogue typé des commandes déclarées (`id entité.commande`, type
`number`/`action`, canaux, min/max/step, `value_scale`). `POST .../commands/{id}` génère le payload par substitution `$channel`/`$value`
(jamais de payload brut), exige une confirmation à usage unique (jeton 60 s
lié à l'appareil et à la commande), refuse hors ligne, double clic et commande
concurrente, applique un cooldown et audite avec snapshots avant/après. Le GET
live renvoie aussi les valeurs typées extraites par le moteur. Les écritures
d'instance (durées, calibration, position) passent par ces commandes sans
modifier le YAML. Limite : les commandes des modèles de sous-appareils ne sont
pas exposées, faute de jeton `$subId` dans le moteur ; les modèles restent
visibles en lecture seule.

## Étape 5 — UI V2

5.1 Actions dans l’onglet Instance, générées depuis le profil.
5.2 Dialogue de confirmation avec impact et payload résumé.
5.3 Résultat et état rafraîchi ; audit accessible.
5.4 Tests e2e : action autorisée, action refusée, hors ligne, annulation.

**État (2026-11-22)** : fait. L'onglet Appareils liste les commandes typées avec
canal et valeur contraints, affiche le payload généré dans la confirmation,
désactive l'action pendant l'envoi et rafraîchit l'état et l'audit après
l'ACK. Les scénarios dégradés sont couverts par les tests composant et API ;
les e2e Protractor ne sont pas exécutés dans l'environnement de développement.

## Étape 6 — Documentation et livraison

- Guide utilisateur : overrides, capture, tests, rollback.
- Contrats API et ADR du moteur partagé.
- Notes de version broker.
- Validation terrain : modifier un profil, l’appliquer sur un appareil réel,
  puis revenir au profil livré.

**État (2026-11-22)** : documentation faite (guide
`docs/guides/DEVICE-TUNING.md`, ADR du moteur partagé, contrats ci-dessous,
notes de version). La validation terrain reste à faire avec un appareil réel :
appliquer un override, vérifier le comportement, revenir au profil livré, puis
tester une commande V2 confirmée.

## API cible

| Méthode | Route                                               | V1  | Rôle                            |
| ------- | --------------------------------------------------- | --- | ------------------------------- |
| GET     | `/_admin_/tuning/devices`                           | oui | appareils + profil/source/état  |
| GET     | `/_admin_/tuning/devices/{uuid}`                    | oui | descripteur, entités, cache     |
| GET     | `/_admin_/profiles`                                 | oui | inventaire effectif             |
| GET     | `/_admin_/profiles/{id}`                            | oui | profil effectif + hashes + diff |
| POST    | `/_admin_/profiles/validate`                        | oui | validation + diff               |
| POST    | `/_admin_/profiles/{id}/preview`                    | oui | simulation de trames            |
| PUT     | `/_admin_/profiles/{id}/override`                   | oui | appliquer (révision attendue)   |
| DELETE  | `/_admin_/profiles/{id}/override`                   | oui | revenir au livré                |
| GET     | `/_admin_/profiles/export`                          | oui | YAML/ZIP                        |
| POST    | `/_admin_/profiles/import`                          | oui | dry-run puis apply              |
| GET     | `/_admin_/profiles/{id}/backups`                    | oui | backups horodatés               |
| POST    | `/_admin_/profiles/{id}/backups/{file}/restore`     | oui | restaurer un backup             |
| GET     | `/_admin_/tuning/audit`                             | oui | journal d’audit                 |
| POST    | `/_admin_/tuning/devices/{uuid}/read`               | oui | GET live                        |
| GET     | `/_admin_/tuning/capture/status`                    | oui | session de capture              |
| POST    | `/_admin_/tuning/capture/start`                     | oui | démarrer une capture            |
| POST    | `/_admin_/tuning/capture/stop`                      | oui | arrêter la capture              |
| POST    | `/_admin_/tuning/capture/draft`                     | oui | brouillon YAML                  |
| GET     | `/_admin_/tuning/devices/{uuid}/commands`           | oui | commandes autorisées (V2)       |
| POST    | `/_admin_/tuning/devices/{uuid}/commands/{command}` | oui | SET typé confirmé (V2)          |

## Contrats backend (étapes 1-2)

Accès : ingress admin uniquement. L’acteur vient des en-têtes
`X-Remote-User-Display-Name`, `X-Remote-User-Name`, `X-Remote-User-Id`
(défaut `unknown`).

- **Validation** `POST /_admin_/profiles/validate`
  corps `{yaml, profile_id?, expected_hash?}` →
  `{valid, profile_id, errors[], warnings[], summary, diff, diff_base}`.
  `diff` est un diff unifié base effective → proposition ; `diff_base` vaut
  `bundled`, `override` ou `none`. Les erreurs YAML portent ligne et colonne.
  `400` si `yaml` n’est pas une chaîne.
- **Profil** `GET /_admin_/profiles/{id}` → métadonnées, `yaml` effectif,
  `bundled_yaml`, `override_yaml`, hashes, `revision`, `diff`
  livré → surcharge, impact et backups. `404` si inconnu.
- **Écriture** `PUT /_admin_/profiles/{id}/override` corps
  `{yaml, expected_hash?}` → `{id, revision, override_hash, diff, warnings}`.
  `400` invalide, `409` hash attendu différent. Une surcharge crée un profil ;
  le livré n’est jamais modifié.
- **Suppression** `DELETE /_admin_/profiles/{id}/override` corps
  `{expected_hash?}` → `{id, revision, removed}`. `404` sans surcharge,
  `409` conflit.
- **Export** `GET /_admin_/profiles/export?format=yaml|zip&source=overrides|effective&id=...`.
  YAML : profil unique (`id` requis). ZIP : toutes les surcharges ou tous les
  profils effectifs, avec `manifest.json` (révision, source, horodatage,
  hashes). `400` source inconnue, `404` surcharge absente.
- **Import** `POST /_admin_/profiles/import?dry_run=true|false` JSON
  `{profiles: [{id, yaml}]}` ou multipart `file` (`.yaml`/`.zip`) →
  `{dry_run, revision, profiles[]}`. Tout est validé avant écriture ; doublons
  d’id refusés. Limites : 2 Mo, 200 entrées, 256 Ko et 5000 lignes par profil,
  profondeur 32. `400` contenu invalide.
- **Backups** `GET /_admin_/profiles/{id}/backups` →
  `[{file, created_at, hash}]` ; `POST .../{file}/restore` →
  `{id, revision, restored}`. `404` backup inconnu, `409` backup qui ne valide
  plus.
- **Audit** `GET /_admin_/tuning/audit?limit=1..500&profile_id=...` → entrées
  récentes d’abord.
- **État appareil** `GET /_admin_/tuning/devices/{uuid}` → descripteur (sans
  secret), profil/source/hash, entités attendues, modèles de sous-appareils,
  plan de polling, capacité et cache volet. `404` si inconnu.
- **Aperçu** `POST /_admin_/profiles/{id}/preview` corps
  `{namespace, method, payload}` ou `{frame: {header, payload}}`, avec
  `channels` et `subdevice` optionnels → valeurs extraites, compteurs
  `applied`/`ignored`, `known_namespace`, erreurs et avertissements. Les canaux
  sont déduits de la trame si `channels` est absent. `400` méthode non
  porteuse d’état ou trame invalide, `404` profil inconnu.
- **GET live** `POST /_admin_/tuning/devices/{uuid}/read` corps
  `{namespace?, payload?, timeout_ms?}` → `{ok, method, header, payload, elapsed_ms, received_at, profile_id}`. Namespace limité au profil (plus
  `Appliance.System.All`) ; `404` appareil inconnu, `409` hors ligne/sans
  propriétaire/aucun profil, `429` cooldown par appareil (`Retry-After`),
  `504` timeout, `503` MQTT local indisponible. GET signé uniquement, jamais
  SET ; réponse assainie.
- **Capture** `GET /_admin_/tuning/capture/status`, `POST .../start`
  `{uuid, type?, duration_s?, max_bytes?}`, `POST .../stop`, `POST .../draft`
  `{type}` → brouillon YAML pour l’éditeur. Une seule session active.
- **Commandes (V2)** `GET /_admin_/tuning/devices/{uuid}/commands` →
  catalogue typé (canaux, bornes, pas, `value_scale`) dérivé des commandes
  déclarées. `POST .../commands/{id}` sans `confirm` → aperçu + jeton à usage
  unique (60 s, lié à l’appareil et à la commande) ; avec `confirm: true` et
  `token` → SET généré par le profil puis exécuté. `400` commande, valeur ou
  canal invalide ; `409` hors ligne, jeton expiré/réutilisé ou commande
  concurrente ; `429` cooldown ; `504` timeout ; `503` MQTT indisponible.
  Jamais de payload brut ; audit `device.command` avec snapshots avant/après.

Stockage : surcharges `/data/device_profiles` (catalogue livré en lecture
seule), backups `/data/profile_backups`, audit `/data/profile_audit.jsonl`,
captures `/data/capture`. Fichiers en `0600`, écriture atomique avec fsync du
fichier et du répertoire. Identifiants MQTT de lecture dérivés du propriétaire,
jamais persistés.

## Risques et parades

| Risque                                      | Parade                                             |
| ------------------------------------------- | -------------------------------------------------- |
| Divergence du moteur partagé                | CI de parité, version épinglée                     |
| Profil appliqué cassant plusieurs appareils | Impact affiché, diff obligatoire, backup, rollback |
| SET live dangereux                          | Typé, confirmé, audité, jamais brut                |
| Import malveillant                          | `safe_load`, limites, refus Zip Slip, dry-run      |
| Valeurs d’instance périmées                 | Timestamps, P3, GET avant action                   |
| Conflit multi-utilisateur                   | Révision + hash, refus et diff                     |

## Jalons

- **M0** : moteur partagé et CI de parité. — atteint (étape 0).
- **M1** : backend V1 lecture/validation/export. — atteint (étape 1).
- **M2** : backend V1 application/rollback/audit. — atteint (étape 1).
- **M3** : UI V1 complète. — atteint (étape 3).
- **M4** : GET et simulation dans l’UI. — atteint (étapes 2-3).
- **M5** : backend V2 commandes typées. — atteint (étape 4).
- **M6** : UI V2 et validation terrain. — UI faite (étape 5) ; validation
  terrain en attente.

## Critères d’acceptation V1

- Un profil invalide ne peut jamais être appliqué.
- Un import valide produit un diff et ne s’applique qu’après confirmation.
- L’application est atomique, sauvegardée et réversible en un clic.
- Le nombre d’appareils impactés est affiché avant toute écriture.
- Une simulation de trame met à jour l’aperçu d’entités sans toucher à
  l’appareil.
- Un GET live ne peut utiliser qu’un namespace déclaré par le profil.
- Aucune action de la page n’est accessible hors ingress admin.

## Critères d’acceptation V2

- Aucun SET ne part sans confirmation, appareil en ligne et namespace autorisé.
- Les commandes sont générées depuis le profil, pas saisies en payload brut.
- Chaque action est auditée et rate-limitée.
- Les échecs (hors ligne, timeout, refus, double clic) sont explicites et ne
  laissent pas l’UI dans un état trompeur.

**Statut (2026-11-22)** : satisfaits côté code et tests (backend, API,
composants). La validation sur un appareil réel reste à faire.
