# D2b — Parité du catalogue d’appareils

**Statut** : jeu pilote, familles local-MQTT simples et multiprises portés ;
quelques familles restent en attente de trames réelles (voir la matrice).
**Référence** : [D2-PLAN.md]../design/D2-PLAN.md et
[D0-ARCHITECTURE.md]../architecture/D0-ARCHITECTURE.md.

## Principe

Chaque famille local-MQTT couverte par meross_lan doit avoir un profil
déclaratif qui produit les mêmes entités. Le schéma n’évolue que par ajouts
optionnels ; un profil pilote qui exige une rupture est un défaut de conception
du schéma.

## Profils livrés

| Famille              | Profil          | Match                       | Entités                                   |
| -------------------- | --------------- | --------------------------- | ----------------------------------------- |
| Hub MSH300           | `meross.msh300` | `kind: hub`, `msh`          | hub : online ; modèles ci-dessous         |
| Sous-appareil MS100  | template        | `ms1`                       | temperature, humidity, voltage            |
| Sous-appareil MS130  | template        | `ms130`                     | temperature, humidity                     |
| Sous-appareil MTS100 | template        | `mts1`                      | climate (consigne, mesure, mode)          |
| Sous-appareil MS200  | template        | `ms200`                     | binary_sensor fenêtre                     |
| Sous-appareil MS400  | template        | `ms400`                     | binary_sensor fuite d’eau                 |
| Capteur MS600        | `meross.ms600`  | `ms600`                     | présence, distance, luminosité            |
| Sous-appareil GS559  | template        | `gs559`                     | fumée, défaut, silencieux, interconnexion |
| Porte de garage      | `meross.garage` | `msg`, `rsg`                | cover (ouvrir/fermer, état)               |
| Thermostat MTS200    | `meross.mts200` | `mts2`                      | climate (mesure, consigne, mode, on/off)  |
| Thermostat MTS300    | `meross.mts300` | `mts3`                      | climate (échelle 0,01)                    |
| Ventilateur MFC      | `meross.mfc`    | `mfc`                       | fan (vitesse, vitesse max)                |
| Prises/interrupteurs | `meross.mss`    | `mss*`, `mop`, `p11`, `r1x` | switch (canal 0)                          |
| Multiprises          | `meross.mss425` | `mss425`, `msp844`          | switch par canal exposé                   |
| Variateur Mss5       | `meross.mss5`   | `mss5`                      | light                                     |
| Éclairages           | `meross.msl`    | `msl*`                      | light (onoff, luminosité, RGB)            |
| Volet MRS100         | `meross.mrs100` | `mrs100`                    | cover, durées, calibration, statut        |
| Volets               | `meross.mrs`    | `mrs`                       | cover (position, ouvrir/fermer/stop)      |
| Diffuseur MOD        | `meross.mod`    | `mod`                       | humidifier (diffusion) + light            |

Les trames dorées utilisées par les tests proviennent des définitions de
payloads du client vendorisé (`protocol/types/*.py`) : TempHum, Sensor.All,
Mts100.All, Thermostat.Mode, ToggleX, Light, RollerShutter.Position,
Control.Fan et Diffuser.\*. **Elles restent à confirmer par des captures
réelles** avant de déclarer la parité validée sur matériel.

## Enseignements du pilote

- Le schéma n’a nécessité **aucun changement cassant** : hubs/sub-appareils,
  plateformes complexes et `capabilities` suffisent. Les multiprises ajoutent
  deux champs optionnels (`channel: $channels`, `state.select`) et le moteur
  2.3 qui les honore.
- Le seul ajout est moteur : le jeton `$id` pour adresser un sous-appareil
  dans une commande (`Appliance.Hub.Mts100.Mode`, `…Temperature`). Il est
  refusé hors template.
- Les thermostat MTS100 utilise `Appliance.Hub.Mts100.All` comme source
  d’état unique ; MTS200 et MTS300 utilisent
  `Appliance.Control.Thermostat.Mode`.
- Les échelles diffèrent : MTS200 en dixièmes (×0,1), MTS300 en centièmes
  (×0,01), d’où deux profils. Le mapping fin des modes (valeurs brutes →
  `hvac_modes`) reste un quirk de plateforme (D3).

## Couverture restante (meross_lan local-MQTT)

| Famille                        | État                                              |
| ------------------------------ | ------------------------------------------------- |
| Prises/switchs mono-canal      | porté (`mss`, `mss310`, `mss5`)                   |
| Multiprises (mss425/msp844)    | porté : sélection par canal, entités dynamiques   |
| Éclairages                     | porté (`msl`, `msl120`, `msl320*`)                |
| Volets                         | porté (`mrs`, `mrs100`)                           |
| Hubs                           | MS100/MS130/MTS100/MS200/MS400/GS559 portés       |
| Capteurs                       | MS600 porté (push) ; MS200/MS400 via hub          |
| Thermostats                    | MTS200/MTS300 + MTS100 portés ; mts9 à confirmer  |
| Ventilateurs                   | porté (`mfc`)                                     |
| Diffuseurs/humidificateurs     | porté (`mod`) ; purificateurs à confirmer         |
| Garages (msg/rsg)              | porté : State objet ou liste, cover ouvrir/fermer |
| Sprinklers MST, énergie, HP110 | en attente de trames réelles                      |
| Capteur hub GS559 (fumée)      | porté : alarme/défaut/silencieux via `on_values`  |

Gaps identifiés pour la suite :

- formes de payloads non documentées dans le client vendorisé pour les
  sprinklers et HP110.

Le gap des chemins indexés par canal est résolu par `channel: $channels` +
`state.select` (moteur 2.3), qui clone l’entité par canal découvert et
sélectionne l’élément de liste par sa clé `channel`.

**Ordre de publication** : livrer d’abord l’intégration avec le moteur 2.4
(`mss425`, GS559 et garage), puis le broker. Un moteur antérieur ignore les
profils concernés : `mss425`/`msp844` retombent sur `mss` (canal 0), et un hub
dont le profil exige 2.4 n’est pas apparié tant que l’intégration n’est pas à
jour.

## Critères de sortie D2b

1. Chaque famille ci-dessus a un profil validé par le linter.
2. Les trames réelles de chaque profil sont capturées et versionnées.
3. La matrice modèle ↔ entités est revue avec un appareil réel par famille.
4. Le schéma n’évolue que par ajouts optionnels (`$channels`,
   `state.select`, `on_values`, quirk `garage_door`).
