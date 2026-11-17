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
MRS100 ──MQTT/TLS──> add-on Meross Local Broker ──API/MQTT──> intégration HA
                            ^
                            │ appairage initial
                       Meross Local Pairer (Android)
```

## Ports

| Port          | Usage                            | Actif par défaut           |
| ------------- | -------------------------------- | -------------------------- |
| **2001/tcp**  | MQTT/TLS (appareils)             | oui                        |
| **2003/tcp**  | API HTTP, ingress et panneau web | oui                        |
| **2004/tcp**  | API HTTPS (TLS)                  | oui, via `enable_https`    |
| **10001/tcp** | débogage distant                 | uniquement en `debug_mode` |

Meross Local Pairer privilégie **HTTPS 2004**. HTTP 2003 reste disponible pour
l'ingress et les clients existants.

## Avant de commencer

- Home Assistant OS ou Supervised (l'add-on a besoin du Supervisor).
- HACS installé, pour l'intégration Home Assistant.
- Un MRS100 et un Wi-Fi **2,4 GHz en WPA2**.
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
curl -s -X PUT http://homeassistant.local:2003/_admin_/configuration \
  -H 'Content-Type: application/json' \
  -d '{"email":"meross-local","password":"MotDePasseLocal"}'
```

La réponse contient `userId` et `mqttKey`. Le `userId` vaut normalement `1`.

### 3. Appairer le MRS100

Suivre la procédure de
[Meross Local Pairer](https://github.com/mazkagaz/meross-local-pairer#appairage-pas-à-pas).
L'application configure le MRS100 pour qu'il se connecte à cet add-on.

- **Firmware 7** : appairage par l'AP Wi-Fi `Meross_RS_*`.
- **Firmware 8** : l'AP Wi-Fi n'est pas ouvert ; utiliser l'appairage
  **Bluetooth LE** de Meross Local Pairer (`MRBL_…`).

Une fois l'appairage terminé :

- l'add-on doit journaliser la connexion du MRS100 et son passage **ONLINE** ;
- la page **Paired devices** du panneau web doit afficher l'appareil.

### 4. Installer l'intégration Home Assistant

Suivre la procédure de
[Meross Local Cloud](https://github.com/mazkagaz/meross-local-cloud#installation-avec-hacs).
L'intégration s'installe avec **HACS**, puis se configure avec le compte local
du broker.

Champs usuels :

| Champ                            | Valeur                                                                           |
| -------------------------------- | -------------------------------------------------------------------------------- |
| HTTP API Endpoint                | `https://homeassistant.local:2004` (défaut) ou `http://homeassistant.local:2003` |
| MQTT Address                     | `homeassistant.local:2001`                                                       |
| Local login                      | le compte local, par exemple `meross-local`                                      |
| Password                         | le mot de passe local                                                            |
| Skip MQTT certificate validation | coché                                                                            |
| Skip HTTP certificate validation | coché avec `https://` et le certificat local                                     |

Si `homeassistant.local` ne répond pas, utiliser l'adresse IP de Home Assistant.

### TLS

Le listener MQTT **2001** et le listener HTTPS **2004** partagent la même
autorité de certification locale (`/data/mqtt/certs`). Le port **2003** reste
en HTTP simple pour l'ingress Home Assistant et les anciens clients.

L'option **`enable_https`** (activée par défaut) contrôle le listener 2004 :
la désactiver ne touche ni MQTT/TLS sur 2001, ni HTTP sur 2003.

Le certificat du serveur est auto-signé. Deux options :

- **valider le certificat** : récupérer la CA sur
  `http://homeassistant.local:2003/ca.crt` (ou
  `https://homeassistant.local:2004/ca.crt`), comparer son empreinte avec
  celle du fichier `/data/mqtt/certs/ca.crt`, puis l'importer côté client.
  Les certificats générés depuis `alpha71` contiennent
  `homeassistant.local`, `localhost` et `127.0.0.1` ; avec une autre adresse,
  désactiver la validation ou régénérer les certificats en supprimant
  `/data/mqtt/certs`.
- **ignorer la validation** : cocher les options « Skip … certificate
  validation » de l'intégration. Le trafic reste chiffré, mais le pairer
  épingle le certificat au premier usage.

### 5. Vérifier

Dans Home Assistant, l'appareil doit apparaître avec :

- une entité `cover` pour le volet ;
- deux entités `number` pour les durées d'ouverture/fermeture ;
- deux boutons de calibration ;
- un capteur **Calibration status**.

## Utilisation

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
révocation. L'appareil conserve le même UUID : dans Home Assistant, l'entité
`cover`, les entités `number` et les automatisations existantes restent valides
après un cycle oubli/réappairage.

## Réglage `device_timezone`

L'option `device_timezone` pousse le fuseau et les règles d'heure d'été aux
appareils. Laisser vide pour utiliser le fuseau de Home Assistant.

## Dépannage

| Problème                            | Vérifier                                                                     |
| ----------------------------------- | ---------------------------------------------------------------------------- |
| L'add-on ne démarre pas             | architecture amd64/aarch64, logs du Supervisor, image GHCR publique          |
| Aucun appareil dans l'add-on        | appairage Wi-Fi (FW7) ou Bluetooth (FW8), port MQTT 2001, Wi-Fi 2,4 GHz WPA2 |
| L'intégration ne voit pas le broker | adresse HTTPS 2004 (ou HTTP 2003), compte local, certificat MQTT ignoré      |
| Entités absentes                    | appareil ONLINE dans l'add-on, puis redémarrer l'intégration                 |
| Durées non conservées               | logs `Stored roller-shutter config` / `Re-applied roller-shutter config`     |
| Appareil déjà lié au cloud Meross   | réinitialiser l'appareil avant l'appairage local                             |

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
