# D2b — Parité du catalogue d’appareils

**Statut** : jeu pilote et familles local-MQTT simples portés ; quelques
familles restent en attente de trames réelles (voir la matrice).
**Référence** : [D2-PLAN.md]../design/D2-PLAN.md et
[D0-ARCHITECTURE.md]../architecture/D0-ARCHITECTURE.md.

## Principe

Chaque famille local-MQTT couverte par meross_lan doit avoir un profil
déclaratif qui produit les mêmes entités. Le schéma n’évolue que par ajouts
optionnels ; un profil pilote qui exige une rupture est un défaut de conception
du schéma.

## Profils livrés

| Famille              | Profil          | Match                       | Entités                                  |
| -------------------- | --------------- | --------------------------- | ---------------------------------------- |
| Hub MSH300           | `meross.msh300` | `kind: hub`, `msh`          | hub : online ; modèles ci-dessous        |
| Sous-appareil MS100  | template        | `ms1`                       | temperature, humidity, voltage           |
| Sous-appareil MS130  | template        | `ms130`                     | temperature, humidity                    |
| Sous-appareil MTS100 | template        | `mts1`                      | climate (consigne, mesure, mode)         |
| Thermostat MTS200    | `meross.mts200` | `mts2`, `mts3`              | climate (mesure, consigne, mode, on/off) |
| Ventilateur MFC      | `meross.mfc`    | `mfc`                       | fan (vitesse, vitesse max)               |
| Prises/interrupteurs | `meross.mss`    | `mss*`, `mop`, `p11`, `r1x` | switch (canal 0)                         |
| Variateur Mss5       | `meross.mss5`   | `mss5`                      | light                                    |
| Éclairages           | `meross.msl`    | `msl*`                      | light (onoff, luminosité, RGB)           |
| Volet MRS100         | `meross.mrs100` | `mrs100`                    | cover, durées, calibration, statut       |
| Volets               | `meross.mrs`    | `mrs`                       | cover (position, ouvrir/fermer/stop)     |
| Diffuseur MOD        | `meross.mod`    | `mod`                       | humidifier (diffusion) + light           |

Les trames dorées utilisées par les tests proviennent des définitions de
payloads du client vendorisé (`protocol/types/*.py`) : TempHum, Sensor.All,
Mts100.All, Thermostat.Mode, ToggleX, Light, RollerShutter.Position,
Control.Fan et Diffuser.\*. **Elles restent à confirmer par des captures
réelles** avant de déclarer la parité validée sur matériel.

## Enseignements du pilote

- Le schéma n’a nécessité **aucun changement** : hubs/sub-appareils,
  plateformes complexes et `capabilities` suffisent.
- Le seul ajout est moteur : le jeton `$id` pour adresser un sous-appareil
  dans une commande (`Appliance.Hub.Mts100.Mode`, `…Temperature`). Il est
  refusé hors template.
- Les thermostat MTS100 utilise `Appliance.Hub.Mts100.All` comme source
  d’état unique ; MTS200 utilise `Appliance.Control.Thermostat.Mode`.
- Le mapping fin des modes (valeurs brutes → `hvac_modes`) et les échelles
  de température par champ restent des quirks de plateforme (D3), pas du YAML.

## Couverture restante (meross_lan local-MQTT)

| Famille                                   | État                                                    |
| ----------------------------------------- | ------------------------------------------------------- |
| Prises/switchs mono-canal                 | porté (`mss`, `mss310`, `mss5`)                         |
| Multiprises (mss425/msp844)               | en attente : chemins indexés par canal                  |
| Éclairages                                | porté (`msl`, `msl120`, `msl320*`)                      |
| Volets                                    | porté (`mrs`, `mrs100`)                                 |
| Hubs                                      | MS100/MS130/MTS100 portés ; autres capteurs à confirmer |
| Thermostats                               | MTS200/MTS300 + MTS100 portés ; mts9 à confirmer        |
| Ventilateurs                              | porté (`mfc`)                                           |
| Diffuseurs/humidificateurs                | porté (`mod`) ; purificateurs à confirmer               |
| Garages (msg/rsg)                         | en attente : forme exacte du payload State              |
| Sprinklers MST, énergie, HP110            | en attente de trames réelles                            |
| Autres capteurs hub (MS200/400/600/GS559) | en attente de trames réelles                            |

Gaps identifiés pour la suite :

- **chemins indexés par canal** : les multiprises renvoient une liste
  `togglex` complète ; un chemin statique ne peut pas sélectionner l’élément
  dont `channel` correspond à l’entité.
- formes de payloads non documentées dans le client vendorisé pour les
  garages, purificateurs, sprinklers et certains capteurs hub.

## Critères de sortie D2b

1. Chaque famille ci-dessus a un profil validé par le linter.
2. Les trames réelles de chaque profil sont capturées et versionnées.
3. La matrice modèle ↔ entités est revue avec un appareil réel par famille.
4. Le schéma reste inchangé sur les deux derniers profils portés.
