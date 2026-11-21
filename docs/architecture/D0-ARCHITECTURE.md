# D0 — Architecture cible : tout local, profils déclaratifs

**Statut** : décisions validées le 2026-11-19 ; **D1 terminé et validé** ;
**schéma 2 rédigé** (voir [D2-PLAN.md]../design/D2-PLAN.md).
**Portée** : broker, intégration Home Assistant, pairer.

## Contexte

La suite actuelle fonctionne de bout en bout sans cloud, mais :

- la gestion des appareils repose sur `meross_iot` et son modèle ability/mixin,
  inadapté à certains appareils (MRS100) ;
- le nombre de modèles réellement décrits est faible et leur description est
  dispersée dans le code ;
- broker et intégration sont deux artefacts dont l'installation et la
  configuration ne sont pas guidées ;
- meross_lan apporte un protocole et un catalogue riches, mais dépend du cloud
  officiel pour l'appairage/les clés et embarque une couche HA liée à une
  config entry par appareil.

## Décisions

### D0.1 — Un produit, deux artefacts

- **Broker** = add-on (MQTT/TLS, API HTTPS, comptes, ACL, profils).
- **Intégration** = entités Home Assistant, consommatrice du broker.
- Séparation technique assumée : une intégration ne peut pas héberger un broker,
  un add-on ne peut pas créer d'entités.
- Parcours **guidé niveau 2** sur HA OS/Supervised : l'intégration détecte
  l'add-on, propose de l'installer/démarrer via le Supervisor, puis une seule
  saisie du compte local configure les deux.
- HA Container/Core : pas de Supervisor ni d'add-on ; documentation Docker
  manuelle, broker joignable par réseau.
- Version, documentation et identité produit communes ; dépôts séparés.

### D0.2 — Le broker est la source de vérité des profils

- Stockage du catalogue livré et des surcharges dans le broker.
- Validation de schéma, signature, calcul de révision, exposition à
  l'intégration via l'API.
- L'intégration ne lit jamais de YAML local : elle consomme la révision servie
  par le broker.

### D0.3 — Profils déclaratifs et surcharges

- **Catalogue livré** : profils validés, lecture seule, versionnés avec
  l'add-on.
- **Surcharges utilisateur** dans `/data/device_profiles/` : visibles seulement
  en **mode avancé** ; remplacement total possible ; marquées `custom`.
- Précédence : surcharge valide > catalogue ; une surcharge invalide n'est
  jamais appliquée.
- Aucune mise à jour de catalogue n'écrase une surcharge.

### D0.4 — Catalogue signé, mise à jour optionnelle

- Index signé **Ed25519**, clé publique embarquée ; vérification avant usage.
- Contrôle réseau **désactivé par défaut**, activable en mode avancé.
- Par appareil : entité **`update`** native (`installed_version` /
  `latest_version`, action « Installer ») + **capteur diagnostic**
  (`source: bundled|custom`, version, base, hash).
- En surcharge custom, `update` informe sans écraser ; « Installer » demande
  confirmation et sauvegarde la surcharge.

### D0.5 — Rechargement à chaud à deux modes

- **Mode 1 — ajout/mise à jour** : nouvelles entités et payloads appliqués ;
  entités retirées laissées indisponibles.
- **Mode 2 — appliquer aussi les retraits** : entités retirées désactivées
  proprement ; jamais supprimées automatiquement.
- Aperçu du diff et validation avant application ; révision de profils
  propagée à l'intégration ; seuls les appareils concernés sont rechargés.

### D0.6 — Socle protocolaire vendorisé

- Vendorisation de `merossclient` (MIT, meross_lan v6.0.2) **restreinte** :
  `protocol/`, `DeviceDescriptor`/`HostAddress`, `device/`, `client/mqtt.py`,
  `exceptions.py`, `logging.py`, éventuellement `library/devices.json`.
- Exclus : `cloudapi.py`, Bluetooth, `broadcast.py`, `client/http.py`.
- Commit upstream épinglé, licence/NOTICE conservés, adaptations dans un
  adaptateur hors du dossier vendorisé.
- Notre couche HA, nos identités (`unique_id`) et notre UX sont conservées.

### D0.7 — Invariants de sécurité

- Aucune dépendance obligatoire au cloud ; capture et catalogue hors ligne
  possibles.
- TLS/CA locale épinglée, Argon2id, sessions hachées, ACL inter-device et
  inter-composant, intégrité MQTT.
- Profils **données uniquement** : pas de Jinja, pas d'`eval`, pas de code
  arbitraire ; hooks typés référencés.
- Surcharges validées avant activation ; capture jamais appliquée
  automatiquement.
- Export de capture **obfusqué par défaut** (pseudonymes stables, secrets
  supprimés, horodatages relatifs) avec manifeste et revue avant partage.

## Non-objectifs

- Une entrée de configuration par appareil.
- Client cloud Meross, Bluetooth.
- HTTP direct aux appareils comme transport principal.
- Suppression automatique d'entités.

## Flux

```
Appareil ──MQTT/TLS──> Broker ──profils/révisions──> Intégration HA
                        │                              │
                        ├── panneau avancé (édition,   ├── entités (update,
                        │   capture, validation)       │   diagnostic)
                        └── /data/device_profiles      └── rechargement ciblé
```

## Contrats d'API (proposition, noms à figer en D1)

- `GET /v1/Device/profiles/rev` : révision courante.
- `GET /v1/Device/profiles` : profils fusionnés + source/version (authentifié).
- Admin ingress-only : import/validation/activation d'une surcharge, export,
  capture, aperçu de diff, réglage des modes.

## Risques et parades

| Risque                                | Parade                                                           |
| ------------------------------------- | ---------------------------------------------------------------- |
| Dérive du langage de profils          | schéma strict, `x-` extensions, hooks typés                      |
| Profil qui casse toute l'architecture | `requires_engine`, isolation par appareil, dernier profil valide |
| Perte d'automatisations               | conservation des `unique_id`, retrait désactivé jamais supprimé  |
| Dérive upstream du socle              | commit épinglé, tests de conformité, mise à jour revue           |
| Mise à jour signée compromise         | signature Ed25519, opt-in, diff, pas d'auto-application          |
| Capture contenant des secrets         | scrub systématique, dossier séparé, activation manuelle          |

## Découpage suivant

### État d’avancement

- **D1 : terminé et validé** (broker 1.1.3, intégration 2.4.4). Transport MQTT
  applicatif, descripteurs, catalogue lisible, résolution des transactions,
  logs DEBUG obfusqués. Capteur `Broker profile backend` = `connected`.
- **D2 et D2b : faits** (moteur, P3, pilote et familles simples ; reste de la
  matrice de parité en attente de trames réelles).
- **D3 : fait (mode opt-in)** : scheduler central, batching, lazy poll, rate
  limiting, entités issues des profils (switch, light, sensor, binary_sensor,
  cover, number, button), sous-appareils, disponibilité. Les plateformes
  complexes, la restauration d’état et la reprise exacte des `unique_id`
  historiques restent avant D5.
- **D4 : avancé** : surcharges de profils dans `/data/device_profiles`,
  rechargement à chaud exposé à l’admin, diff added/removed/changed,
  exposition source/révision, mode capture avec assainissement/limites/
  brouillon, rechargement automatique de l’entrée HA au changement de
  révision (vérification toutes les 60 s, surcharges détectées
  automatiquement), catalogue signé Ed25519 vérifié par l’intégration,
  entités `update` par appareil/sous-appareil et guide avancé
  ([D4-GUIDE.md]../design/D4-GUIDE.md). D4 est terminé côté backend/documentation ;
  l’UI graphique dédiée n’est pas planifiée.
- **D5 : terminé** : suite de parité/trames dorées pour les 16 profils,
  broker sans `meross_iot`, accès HTTP catalogue/P3 migré vers un client
  signé maison, échelles par champ, entités profils climate/fan/humidifier et
  bascule opt-in `profile_entities_only` (identifiants historiques préservés,
  entités historiques supprimées pour les appareils couverts), et découverte
  des appareils de l’adaptateur et du polling du coordinateur via l’API
  broker (`broker_devices.py`), et authentification de la config flow via le
  client signé (`BrokerHttpClient.async_login`, identifiants locaux). Restent
  le manager (encore utilisé pour les entités historiques), les patches et
  les fichiers d’entités historiques, puis D5.1.
- D5.1 : à venir.

### D2 — Moteur de profils, schéma 2

- **Schéma 2** : évolution additive uniquement ; seuls les changements
  incompatibles incrémentent `schema_version`. Voir [D2-PLAN.md]../design/D2-PLAN.md.
- **Schéma hybride** : tronc commun + sous-schémas stricts pour les plateformes
  complexes ; `state`/`commands` pour les simples.
- **Hubs** : un profil hub avec templates de sous-appareils (`via_device`).
- Contenu :
  - plateformes manquantes : `climate`, `fan`, `humidifier`, `calendar`,
    `media_player`, `siren`, `update` ;
  - **hubs et sous-appareils** : identité, `via_device`, entités par
    sous-appareil ;
  - **polling par namespace** : stratégie (`default`, `smart`, `once`,
    `chunked`), période, capacité PUSH, taille de réponse estimée ;
  - capacités/quirks supplémentaires nécessaires au catalogue.
- Moteur : registre, fusion catalogue/surcharges, validation, révision.
- Tout accès au catalogue vendorisé (`devices.json`, `descriptor.parameters`)
  se fait hors boucle événementielle, via l’exécuteur Home Assistant.
- **P3** (config volet via un endpoint broker dédié et un cache, sans GET par
  entité) est traité ici.

### D2b — Parité du catalogue d’appareils (parallèle borné)

- Pilote démarré pendant D2 : hub + sous-appareils, thermostat, éclairage/
  ventilateur ; gel du schéma après deux pilotes sans changement.
- Puis porter en profils les types local-MQTT couverts par meross_lan : prises,
  éclairages, volets, hubs et sous-appareils, thermostats, capteurs,
  humidificateurs, etc.
- Les types liés au cloud, au Bluetooth de l’intégration ou au HTTP direct
  restent hors périmètre.
- Critère de sortie : matrice de parité modèle ↔ entités, validée par trames
  observées et tests.

### D3 — Entités, scheduler et migration des identités

- Scheduler **central par appareil** : une tâche, un verrou, `next_poll_epoch`.
- **Namespace handlers** partagés entre entités, stratégies de polling de D2.
- **Batching** `Appliance.Control.Multiple`, limites de taille de réponse,
  file « lazy poll » et rate limiting configurable.
- **Aucun `update_before_add`** : l’ajout d’une entité ne déclenche pas
  `device.async_update()` ; suppression des doublons `Config`/`System.All`
  constatés en série A/B. **P1** est ainsi couvert.
- **P2** (coalescence des updates par appareil) si des bursts subsistent.
- Entités : plateformes étendues, hubs/sous-appareils, restauration et
  disponibilité ; `unique_id` existants conservés.

**État** : socle et entités livrés. `profiles/scheduler.py` fournit une tâche
et un verrou par appareil, le plan de polling, le batching
`Appliance.Control.Multiple`, la file lazy, le rate limiting et le backoff ;
les réponses sollicitées ne sont plus dispatchées deux fois.
`profile_entities.py` crée les entités des plateformes simples depuis les
profils, avec commandes, abonnements runtime et `via_device` des
sous-appareils. Ces entités sont derrière l’option dédiée
`profile_entities` (elle-même utile seulement avec `profile_backend`) et
coexistent avec les entités historiques jusqu’à D5 : identifiants distincts,
pas de collision, mais doublons fonctionnels pendant la transition.

### D4 — UX avancée sans changer le parcours de base

- Édition des profils, surcharges, diff et rechargement à chaud.
- Capture de trames et génération de brouillon.
- Catalogue signé, entités `update` par appareil, capteur source/version.
- Parcours guidé Supervisor et documentation HA Container/Core.

**État** : les surcharges sont lues dans `/data/device_profiles` (même `id`
qu’un profil livré ou nouveau profil) ; un fichier invalide est signalé et le
profil livré reste actif. `POST /_admin_/profiles/reload` recharge le
catalogue et renvoie `added`/`removed`/`changed`. Le capteur de diagnostics
expose révision, source et version. L’intégration reprend le nouveau
catalogue au prochain démarrage ou rechargement de l’entrée.

Le mode capture est activable par appareil via
`/_admin_/capture/start|stop|status|draft` : sessions sous `/data/capture`
(0600/0700), secrets retirés, identifiants pseudonymisés, limites de durée,
de taille et de nombre de trames, et brouillon YAML agrégé par namespace.

Côté HA, l’adaptateur compare la révision du catalogue toutes les 60 s et
recharge l’entrée de configuration quand elle change : les profils surchargés
s’appliquent sans redémarrage de Home Assistant.

Le catalogue est signé en Ed25519 (paire générée dans `/data` avec openssl,
clé publique exposée par `/v1/Device/profiles/pubkey`). L’intégration vérifie
la signature : un catalogue signé invalide est refusé, un catalogue non signé
(ancien broker) est accepté et signalé dans les diagnostics.

Chaque appareil et sous-appareil exposé par les profils a une entité
`update` (titre, source, version installée/dernière, description) dont
l’action « installer » recharge l’entrée pour réappliquer le catalogue.

Les surcharges déposées dans `/data/device_profiles` sont détectées à la
prochaine lecture du catalogue, sans redémarrage. Le parcours guidé et les
limites Supervisor/Container/Core sont documentés dans
[D4-GUIDE.md]../design/D4-GUIDE.md.

### D5 — Parité, trames dorées, suppression de `meross_iot`

- Tests de parité et trames dorées pour chaque profil livré.
- Migration complète des commandes vers le socle vendorisé.
- Suppression de `meross_iot`, des patches et des entités historiques.

**État** : la suite `test_profile_parity.py` couvre les 16 profils avec des
trames dorées (dont la multiprise par canal) ; le broker n’importe plus `meross_iot` (remplacé par
`compat.py`, dépendance retirée de `requirements.txt`). Côté intégration, le
catalogue et la config P3 passent par `broker_http.py` : signature d’enveloppe
locale, TLS du broker, plus aucune dépendance à `MerossHttpClient`. Le
manager, les commandes des entités historiques et les patches restent à
migrer.

### D5.1 — Nettoyage des topics ACK

Terminé : l’option `legacy_user_topic_acks` et la copie des ACK sur le topic
utilisateur ont été supprimées.

### Transition des topics ACK

De 1.0.0 à D5, le broker publiait une réponse d’appareil **deux fois** : sur
`/app/<userId>/subscribe` (clients historiques, PUSH, `meross_iot`) et sur le
topic `header.from` (`/app/<userId>-<appId>/subscribe`) attendu par
`merossclient`.

La copie temporaire a été retirée avec l’option `legacy_user_topic_acks`.
Désormais :

1. **Broker** : PUSH (`PUSH`) sur `/app/<userId>/subscribe` uniquement ; ACK
   (`GETACK`, `SETACK`, `ERROR`) sur le topic `header.from` du propriétaire
   uniquement. Repli sur le topic utilisateur seulement si `from` est absent ou
   invalide.
2. **Tests** : ACK sur le topic applicatif, absence d’ACK sur le topic
   utilisateur, PUSH inchangés et non-régression du client standard.

Condition d’entrée remplie : D3 terminé, intégration profile-only et client
standard vendorisé.
