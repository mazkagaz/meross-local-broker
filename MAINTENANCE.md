# Maintenance — Meross Local Broker

Dernière revue : **2026-11-27**

## Politique de support

- **Runtime** : image Debian bookworm / Python 3.11.
- **Tests** : Python 3.13 dans la CI.
- **Profil moteur** : synchronisé avec l’intégration et épinglé dans
  `profile_engine/UPSTREAM.md`.
- **Contrats croisés** : les pins CI intégration/broker doivent être mis à jour
  à chaque release de l’autre dépôt.
- **Dépendances natives** : Mosquitto, libwebsockets, mosquitto-go-auth et Go
  sont épinglés et font l’objet d’une revue trimestrielle EOL.

## Rythme

| Fréquence    | Action                                                                        |
| ------------ | ----------------------------------------------------------------------------- |
| Chaque PR    | tests broker, lint des profils, parité moteur, traductions, couverture ≥ 70 % |
| Hebdomadaire | audit des dépendances Python et npm                                           |
| Mensuel      | revue des PR Dependabot                                                       |
| Trimestriel  | revue Python/native, versions EOL, image de base                              |
| Annuel       | revue d’architecture et de sécurité                                           |

## Automatisations

- `Dependabot` : GitHub Actions, dépendances Python du broker et Web UI.
- `security.yaml` : `pip-audit` sur les dépendances de test et `npm audit`
  sur la Web UI.
- `profile_lint.py` et `sync_profile_engine.py --check` dans la CI.
- `tests/supervisor` et `tests/docker` pour les parcours réels.

## Checklist de release

- [ ] La CI et le Builder sont verts sur `main`.
- [ ] `config.yaml` et `RELEASE_NOTES.md` portent la même version.
- [ ] `meross_local_broker/CHANGELOG.md` contient l’entrée de version.
- [ ] Le README EN/FR et `docs/translations.json` sont à jour.
- [ ] `sync_profile_engine.py --check` passe contre l’intégration publiée.
- [ ] L’image multi-arch est construite et testée.
- [ ] La release GitHub est créée après le tag.
- [ ] Aucun bump de version n’est poussé avant le commit final de release.

## Règles de conception

- Aucune modification du moteur partagé dans ce dépôt : modifier l’intégration,
  puis synchroniser.
- Un nouveau profil doit avoir un test golden frame et, si possible, un test
  fonctionnel côté intégration.
- Les montées de dépendances natives sont des PR dédiées, avec image de secours
  et validation Supervisor/Docker.
- Une dépendance EOL doit être remplacée ou documentée dans `MAINTENANCE.md`.
