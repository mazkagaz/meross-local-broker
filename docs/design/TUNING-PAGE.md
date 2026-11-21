# Page de tuning des appareils — plan V1 → V2

**Statut** : proposition de conception, non implémentée.
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

## Étape 5 — UI V2

5.1 Actions dans l’onglet Instance, générées depuis le profil.
5.2 Dialogue de confirmation avec impact et payload résumé.
5.3 Résultat et état rafraîchi ; audit accessible.
5.4 Tests e2e : action autorisée, action refusée, hors ligne, annulation.

## Étape 6 — Documentation et livraison

- Guide utilisateur : overrides, capture, tests, rollback.
- Contrats API et ADR du moteur partagé.
- Notes de version broker.
- Validation terrain : modifier un profil, l’appliquer sur un appareil réel,
  puis revenir au profil livré.

## API cible

| Méthode | Route                                               | V1  | Rôle                           |
| ------- | --------------------------------------------------- | --- | ------------------------------ |
| GET     | `/_admin_/tuning/devices`                           | oui | appareils + profil/source/état |
| GET     | `/_admin_/profiles`                                 | oui | inventaire effectif            |
| GET     | `/_admin_/profiles/{id}`                            | oui | profil effectif + hashes       |
| POST    | `/_admin_/profiles/validate`                        | oui | validation + diff              |
| POST    | `/_admin_/profiles/{id}/preview`                    | oui | simulation de trames           |
| PUT     | `/_admin_/profiles/{id}/override`                   | oui | appliquer (révision attendue)  |
| DELETE  | `/_admin_/profiles/{id}/override`                   | oui | revenir au livré               |
| GET     | `/_admin_/profiles/export`                          | oui | YAML/ZIP                       |
| POST    | `/_admin_/profiles/import`                          | oui | dry-run puis apply             |
| POST    | `/_admin_/tuning/devices/{uuid}/read`               | oui | GET live                       |
| GET     | `/_admin_/tuning/devices/{uuid}/commands`           | V2  | commandes autorisées           |
| POST    | `/_admin_/tuning/devices/{uuid}/commands/{command}` | V2  | SET typé confirmé              |

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

- **M0** : moteur partagé et CI de parité.
- **M1** : backend V1 lecture/validation/export.
- **M2** : backend V1 application/rollback/audit.
- **M3** : UI V1 complète.
- **M4** : GET et simulation dans l’UI.
- **M5** : backend V2 commandes typées.
- **M6** : UI V2 et validation terrain.

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
