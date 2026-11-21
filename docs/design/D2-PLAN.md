# D2 — Schéma 2 et moteur de profils

**Statut** : décisions actées ; D2.1, D2.2.1 à D2.2.5 et D2.3 faits ; D2b
pilote et familles local-MQTT simples portés, familles complexes en attente
de trames réelles (détails : [D2.2-PLAN.md]D2.2-PLAN.md et
[D2b-PARITY.md]D2b-PARITY.md).
**Prérequis** : D1 terminé (broker 1.1.3, intégration 2.4.4/2.4.5).

## Décisions

1. **`schema_version: 2`** adopté, avec une politique d’évolution additive.
2. **Hubs** : un profil hub avec **templates de sous-appareils** ; génération
   `via_device` et identités stables.
3. **Schéma hybride** : tronc commun + sous-schémas stricts pour les plateformes
   complexes ; `state`/`commands` pour les simples.
4. **P3 source B** : endpoint broker dédié pour `RollerShutter.Config`, cache
   côté intégration ; plus de GET Config par entité.
5. **D2b en parallèle borné** : jeu pilote pendant D2, puis portage complet.

## Politique d’évolution du schéma

- `schema_version` est une **version majeure** : seuls les changements
  incompatibles l’incrémentent.
- Les ajouts de champs **optionnels**, de plateformes (`$defs`), de valeurs
  d’énumération et de capacités ne changent pas la version.
- Les clés `x-*` sont **préservées** ; les champs cœur inconnus sont rejetés.
- Un champ n’est jamais réutilisé avec un autre sens. Un champ déprécié reste
  accepté (avertissement moteur) jusqu’au prochain majeur.
- `profile.requires_engine` exprime les fonctionnalités ; le moteur supporte
  **v1 et v2** pendant la transition, puis N et N-1.
- Le catalogue peut publier un profil destiné à un moteur plus récent : un
  moteur ancien l’ignore proprement.

## D2.1 — Schéma et outillage (documentation)

- `docs/device-profiles.schema.json` : version 2 (fait).
- Guide auteur de profil : tronc commun, plateformes, hubs, polling, quirks,
  règles d’évolution.
- Linter de profils : validation du schéma, références de quirks, cohérence
  des namespaces, IDs d’entités uniques.
- Fixtures de compatibilité : profils v1 (MRS100, mss310, msl120) et v2 pilote.

## D2.2 — Moteur (intégration)

Plan détaillé, matrice de tests négatifs et critères de sortie :
[D2.2-PLAN.md]D2.2-PLAN.md. Séquence : D2.2.1 registre (fait), D2.2.2
chemins/matching/compilation simple, D2.2.3 hubs et plateformes complexes,
D2.2.4 dispatch runtime, D2.2.5 interface P3.

Modules prévus, sans détail d’implémentation :

- `profiles/registry.py` : chargement, fusion catalogue/surcharges, révision.
- `profiles/match.py` : résolution type/subtype/MAC/abilities, hubs et
  sous-appareils, priorité et conflits.
- `profiles/compiler.py` : compilation des namespaces (parsing/polling) et des
  entités (modèles, IDs stables, `device` hub/sous-appareil).
- `profiles/engine.py` : registre runtime, handlers par appareil, isolement
  des erreurs, application des stratégies de polling.
- `profiles/quirks.py` : registre de hooks typés (pas de code dans le YAML).
- `broker_config.py` : récupération et cache de la configuration volet (P3).

Contraintes :

- accès au catalogue vendorisé (`devices.json`, `descriptor.parameters`) hors
  boucle événementielle ;
- un profil invalide n’affecte que l’appareil concerné ;
- aucun poll déclenché par l’ajout d’une entité (préparation D3).

## D2.3 — Endpoint broker pour la configuration volet

- Route authentifiée, par exemple `POST /v1/Device/rollerShutterConfig`.
- Réponse : `uuid → {config: [...], position: [...], adjust: [...]}` limitée aux
  appareils du compte.
- Source : tables du broker, déjà alimentées par SET/cache.
- Intégration : appel avec le coordinateur, cache TTL (5–10 min), mise à jour sur
  SET ; aucune dépendance à `meross_iot` pour cette donnée.
- Tests : authentification, isolation par compte, cache, appareil sans config.

## D2b — Parité du catalogue (parallèle borné)

**Jeu pilote** :

- un hub + deux types de sous-appareils (ex. MSH300 + MS100/MTS100) ;
- un thermostat (ex. MTS200/MTS300) ;
- un éclairage et un ventilateur.

**Boucle de retour** :

- porter les profils pilotes dès que le schéma et le squelette du moteur sont
  disponibles ;
- chaque manque de schéma doit être résolu par un ajout optionnel, jamais par
  une rupture ;
- **gel du schéma** lorsque deux profils pilotes consécutifs ne nécessitent plus
  aucun changement ;
- portage du reste du catalogue ensuite, avec la matrice de parité D2b.

## Tests et critères de sortie

- Schéma : v1 et v2 valides, champs inconnus `x-` tolérés, champ cœur inconnu
  refusé, enum futurs gérés par le moteur.
- Moteur : fusion, précédence, conflits, IDs stables, sous-appareils.
- P3 : valeur initiale correcte, SET met à jour le cache, absence de timeout
  `Config`.
- D2b pilote : entités attendues, trames réelles, aucune boucle de polling
  dupliquée.

## Risques

| Risque                           | Parade                                          |
| -------------------------------- | ----------------------------------------------- |
| Schéma élégant mais inutilisable | pilotes D2b en parallèle                        |
| Dérive vers un DSL               | sous-schémas stricts, pas d’expressions         |
| Rupture de compatibilité         | politique additive + fixtures v1/v2             |
| Profil invalide global           | isolation par appareil                          |
| Écart meross_iot                 | D2/D3 remplacent le modèle, pas un shim durable |

## Hors périmètre

- Cloud Meross, Bluetooth de l’intégration, HTTP direct aux appareils.
- D3 (scheduler central, batching, suppression de `meross_iot`).
