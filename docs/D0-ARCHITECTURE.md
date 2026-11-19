# D0 — Architecture cible : tout local, profils déclaratifs

**Statut** : décisions validées le 2026-11-19 ; schéma v0 à figer.
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

- D1 : adaptateur broker local (MQTT applicatif + descripteurs) et révision.
- D2 : moteur de profils, registre, fusion et validation.
- D3 : entités et migration des identités.
- D4 : UX avancée (édition, capture, `update`) sans changer le parcours de base.
- D5 : parité, trames dorées, suppression de `meross_iot`.
- D5.1 : nettoyage des topics ACK (voir ci-dessous).

### Transition des topics ACK

De 1.0.0 à D5, le broker publie une réponse d'appareil **deux fois** : sur
`/app/<userId>/subscribe` (clients historiques, PUSH, `meross_iot`) et sur le
topic `header.from` (`/app/<userId>-<appId>/subscribe`) attendu par
`merossclient`.

**Toggle temporaire** : `legacy_user_topic_acks` (broker 1.1.1, défaut
`true`) permet de couper la copie sur le topic utilisateur pendant les tests,
sans supprimer le code. Il est explicitement **supprimé en D5.1** avec
`patch_mqtt_acks_on_user_topic`.

Nettoyage prévu en **D5.1**, une fois les entités migrées :

1. **Broker** : PUSH (`PUSH`) sur `/app/<userId>/subscribe` uniquement ; ACK
   (`GETACK`, `SETACK`, `ERROR`) sur le topic `header.from` du propriétaire
   uniquement. Repli sur le topic utilisateur seulement si `from` est absent ou
   invalide (compatibilité de dernier recours, documentée).
2. **Intégration** : suppression de `patch_mqtt_acks_on_user_topic` et de ses
   tests, une fois toutes les commandes passées par le client vendorisé.
3. **Tests** : trames dorées ACK/PUSH, absence d'ACK sur le topic utilisateur,
   non-régression du client standard.
4. **Version** : broker 1.2.0 (changement de routage) et intégration 2.5.0
   (suppression du patch), avec note dans `RELEASE_NOTES.md`.

Condition d'entrée : D3 terminé (plus aucune commande métier via
`meross_iot`) et validation sur matériel réel.
