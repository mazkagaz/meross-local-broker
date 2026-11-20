# D2b — Parité du catalogue d’appareils

**Statut** : jeu pilote livré ; portage du reste du catalogue à venir.
**Référence** : [D2-PLAN.md](D2-PLAN.md) et
[D0-ARCHITECTURE.md](D0-ARCHITECTURE.md).

## Principe

Chaque famille local-MQTT couverte par meross_lan doit avoir un profil
déclaratif qui produit les mêmes entités. Le schéma n’évolue que par ajouts
optionnels ; un profil pilote qui exige une rupture est un défaut de conception
du schéma.

## Jeu pilote livré

| Famille              | Profil          | Match              | Entités                                  |
| -------------------- | --------------- | ------------------ | ---------------------------------------- |
| Hub MSH300           | `meross.msh300` | `kind: hub`, `msh` | hub : online ; modèles ci-dessous        |
| Sous-appareil MS100  | template        | `ms1`              | temperature, humidity, voltage           |
| Sous-appareil MTS100 | template        | `mts1`             | climate (consigne, mesure, mode)         |
| Thermostat MTS200    | `meross.mts200` | `mts2`, `mts3`     | climate (mesure, consigne, mode, on/off) |
| Ventilateur MFC      | `meross.mfc`    | `mfc`              | fan (vitesse, vitesse max)               |
| Éclairage RGB        | `meross.msl120` | `msl120`           | light                                    |

Les trames dorées utilisées par les tests proviennent des définitions de
payloads du client vendorisé (`protocol/types/*.py`) : TempHum, Mts100.All,
Thermostat.Mode et Control.Fan. **Elles restent à confirmer par des captures
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

| Famille                              | État                                           |
| ------------------------------------ | ---------------------------------------------- |
| Prises/switchs (mss310, mss, mss425) | mss310 fait ; autres à porter                  |
| Éclairages (msl100/120/320)          | msl120 fait ; autres à porter                  |
| Volets (mrs)                         | mrs100 fait                                    |
| Hubs (msh)                           | pilote MS100/MTS100 ; autres capteurs à porter |
| Thermostats (mts1/mts2/mts3/mts9)    | MTS200 + MTS100 via hub ; mts9 à confirmer     |
| Ventilateurs (mfc)                   | pilote livré                                   |
| Humidificateurs, purificateurs       | à porter                                       |
| Garages, capteurs, sprinklers        | à porter                                       |

## Critères de sortie D2b

1. Chaque famille ci-dessus a un profil validé par le linter.
2. Les trames réelles de chaque profil sont capturées et versionnées.
3. La matrice modèle ↔ entités est revue avec un appareil réel par famille.
4. Le schéma reste inchangé sur les deux derniers profils portés.
