# Test Docker de bout en bout

Environnement jetable : broker en mode autonome + Home Assistant Container,
avec ajout réel de l'entrée `meross_local_cloud` par le flux de configuration.

## Prérequis

- Accès à Docker.
- `curl`.
- Un Python avec `aiohttp` : `HA_PYTHON=/chemin/vers/python`.

## Lancer

```bash
CLOUD_ROOT=/chemin/vers/meross-cloud \
HA_PYTHON=/chemin/vers/python \
bash tests/docker/run.sh
```

Le script :

1. démarre l'image broker publiée avec les scripts standalone du dépôt montés
   en superposition ;
2. crée le compte local via `/_admin_/configuration` ;
3. démarre HA `stable` dans le namespace réseau du broker ;
4. onboarde HA, ajoute l'intégration, vérifie que l'entrée est `loaded` ;
5. vérifie dans les événements broker le login « Meross Local API ».

HA partage le namespace réseau du broker (`--network container:`) : il joint
donc `127.0.0.1:2004` et le test ne dépend pas du forwarding bridge de l'hôte.

## Limites

- Aucun appareil Meross : le test valide le login, le catalogue et le
  démarrage de l'intégration, pas l'appairage.
- L'image broker utilisée porte les correctifs runtime du dépôt ; l'image
  elle-même est reconstruite par la CI.
