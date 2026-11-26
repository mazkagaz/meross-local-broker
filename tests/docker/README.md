# Test Docker de bout en bout

Environnement jetable : broker en mode autonome + Home Assistant Container,
avec ajout réel de l'entrée `meross_local_cloud` par le flux de configuration.

## Outils requis

- **Docker Engine** accessible à l'utilisateur courant (groupe `docker`), ou
  exécution via `sg docker -c '…'`.
- **curl** sur l'hôte.
- **Python 3.11+ avec `aiohttp`** pour le script de pilotage HA. Le venv de
  test de l'intégration convient :
  `HA_PYTHON=/chemin/meross/.ha-venv/bin/python`.
- Images : broker publié (`ghcr.io/mazkagaz/amd64-meross_local_broker:1.4.8`
  par défaut) et `ghcr.io/home-assistant/home-assistant:stable`.

## Variables

| Variable       | Défaut                  | Rôle                                             |
| -------------- | ----------------------- | ------------------------------------------------ |
| `CLOUD_ROOT`   | `../meross-cloud`       | dépôt de l'intégration (composant copié dans HA) |
| `HA_PYTHON`    | `python3`               | interpréteur avec `aiohttp`                      |
| `BROKER_IMAGE` | broker `1.4.8`          | image broker à tester                            |
| `HA_IMAGE`     | `home-assistant:stable` | image Home Assistant                             |

Les scripts standalone du dépôt sont montés en superposition sur l'image
broker : le test valide le code de la branche sans reconstruire l'image.

## Lancer

```bash
CLOUD_ROOT=/chemin/meross-cloud \
HA_PYTHON=/chemin/meross/.ha-venv/bin/python \
bash tests/docker/run.sh
```

Sous un hôte où Docker n'est pas dans le groupe courant :

```bash
sg docker -c "env CLOUD_ROOT=… HA_PYTHON=… bash tests/docker/run.sh"
```

## Ce que fait le script

1. Démarre le broker autonome avec les ports `2001`, `2003`, `2004` publiés sur
   la boucle locale, un volume `/data` temporaire et les scripts du dépôt.
2. Attend `/ca.crt`, puis crée le compte local via
   `PUT /_admin_/configuration`.
3. Démarre HA `stable` avec `default_config` et le composant copié dans
   `/config/custom_components/meross_local_cloud`.
4. Onboarde HA et ajoute l'intégration par le vrai flux HTTP :
   hôte `127.0.0.1`, ports `2004`/`2001`, compte local.
5. Vérifie que l'entrée est `loaded`, que les événements broker contiennent
   `logged in via Meross Local API`, et qu'aucun avertissement
   `Detected blocking call … meross_local_cloud` n'apparaît dans les logs HA.
6. Supprime conteneurs, réseau et volumes temporaires (y compris les fichiers
   créés par root via un conteneur jetable).

HA partage le namespace réseau du broker (`--network container:`) : il joint
donc `127.0.0.1:2004` et le test ne dépend pas du forwarding bridge de l'hôte.

## Comptes et valeurs de test

| Élément                        | Valeur                                               |
| ------------------------------ | ---------------------------------------------------- |
| Compte local broker            | `local-user` / `secret`                              |
| Compte HA (créé si nécessaire) | `e2e` / `e2e-pass-123`                               |
| Admin broker                   | `0.0.0.0:2003`, CIDR `172.16.0.0/12` (réseau Docker) |
| SAN TLS                        | `127.0.0.1`                                          |
| Entrée intégration             | hôte `127.0.0.1`, HTTPS 2004, MQTT 2001              |

Ces identifiants sont réservés aux tests et ne doivent pas être réutilisés.

## Limites

- Aucun appareil Meross : le test valide le login, le catalogue, le démarrage
  de l'intégration et l'absence de régression d'import, pas l'appairage.
- Le test suppose une image broker déjà construite ; la CI reconstruit l'image
  et exécute par ailleurs `tools/test_standalone_docker.sh`.

## Dépannage

| Symptôme                                 | Vérifier                                                            |
| ---------------------------------------- | ------------------------------------------------------------------- |
| `permission denied` sur le socket Docker | groupe `docker`, ou `sg docker -c`                                  |
| Port déjà utilisé                        | arrêter les conteneurs de test précédents                           |
| Image broker introuvable                 | architecture (`amd64`/`aarch64`), tag dans `BROKER_IMAGE`           |
| HA ne répond pas                         | `docker logs e2e-ha-t`, démarrage `default_config`                  |
| Le test échoue sur « blocking call »     | import du composant exécuté sur la boucle d'événements              |
| Nettoyage incomplet                      | relancer le script ; il supprime les fichiers root via un conteneur |
