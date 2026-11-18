# Meross Local Broker — add-on Home Assistant

![Meross Local Broker](meross_local_broker/logo.png)

Add-on **non officiel** qui remplace le cloud Meross par un broker local pour
Home Assistant. Il permet de contrôler les appareils Meross sur le réseau local,
sans dépendre du cloud pour l'usage quotidien.

![aarch64](https://img.shields.io/badge/aarch64-yes-green.svg)
![amd64](https://img.shields.io/badge/amd64-yes-green.svg)

## Les trois briques du montage

| Brique                  | Rôle                              | Dépôt                                                                           |
| ----------------------- | --------------------------------- | ------------------------------------------------------------------------------- |
| **Meross Local Broker** | add-on : broker MQTT + API locale | [mazkagaz/meross-local-broker](https://github.com/mazkagaz/meross-local-broker) |
| **Meross Local Cloud**  | intégration Home Assistant (HACS) | [mazkagaz/meross-local-cloud](https://github.com/mazkagaz/meross-local-cloud)   |
| **Meross Local Pairer** | application Android d'appairage   | [mazkagaz/meross-local-pairer](https://github.com/mazkagaz/meross-local-pairer) |

```
Appareil Meross ──MQTT/TLS──> add-on Meross Local Broker ──API/MQTT──> intégration HA
                                      ^
                                      │ appairage initial
                             Meross Local Pairer (Android)
```

## Compatibilité

Le broker fonctionne avec les appareils Meross qui acceptent un broker local.
Le **MRS100** (volet roulant) est la cible principalement testée, mais les
autres modèles doivent continuer à fonctionner comme avec le broker d'origine,
et parfois mieux. Les retours de test sont précieux : ouvrez une
[issue](https://github.com/mazkagaz/meross-local-broker/issues) en précisant le
modèle, le firmware et les fonctions qui marchent ou non. Les demandes
d'intégration spécifique sont bienvenues.

## Ports

| Port         | Usage                                     | Actif par défaut        |
| ------------ | ----------------------------------------- | ----------------------- |
| **2001/tcp** | MQTT/TLS (appareils)                      | oui                     |
| **2003/tcp** | API HTTP **ingress Supervisor seulement** | oui                     |
| **2004/tcp** | API HTTPS (TLS)                           | oui, via `enable_https` |

Le port **2003** n'est plus accessible depuis le LAN : il sert uniquement à
l'**ingress Home Assistant** (panneau web et administration via le Supervisor).
Les clients LAN (intégration HA, pairer) utilisent exclusivement **HTTPS 2004**.

L'API d'administration (renommage/suppression depuis le panneau web, services,
journaux) n'est accessible qu'à travers l'**ingress Home Assistant**, avec
l'identité de l'utilisateur HA. Aucun port de débogage n'est publié : en
`debug_mode`, debugpy écoute uniquement sur `127.0.0.1` dans le conteneur.

## Avant de commencer

- Home Assistant OS ou Supervised (l'add-on a besoin du Supervisor).
- HACS installé, pour l'intégration Home Assistant.
- Un appareil Meross à appairer et un Wi-Fi **2,4 GHz en WPA2**.
- Un téléphone Android pour Meross Local Pairer.
- Installations **amd64** ou **aarch64** uniquement (les architectures 32 bits
  ne sont plus construites).

## Installation complète

### 1. Installer l'add-on

Dans Home Assistant :

1. **Paramètres → Modules complémentaires → Boutique de modules**.
2. Menu **⋮ → Dépôts**.
3. Ajouter `https://github.com/mazkagaz/meross-local-broker`.
4. Installer **Meross Local Broker**, puis démarrer.

Le bouton ci-dessous ouvre directement la boîte de dialogue :

[![Ouvrir mon Home Assistant](https://my.home-assistant.io/badges/supervisor_add_addon_repository.svg)](https://my.home-assistant.io/redirect/supervisor_add_addon_repository/?repository_url=https%3A%2F%2Fgithub.com%2Fmazkagaz%2Fmeross-local-broker)

### 2. Créer le compte local du broker

1. Ouvrir le panneau **Meross Local Broker** de l'add-on.
2. Créer un compte local, par exemple `meross-local`, avec un mot de passe.
3. Aucun identifiant cloud Meross n’est demandé : ce compte reste local.
4. Valider. L'add-on redémarre ses services.

Ce compte sert uniquement au broker local. Ce n'est pas votre compte Meross
cloud.

En cas de besoin, la même opération peut être faite en ligne de commande
(remplacer l'adresse et le mot de passe) :

```bash
curl -sk -X PUT https://homeassistant.local:2004/_admin_/configuration \
  -H 'Content-Type: application/json' \
  -d '{"email":"meross-local","password":"MotDePasseLocal"}'
```

La réponse contient `userId` et `mqttKey`. Le `userId` vaut normalement `1`.

### 3. Appairer un appareil Meross

Suivre la procédure de
[Meross Local Pairer](https://github.com/mazkagaz/meross-local-pairer#appairage-pas-à-pas).
L'application configure l'appareil pour qu'il se connecte à cet add-on.

- **Sans Bluetooth LE** : appairage par l'AP Wi-Fi `Meross_*` de l'appareil.
- **Avec Bluetooth LE** (publicité `MRBL_…`, notamment les MRS100 récents) :
  utiliser l'appairage Bluetooth LE de Meross Local Pairer.

Une fois l'appairage terminé :

- l'add-on doit journaliser la connexion de l'appareil et son passage **ONLINE** ;
- la page **Paired devices** du panneau web doit afficher l'appareil.

### 4. Installer l'intégration Home Assistant

Suivre la procédure de
[Meross Local Cloud](https://github.com/mazkagaz/meross-local-cloud#installation-avec-hacs).
L'intégration s'installe avec **HACS**, puis se configure avec le compte local
du broker.

Champs usuels :

| Champ             | Valeur                                           |
| ----------------- | ------------------------------------------------ |
| HTTP API Endpoint | `https://homeassistant.local:2004` (obligatoire) |
| MQTT Address      | `homeassistant.local:2001`                       |
| Local login       | le compte local, par exemple `meross-local`      |
| Password          | le mot de passe local                            |

Le broker doit être en **alpha99 ou plus récent** : l'intégration récupère et
épingle sa CA (`/ca.crt`). Les options « ignorer la validation » n'existent plus.

Si `homeassistant.local` ne répond pas, utiliser l'adresse IP de Home Assistant.

### TLS

Le listener MQTT **2001** et le listener HTTPS **2004** partagent la même
autorité de certification locale (`/data/mqtt/certs`). Cette CA est valide
(`CA:TRUE`) et le certificat serveur contient les IP LAN. Le port **2003** est
en HTTP simple mais **réservé à l'ingress du Supervisor** ; le LAN passe par
HTTPS 2004.

L'option **`enable_https`** (activée par défaut) contrôle le listener 2004.
La désactiver laisse MQTT/TLS sur 2001 et l'ingress sur 2003, mais **aucun
client LAN ne peut plus se connecter** (intégration et pairer exigent HTTPS).

Les publications des appareils sont contrôlées (signature, fraîcheur,
anti-rejeu) et chaque appareil ne peut utiliser que ses propres topics.
L'option **`mqtt_integrity_mode`** vaut `observe` par défaut (écarts
journalisés) ; passer à `enforce` après une période de vérification.

Le certificat du serveur est auto-signé. Deux options :

- **valider le certificat** : récupérer la CA sur
  `https://homeassistant.local:2004/ca.crt`, comparer son empreinte avec
  celle du fichier `/data/mqtt/certs/ca.crt`, puis l'importer côté client.
  Depuis **alpha99**, la CA est valide (`CA:TRUE`) et le certificat serveur
  contient les adresses IPv4 LAN : l'intégration et le pairer vérifient la
  chaîne. Les options « ignorer la validation » ont été supprimées.

### 5. Vérifier

Dans Home Assistant, l'appareil doit apparaître avec les entités
correspondant à son type (prise, éclairage, volet, etc.).

Pour un **MRS100**, l'intégration crée en plus :

- une entité `cover` pour le volet ;
- deux entités `number` pour les durées d'ouverture/fermeture ;
- deux boutons de calibration ;
- un capteur **Calibration status**.

## Utilisation

Les appareils se pilotent avec leurs entités Home Assistant habituelles. Pour
le **MRS100** :

- **Ouvrir/fermer** : entité `cover`.
- **Durées** : entités `number` (10 à 120 secondes). Les valeurs sont
  persistées par l'add-on et réappliquées après reconnexion.
- **Calibration** : bouton **Start calibration**, puis suivi dans
  **Calibration status** (`in_progress`, `success`, `timeout`,
  `motor_blocked`, `failed_N`). **Stop calibration** interrompt le mouvement.

## Oublier un appareil

**Forget device** (Web UI de l'add-on ou application d'appairage) supprime
l'appareil et **révoque son MAC** : l'appareil garde ses identifiants MQTT, mais
le broker refuse désormais sa connexion, donc il ne peut pas revenir tout seul.

Un nouvel appairage réussi appelle `POST /v1/Device/claim` pour lever la
révocation. L'appareil conserve le même UUID : dans Home Assistant, ses entités
et les automatisations existantes restent valides après un cycle
oubli/réappairage.

## Réglage `device_timezone`

L'option `device_timezone` pousse le fuseau et les règles d'heure d'été aux
appareils. Laisser vide pour utiliser le fuseau de Home Assistant.

## Dépannage

| Problème                            | Vérifier                                                                 |
| ----------------------------------- | ------------------------------------------------------------------------ |
| L'add-on ne démarre pas             | architecture amd64/aarch64, logs du Supervisor, image GHCR publique      |
| Aucun appareil dans l'add-on        | appairage Wi-Fi AP ou Bluetooth LE, port MQTT 2001, Wi-Fi 2,4 GHz WPA2   |
| L'intégration ne voit pas le broker | adresse HTTPS 2004, compte local, broker alpha99+                        |
| Entités absentes                    | appareil ONLINE dans l'add-on, puis redémarrer l'intégration             |
| Durées non conservées               | logs `Stored roller-shutter config` / `Re-applied roller-shutter config` |
| Appareil déjà lié au cloud Meross   | réinitialiser l'appareil avant l'appairage local                         |

## Documentation technique

- [MRS100.md](MRS100.md) — détails du support MRS100.
- [TESTING.md](TESTING.md) — tests unitaires et checklist matérielle.
- [BUILDING.md](BUILDING.md) — construction de l'image et publication.

## Origine et licence

Fork non officiel de
[albertogeniola/ha-meross-local-broker](https://github.com/albertogeniola/ha-meross-local-broker),
sous **Apache License 2.0**. Le texte de licence et l'attribution upstream sont
conservés dans `LICENSE`, `NOTICE`, `MODIFICATIONS.md` et `LEGAL.md`.

Ce fork n'est ni affilié, ni approuvé, ni sponsorisé par Meross ou l'auteur
upstream. Meross est une marque de son propriétaire respectif.
