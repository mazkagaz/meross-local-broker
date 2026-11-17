# Meross Local Broker

Cet add-on remplace le cloud Meross par un broker local (MQTT/TLS + API
HTTP/HTTPS) pour Home Assistant. HTTPS est activé par défaut. Il est prévu pour
être utilisé avec :

- [Meross Local Pairer](https://github.com/mazkagaz/meross-local-pairer) pour appairer
  un appareil Meross ;
- [Meross Local Cloud](https://github.com/mazkagaz/meross-local-cloud) pour créer les
  entités Home Assistant.

## Démarrage

1. Démarrer l'add-on.
2. Ouvrir son panneau et créer un **compte local** (login et mot de passe).
3. Ce compte est strictement local : aucun identifiant cloud Meross n’est utilisé.
4. Appairer l'appareil avec Meross Local Pairer.
5. Ajouter l'intégration Home Assistant en mode **LAN-only broker**.

L'add-on expose :

- **2001/tcp** : broker MQTT (TLS, toujours actif) ;
- **2003/tcp** : API HTTP et panneau web (ingress Home Assistant) ;
- **2004/tcp** : API HTTPS (TLS, activée par défaut) ;
- **10001/tcp** : débogage distant.

Meross Local Pairer utilise **HTTPS sur 2004** par défaut. Le port **2003**
reste utile pour l'ingress et les clients qui ne peuvent pas valider le
certificat local.

## Options

- **`enable_https`** (activé par défaut) : active le listener HTTPS 2004,
  partagé avec le certificat MQTT. Le désactiver ne touche ni MQTT/TLS sur
  2001 ni HTTP sur 2003.
- **`advertise`** : publie le broker et les ports API via mDNS.
- **`reinit_db`** : efface le compte local et les appareils appairés au
  démarrage (dépannage uniquement).
- **`device_timezone`** : fuseau IANA poussé aux appareils (voir ci-dessous).
- **`debug_mode`** : journaux détaillés.

## Option `device_timezone`

Fuseau horaire IANA (par exemple `Europe/Paris`) envoyé aux appareils avec les
règles d'heure d'été, comme le fait le cloud Meross. Laisser vide pour utiliser
le fuseau de Home Assistant.

Sans fuseau, certains appareils de mesure (prises mss310, mss210p, etc.) ne
remontent ni tension, ni courant, ni consommation.

## HTTPS et certificat

Les ports **2001** (MQTT/TLS) et **2004** (HTTPS) utilisent la même autorité de
certification locale, stockée dans `/data/mqtt/certs`. Le certificat serveur est
auto-signé et contient `homeassistant.local`, `localhost` et `127.0.0.1`.
Meross Local Pairer épingle le certificat au premier contact ; l'intégration
Home Assistant peut ignorer sa validation (option « Skip HTTP certificate
validation »). La CA est téléchargeable sur `http://homeassistant.local:2003/ca.crt`
ou `https://homeassistant.local:2004/ca.crt`.

## Vérifications rapides

- Appareil connecté : ouvrir **Paired devices** dans le panneau web, ou
  `curl -k https://homeassistant.local:2004/_admin_/devices` depuis le réseau
  autorisé.
- Journal de l'add-on : recherche de `ONLINE` et des messages
  `Stored roller-shutter config` / `Re-applied roller-shutter config`.
- Le broker MQTT doit être joignable sur le port 2001.

## Dépannage

| Problème                  | Vérifier                                                |
| ------------------------- | ------------------------------------------------------- |
| L'appareil n'apparaît pas | appairage effectué, Wi-Fi 2,4 GHz WPA2, port 2001       |
| Authentification refusée  | identifiants du compte local, `UserId`/`mqttKey`        |
| Entités absentes dans HA  | intégration en mode local, certificat MQTT ignoré       |
| Consommation à zéro       | `device_timezone` renseigné ou fuseau HA correct        |
| Durées perdues            | logs `Stored` / `Re-applied`, reconnexion de l'appareil |

## Licence

Fork non officiel, Apache-2.0. Voir `NOTICE`, `MODIFICATIONS.md` et `LEGAL.md`.
