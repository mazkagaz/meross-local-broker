# Tests fonctionnels — broker, intégration, pairer

Les tests unitaires vérifient des fonctions ; les tests d’intégration
vérifient des collaborations. Ce document décrit les **tests fonctionnels** :
des scénarios d’utilisation avec préconditions, actions et résultats
observables, sur un harnais déterministe ou du matériel réel.

## Harnais

| Harnais        | Composition                                                                       | Emplacement / mode                         |
| -------------- | --------------------------------------------------------------------------------- | ------------------------------------------ |
| H1 Broker      | Flask test client, DB temporaire, catalogue réel, appareil simulé                 | `meross_local_broker/.../test_*.py`, CI    |
| H2 Intégration | pytest-homeassistant, composants réels, transport MQTT simulé, API broker simulée | `meross-local-cloud/tests/functional/`, CI |
| H3 Banc        | broker réel + HA + appareil physique                                              | manuel/semi-auto, checklist ci-dessous     |
| H4 Pairer      | Android + broker réel + appareil                                                  | manuel                                     |

Chaque scénario note son harnais : **Auto** (CI), **Semi** (banc + script),
**Manuel** (matériel).

## Format d’un scénario

- **Étant donné** : état initial, options, appareils.
- **Quand** : action (UI, service, trame MQTT, API).
- **Alors** : résultat observable (état HA, registre, diagnostics, fichiers,
  logs, réponses API).
- **Nettoyage** : rollback, redémarrage, suppression de session.

## F1 — Installation et configuration (H2)

| ID   | Scénario                                     | Attendu                                                                   | Mode |
| ---- | -------------------------------------------- | ------------------------------------------------------------------------- | ---- |
| F1.1 | Installation neuve, broker découvert en mDNS | Formulaire prérempli, entrée créée, entités après probe                   | Semi |
| F1.2 | Saisie manuelle host/ports                   | Entrée créée avec ces valeurs, TLS vérifié                                | Semi |
| F1.3 | Mauvais mot de passe                         | Erreur « invalid_credentials », aucune entrée                             | Auto |
| F1.4 | Broker injoignable ou TLS invalide           | Erreur explicite, pas de boucle de retry                                  | Auto |
| F1.5 | CA changée                                   | Nouvelle CA acceptée selon la politique, avertissement visible            | Semi |
| F1.6 | Token expiré                                 | `ConfigEntryAuthFailed`, réauthentification, reprise sans perte d’entités | Auto |
| F1.7 | Changement d’options                         | Entrée rechargée, comportement appliqué                                   | Auto |
| F1.8 | Deuxième instance                            | Refus `single_instance_allowed`                                           | Auto |

## F2 — Bascule D5 (`profile_entities_only`)

| ID   | Étant donné / Quand                                                | Alors                                                                                           | Harnais      |
| ---- | ------------------------------------------------------------------ | ----------------------------------------------------------------------------------------------- | ------------ |
| F2.1 | Options backend + entités profils + seules activées ; rechargement | Seules les entités profils existent ; `unique_id` historiques conservés ; `entities_only: true` | H2 Auto      |
| F2.2 | Rollback : option seules désactivée ; rechargement                 | Entités historiques de retour avec les mêmes `unique_id` ; aucune suppression du registre       | H2 Auto + H3 |
| F2.3 | Appareil sans profil en mode seules                                | Aucune entité profil ; entités historiques conservées en repli ; appareil signalé non apparié   | H2 Auto      |
| F2.4 | Hub + sous-appareils                                               | Entités par sous-appareil, `via_device` correct, IDs stables                                    | H2 Auto      |
| F2.5 | Redémarrage HA                                                     | Entités restaurées, mêmes IDs, pas de résurrection des historiques                              | H2 Auto + H3 |

## F3 — Comportements par famille

| ID    | Scénario                        | Attendu                                           | Mode         |
| ----- | ------------------------------- | ------------------------------------------------- | ------------ |
| F3.1  | MRS100 ouvrir/fermer/stop       | Mouvement et états corrects, ACK appliqué         | H3           |
| F3.2  | MRS100 position 0/50/100        | Position et `is_closed` cohérents                 | H3           |
| F3.3  | Durées 10→60 s                  | SET, persistance, réapplication après reconnexion | H3           |
| F3.4  | Calibration start/stop          | `in_progress` → `success`/échec, stop interrompt  | H3           |
| F3.5  | Appareil hors ligne puis retour | `unavailable` puis états corrects, mêmes entités  | H3           |
| F3.6  | Prise/interrupteur              | État et commande, capteurs électricité            | H2 Auto + H3 |
| F3.7  | Éclairage                       | on/off, luminosité, RGB, conversion 0–255 ↔ 0–100 | H2 Auto + H3 |
| F3.8  | Thermostat                      | mode off/heat, consigne, températures normalisées | H2 Auto + H3 |
| F3.9  | Ventilateur / diffuseur         | pourcentage, diffusion on/off                     | H2 Auto + H3 |
| F3.10 | Hub MS100/MS130/MTS100          | temp/humidité/voltage, climate, commandes `$id`   | H2 Auto + H3 |

## F4 — Scheduler et polling (H2 Auto)

| ID   | Quand                    | Alors                                             |
| ---- | ------------------------ | ------------------------------------------------- |
| F4.1 | Démarrage                | Hydratation initiale, un minimum de requêtes      |
| F4.2 | Namespaces PUSH          | Aucun GET périodique ; états via PUSH             |
| F4.3 | Plusieurs namespaces dus | Un seul `Appliance.Control.Multiple`              |
| F4.4 | SET puis attente         | Rafraîchissement lazy, état final correct         |
| F4.5 | Démarrage à froid        | Plus de doublons `Config`/`System.All` par entité |
| F4.6 | Appareil bavard          | Rate limiting/backoff, pas de tempête             |

## F5 — Commandes et ACK (H2 Auto)

| ID   | Quand                                  | Alors                                        |
| ---- | -------------------------------------- | -------------------------------------------- |
| F5.1 | SET depuis une entité                  | ACK routé au demandeur, état mis à jour      |
| F5.2 | ACK sur topic utilisateur et topic app | Pas de double dispatch, compatibilité legacy |
| F5.3 | ACK perdu                              | Timeout isolé, entité réutilisable ensuite   |
| F5.4 | Commande hors ligne                    | Erreur propre, scheduler non bloqué          |

## F6 — Catalogue, surcharges, capture (H1 Auto + H2 Auto)

| ID   | Quand                    | Alors                                              |
| ---- | ------------------------ | -------------------------------------------------- |
| F6.1 | Surcharge valide déposée | Profil remplacé, diff `changed`, révision changée  |
| F6.2 | Surcharge invalide       | Ignorée, profil livré conservé, erreur signalée    |
| F6.3 | Révision changée         | Entrée HA rechargée < 60 s                         |
| F6.4 | Signature invalide       | Catalogue refusé, backend en erreur                |
| F6.5 | Catalogue non signé      | Accepté, `catalog_signature: absent`               |
| F6.6 | Capture puis brouillon   | Fichiers 0600, secrets absents, brouillon cohérent |
| F6.7 | Limites de capture       | Arrêt durée/taille/nombre, fichiers intègres       |

## F7 — Résilience et sécurité

| ID   | Quand                                         | Alors                                      | Mode    |
| ---- | --------------------------------------------- | ------------------------------------------ | ------- |
| F7.1 | Redémarrage broker                            | Reconnexion, états repris, pas de doublons | H2/H3   |
| F7.2 | Coupure MQTT                                  | Indisponibilité puis reprise               | H3      |
| F7.3 | Payload non-objet / géant / namespace inconnu | Ignoré ou erreur isolée, aucun crash       | H2 Auto |
| F7.4 | Trame d’un appareil étranger ou inconnu       | Rejet, aucun état injecté                  | H2 Auto |
| F7.5 | Rotation CA                                   | Échec explicite ou ré-épinglage contrôlé   | H3      |

## F8 — Pairer et cycle de vie (H4 / H3)

| ID   | Quand                  | Alors                                                    |
| ---- | ---------------------- | -------------------------------------------------------- |
| F8.1 | Appairage BLE/AP       | Appareil ONLINE, visible broker + HA                     |
| F8.2 | Oubli puis réappairage | Même UUID, entités et automatisations conservées         |
| F8.3 | Unbind                 | Entités supprimées, pas de fantômes                      |
| F8.4 | Appareil absent 48 h   | Réparation proposée ; retour avant = réparation disparue |

## Priorités

1. **P0 — avant suppression de `meross_iot`** : F2.1–F2.5, F3.1–F3.5,
   F4.1–F4.5, F5.1–F5.3, F7.1–F7.4.
2. **P1** : F1, F6, F3.6–F3.10.
3. **P2** : F8, F7.5.

Les P0 automatisables sont implémentés dans
`meross-local-cloud/tests/functional/` (bascule, scheduler/ACK, résilience
payload). Les scénarios matériels restent une checklist de banc.

## Checklist de banc (P0 matériel)

- [ ] MRS100 : ouvrir, fermer, stop, position 0/50/100, durées persistées et
      réappliquées après coupure d’alimentation, calibration start/stop.
- [ ] Couper le broker 2 min : HA `unavailable`, puis reprise sans doublons.
- [ ] Redémarrer HA : entités restaurées avec les mêmes IDs.
- [ ] Vérifier l’absence de `Appliance.RollerShutter.Config` en double au
      démarrage et de warnings `check_full_update_done`.
- [ ] Vérifier les diagnostics : `entities_only`, `catalog_signature`,
      `devices_matched`, `compile_errors`, compteurs scheduler.
