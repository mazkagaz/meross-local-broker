[English](OVERRIDE-MRS100-MOVEMENT.md) · **Français**

# Ajouter une fonctionnalité sans coder — exemple MRS100

Cette méthode ajoute une entité à un appareil existant **sans modifier le code
du broker ni le catalogue livré**. Tout passe par une surcharge locale du profil
et par la page de tuning.

L’exemple ajoute un capteur diagnostic **Movement** au MRS100, alimenté par les
PUSH `Appliance.RollerShutter.State` que l’appareil émet quand on le commande
au mur. Il sert de preuve de concept : une fonctionnalité nouvelle, validée sur
une capture réelle, sans reconstruction d’image.

## 1. Capturer le comportement réel

1. Ouvrir **Device tuning** (icône tune, ingress Supervisor).
2. Onglet **Appareils**, sélectionner le volet, puis **Start capture**.
3. Descendre le volet au mur, l’arrêter, puis le remonter.
4. **Stop**, puis **Download ZIP**.

Une capture réelle du MRS100 contient par exemple :

| t (s) | Sens | Namespace                          | Payload                  |
| ----- | ---- | ---------------------------------- | ------------------------ |
| 3,66  | rx   | `Appliance.RollerShutter.State`    | `state=2` (fermeture)    |
| 8,69  | rx   | `Appliance.RollerShutter.Position` | `position=84`            |
| 9,71  | rx   | `Appliance.RollerShutter.State`    | `state=0`, `stoppedBy=1` |
| 11,76 | rx   | `Appliance.RollerShutter.State`    | `state=1` (ouverture)    |
| 16,78 | rx   | `Appliance.RollerShutter.Position` | `position=100`           |
| 17,80 | rx   | `Appliance.RollerShutter.State`    | `state=0`, `stoppedBy=0` |

Enseignements :

- `Appliance.RollerShutter.State` donne la **direction immédiatement** :
  `0` = arrêt, `1` = ouverture, `2` = fermeture.
- Les champs `timestamp` et `stoppedBy` accompagnent les PUSH réels ; ils ne
  sont pas nécessaires au mapping, mais utiles à documenter.
- `Position` est plus sparse (84 %, puis 100 %) : il ne faut pas compter sur lui
  pour un retour d’action instantané.

## 2. Choisir le mapping

Le payload `State` est un tableau, comme `Position` :

```json
{ "state": [{ "channel": 0, "state": 2, "timestamp": 1795356738 }] }
```

Le moteur partagé lit un chemin dans le payload. Pour le canal 0, le chemin est
donc `state[0].state` — de la même façon que le profil livré utilise
`position[0].position` pour le cover.

On crée une entité `sensor` diagnostic :

- namespace : `Appliance.RollerShutter.State` ;
- canal : `0` (donc `$channel` dans la déclaration) ;
- valeur : `state[0].state` ;
- état HA : `0` arrêt, `1` ouverture, `2` fermeture (valeurs brutes).

## 3. Créer la surcharge dans le tuning

Prérequis : broker avec la page de tuning, profil `meross.mrs100` associé à
l’appareil et appareil en ligne.

1. Onglet **Profils**, sélectionner `meross.mrs100`.
2. L’éditeur contient le profil effectif. Ajouter ce bloc à la fin de la liste
   `entities:` (conserver toutes les entités existantes) :

```yaml
- key: movement
  platform: sensor
  channel: 0
  name: "Movement"
  entity_category: diagnostic
  state:
    namespace: Appliance.RollerShutter.State
    channel: $channel
    fields:
      value: "state[0].state"
```

3. Facultatif : remplacer le bloc `Appliance.RollerShutter.State` existant
   pour déclarer les champs observés sur le terrain :

```yaml
Appliance.RollerShutter.State:
  methods: [GETACK, PUSH]
  fields:
    channel: { type: integer }
    state:
      type: integer
      values: { 0: stop, 1: open, 2: close }
    timestamp: { type: integer }
    stoppedBy: { type: integer }
```

4. **Validate** : le résultat doit être sans erreur ; le diff ne doit montrer
   que l’ajout.
5. **Apply override** : confirmation, sauvegarde préalable et verrou de hash.
6. Le catalogue est rechargé. L’intégration vérifie la révision toutes les
   60 s ; sinon, redémarrer l’intégration.

## 4. Vérifier

**Dans le tuning**

- Onglet **Appareils** : l’entité attendue `Movement` apparaît.
- **Simulate a frame** : namespace `Appliance.RollerShutter.State`, méthode
  `PUSH`, payload ci-dessous. Les valeurs typées doivent afficher
  `movement = 1`.

```json
{ "state": [{ "channel": 0, "state": 1, "timestamp": 0 }] }
```

**Dans Home Assistant**

- Après le rechargement, un capteur diagnostic **Movement** apparaît.
- Une capture ou un mouvement réel doit le faire passer à `2` (fermeture),
  `0` (arrêt) puis `1` (ouverture).

Le capteur expose des **valeurs numériques brutes**. Une icône de volet
dynamique ou un libellé « ouverture/fermeture » nécessiteraient une évolution
de l’intégration (`is_opening` / `is_closing`), pas seulement un profil.

## 5. Revenir en arrière

- **Revert to bundled** supprime la surcharge après une sauvegarde.
- Les backups horodatés permettent aussi de restaurer une version antérieure.

Le catalogue livré n’est jamais modifié : la surcharge reste dans
`/data/device_profiles`. Une fois la méthode validée, la même entité pourra
être ajoutée au profil livré dans une version ultérieure du broker.

La version livrée du profil MRS100 utilise désormais ce signal directement sur
le cover, via une source `movement` sans entité visible ; cet exercice reste la
méthode générale pour ajouter d’autres fonctionnalités par surcharge.

## Pourquoi cela fonctionne sans code

Le moteur de profils partagé transforme une trame `namespace + méthode + canal + chemin` en valeurs d’entité. L’intégration consomme ensuite les entités
déclarées par le profil. Ajouter une entité est donc une opération de
configuration : aucune ligne de Python n’est nécessaire.
