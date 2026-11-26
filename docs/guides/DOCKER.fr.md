# Broker sous Home Assistant Container (Docker)

Ce guide couvre **Home Assistant Container** : Docker sans Supervisor, donc
sans magasin d'add-ons. Pour HA OS ou HA Supervised, utiliser l'add-on
(**Meross Local Broker**), qui reste le parcours recommandé.

## Prérequis

- Docker Engine avec le plugin `docker compose`, sur un hôte Linux.
- Ports **2001** (MQTT/TLS) et **2004** (HTTPS) libres ; **2003** pour
  l'administration locale.
- Home Assistant Container avec HACS, ou copie manuelle de
  `custom_components/meross_local_cloud`.
- Un appareil Meross et le pairer Android.

## Démarrage rapide

1. Copier le dossier `deploy/` du dépôt sur l'hôte Docker.
2. Lancer `./install.sh` : il crée `.env` et `./data`, démarre le conteneur et
   attend que le broker réponde.
3. Dans Home Assistant : **Paramètres → Appareils et services → Ajouter une
   intégration → Meross Local Cloud**, puis saisir l'adresse de l'hôte, le
   compte local et le mot de passe. Les ports **2004** et **2001** sont ceux du
   broker (préremplis à partir de l'intégration 4.0.4).
4. Appairer l'appareil avec le pairer en utilisant l'adresse de l'hôte Docker.

## Valeurs à saisir

| Champ                | Valeur                           |
| -------------------- | -------------------------------- |
| Adresse du broker    | IP LAN de l'hôte Docker          |
| Port HTTPS           | `2004`                           |
| Port MQTT            | `2001`                           |
| Login / mot de passe | compte local créé dans le broker |

L'administration locale est sur `http://127.0.0.1:2003/`. À distance, utiliser
un tunnel : `ssh -L 2003:127.0.0.1:2003 <utilisateur>@<hôte>`.

## Configuration

Les variables de `deploy/.env` sont lues par `docker-compose.yml` :

| Variable              | Défaut       | Rôle                                        |
| --------------------- | ------------ | ------------------------------------------- |
| `MEROSS_STANDALONE`   | `1`          | force le mode sans Supervisor               |
| `ADVERTISE`           | `false`      | annonce mDNS (avancé)                       |
| `DEBUG_MODE`          | `false`      | journaux détaillés                          |
| `DEVICE_TIMEZONE`     | vide         | fuseau des appareils                        |
| `MQTT_INTEGRITY_MODE` | `observe`    | `observe` ou `enforce`                      |
| `ADMIN_BIND`          | `127.0.0.1`  | interface de l'admin                        |
| `ADMIN_PORT`          | `2003`       | port de l'admin                             |
| `ADMIN_ALLOW_CIDR`    | `127.0.0.1`  | CIDR autorisé sur l'admin                   |
| `TLS_SAN_AUTO`        | `1`          | ajoute les IPv4 de l'hôte aux SAN           |
| `TLS_SAN_EXTRA`       | IP de l'hôte | IP/DNS supplémentaires, séparés par virgule |

Un fichier `/data/options.json` est également accepté : il est prioritaire sur
les variables d'environnement. `install.sh` n'en crée pas.

## Réseau

Le compose fourni utilise `network_mode: host` : le broker prend l'adresse LAN
de l'hôte, les appareils et le pairer le joignent directement, et l'admin reste
sur la boucle locale. En mode bridge, publier explicitement `2001` et `2004`,
puis `2003` uniquement si nécessaire ; l'admin n'a pas d'authentification
propre, ne jamais l'exposer au LAN sans protection.

mDNS est désactivé par défaut : la découverte automatique de l'intégration ne
fonctionne pas en conteneur standard. La configuration manuelle ci-dessus est
la voie normale. Pour l'activer, utiliser `network_mode: host` et monter le
socket D-Bus de l'hôte, puis `ADVERTISE=true`.

## TLS et certificats

Le broker génère sa CA et son certificat au premier démarrage dans
`/data/mqtt/certs`. L'intégration télécharge `/ca.crt` et l'épingle ; le pairer
fait de même. Si l'IP de l'hôte change, mettre à jour `TLS_SAN_EXTRA` ou
`TLS_SAN_AUTO`, puis réinitialiser le certificat épinglé côté clients.

## Données et mise à jour

Le volume `./data` contient la base, les certificats, la clé de signature des
profils, les surcharges et les captures. Sauvegarde = copie du volume.

Mise à jour : `docker compose pull && docker compose up -d`. Épingler une
version précise dans `BROKER_IMAGE` pour éviter les surprises.

## Dépannage

| Problème                        | Vérifier                                                   |
| ------------------------------- | ---------------------------------------------------------- |
| Le conteneur redémarre          | `docker logs meross-local-broker`, architecture de l'image |
| Intégration : certificat refusé | URL `https://<ip>:2004/ca.crt`, SAN, pin réinitialisé      |
| Admin inaccessible              | `ADMIN_BIND`, tunnel SSH, pare-feu                         |
| Appareil non appairé            | IP de l'hôte, ports 2001/2004, `docker compose ps`         |
| mDNS absent                     | normal en bridge ; configurer manuellement                 |

## Tests

- `tools/test_standalone_docker.sh` : smoke test du conteneur autonome
  (HTTPS, admin, MQTT/TLS), exécuté par la CI.
- `tests/docker/run.sh` : test de bout en bout avec une instance Home
  Assistant Container réelle (compte local, flux de configuration, entrée
  chargée, événements broker).

Outils, variables et comptes de test : [tests/docker/README.md](../../tests/docker/README.md).

## Sécurité

- L'admin n'a pas d'authentification : laisser `ADMIN_BIND=127.0.0.1` ou
  placer un reverse proxy authentifié devant.
- Ne pas publier le port 2003 sur Internet.
- Le compte local du broker est indépendant du compte Meross officiel.
