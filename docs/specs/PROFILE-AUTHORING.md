# Guide auteur de profils d’appareils

Un profil décrit un type d’appareil Meross : identité, namespaces, entités et
polling. C’est **une donnée**, jamais du code exécuté.

## Emplacements

- Profils livrés (canoniques) :
  `meross_local_broker/rootfs/opt/custom_broker/device_profiles/`.
- Schéma : `device_profiles/schema.json` (copie de
  [device-profiles.schema.json](../device-profiles.schema.json)).
- Exemples documentaires : [profiles/](../profiles/).

## Vérifier un profil

```bash
cd meross_local_broker/rootfs/opt/custom_broker
../../../../.venv/bin/python profile_lint.py
```

Pour un fichier ou un dossier :

```bash
python3 profile_lint.py --schema device_profiles/schema.json \
  /chemin/vers/mon-profil.yaml
```

Le linter vérifie le schéma JSON, l’unicité des IDs de profil, l’unicité des
clés d’entité, les plateformes, les hubs et la présence des namespaces
référencés.

## Structure

```yaml
schema_version: 2
profile:
  id: meross.exemple
  version: "2026.11.0"
  requires_engine: ">=2.0"
match:
  kind: device # device | hub | any
  type: [mss310]
  abilities:
    all: [Appliance.Control.ToggleX]
payloads:
  Appliance.Control.ToggleX:
    methods: [GET, SET, GETACK, SETACK, PUSH]
    polling:
      strategy: default # default | smart | once | chunked
      period_s: 30
      push: true
entities:
  - key: switch
    platform: switch
    state:
      namespace: Appliance.Control.ToggleX
      channel: $channel
      fields: { onoff: "togglex[0].onoff" }
    commands:
      turn_on:
        namespace: Appliance.Control.ToggleX
        payload:
          { channel: $channel, togglex: [{ channel: $channel, onoff: 1 }] }
```

## Entités

Tronc commun : `key`, `platform`, `name`, `channel`, `device`
(`hub`/`subdevice`), `device_class`, `entity_category`, `unit`, `min_value`,
`max_value`, `step`, `state`, `commands`, `capabilities`, `quirks`.
Les entrées de `state.fields` sont un chemin (`"togglex[0].onoff"`) ou un
objet `{ path, scale, offset }` pour une mise à l’échelle par champ.
`on_values: [23, 25]` transforme la valeur brute en booléen (membre de la
liste), utile pour les codes d’état des capteurs.
`legacy_classifiers` permet de conserver l’identifiant historique d’une
entité lors de la bascule vers les entités profils.

- Plateformes simples (`cover`, `switch`, `light`, `sensor`, `binary_sensor`,
  `number`, `button`, `select`) : `state`/`commands`.
- Plateformes complexes (`climate`, `fan`, `humidifier`, `calendar`,
  `media_player`, `siren`, `update`) : sous-schéma strict, avec `capabilities`
  obligatoire pour `climate` et `fan`.

Jetons autorisés dans les payloads : `$channel`, `$value` et `$id`
(sous-appareils uniquement). Aucune expression, aucun template.

## Canaux multiples

Une entité peut être clonée pour chaque canal exposé par l'appareil :

```yaml
profile:
  requires_engine: ">=2.3"
entities:
  - key: outlet
    platform: switch
    channel: $channels
    name: "Outlet $channel_number"
    state:
      namespace: Appliance.Control.ToggleX
      channel: $channel
      select: { path: togglex, key: channel }
      fields: { onoff: onoff }
```

- `channel: $channels` marque un template ; l'intégration crée une entité par
  canal découvert dans le descriptor (`digest`, avec repli sur le type).
- `state.select` choisit l'élément de la liste dont `key` vaut le canal de
  l'entité ; les chemins de `state.fields` sont relatifs à cet élément. Cela
  évite de dépendre de l'ordre du tableau.
- `name` accepte `$channel` (index) et `$channel_number` (index + 1).
- Les commandes gardent `$channel`, substitué à l'envoi.
- `requires_engine: ">=2.3"` : les moteurs antérieurs ignorent le profil au
  lieu de créer une entité incomplète.
- Les templates de canaux ne sont pas acceptés dans `subdevices`.
- `state.select` accepte aussi un objet unique (anciens firmwares) en plus
  d’une liste.
- Quirk `garage_door` : `is_closed` lit le champ `open` (1 = ouvert) et
  n’expose pas de position.

## Polling

Chaque namespace peut déclarer :

- `strategy` : `default` (pas de poll si PUSH), `smart` (périodique avec
  limitation), `once` (état constant), `chunked` (gros payloads) ;
- `period_s` : période ;
- `push` : un PUSH supprime le poll périodique ;
- `response_size` : estimation pour le batching.

## Hubs et sous-appareils

```yaml
match:
  kind: hub
  type: [msh300]
entities: []
subdevices:
  - match:
      type: [ms100]
    payloads:
      Appliance.Hub.Sensor.TempHum:
        methods: [GETACK, PUSH]
    entities:
      - key: temperature
        platform: sensor
        device: subdevice
        state:
          namespace: Appliance.Hub.Sensor.TempHum
          fields: { value: "temperature" }
```

Chaque template est compilé en appareil HA avec `via_device` et une identité
stable.

## Évolution du schéma

- `schema_version` est une version **majeure** : seuls les changements
  incompatibles l’incrémentent.
- Ajouter un champ optionnel, une plateforme, une valeur d’énumération ou une
  capacité ne change pas la version.
- `profile.requires_engine` indique les fonctionnalités nécessaires.
- Les clés `x-*` sont conservées ; les champs cœur inconnus sont refusés.
- Un champ n’est jamais réutilisé avec un autre sens.

## Cycle de validation

1. Capture de trames (mode avancé) → brouillon.
2. Compléter le profil, lancer `profile_lint.py`.
3. Tester sur l’appareil (entités, commandes, polling).
4. Activer en surcharge locale, puis proposer une PR pour le catalogue livré.

## Sécurité

Un profil ne contient jamais de secret, d’URL, de certificat ni de commande
shell. Les hooks sont des noms typés, fournis par le moteur.
