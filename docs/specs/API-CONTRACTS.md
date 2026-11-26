# Spécification des contrats API

Version de contrat : **1**.

Les objets décrits sont les charges utiles `data` des réponses authentifiées.
Le broker les valide dans ses tests ; l’intégration embarque une copie
identique et la CI compare les deux dépôts.

## Endpoints couverts

| Contrat                      | Endpoint                              | Usage                         |
| ---------------------------- | ------------------------------------- | ----------------------------- |
| `signin.json`                | `POST /v1/Auth/signIn`                | session, token, clé MQTT      |
| `devlist.json`               | `POST /v1/Device/devList`             | appareils, canaux, ability    |
| `profiles_rev.json`          | `POST /v1/Device/profiles/rev`        | révision et nombre de profils |
| `profiles.json`              | `POST /v1/Device/profiles`            | catalogue signé               |
| `pubkey.json`                | `POST /v1/Device/profiles/pubkey`     | clé publique Ed25519          |
| `roller_shutter_config.json` | `POST /v1/Device/rollerShutterConfig` | cache volet                   |

## Règles d’évolution

- Ajout compatible uniquement : champ optionnel ou nouvelle valeur d’énumération.
- Tout changement cassant incrémente la version du contrat et impose une
  publication coordonnée broker + intégration.
- Les fixtures `contracts/fixtures/*.json` doivent rester identiques dans les
  deux dépôts.

## Datations

- Les instants sont stockés en **UTC naïf** dans SQLite et manipulés en
  **UTC aware** par l’application. Le type `UTCDateTime` fait la conversion.
- Les endpoints tuning et admin sérialisent les dates en ISO 8601 UTC avec le
  suffixe `Z`.
- Les endpoints Meross (`devList`, `_admin_/events`) conservent leur format de
  date HTTP GMT ; les filtres `fromTimestamp`/`toTimestamp` restent des epochs
  UTC.
- Aucune date naïve ou heure locale ne doit être exposée par l’API.

## Emplacements

- Schémas : `meross_local_broker/rootfs/opt/custom_broker/contracts/`
- Validation broker : `test_http_api.py`, `test_profiles.py`
- Comparaison inter-repos : `tests/test_contracts.py` de l’intégration
- Index détaillé : `contracts/README.md`
