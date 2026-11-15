# Meross Local Broker

Cet add-on remplace le cloud Meross par un broker local (MQTT + API HTTP) pour
Home Assistant. Il est prévu pour être utilisé avec :

- [Meross Local Pairer](https://github.com/mazkagaz/meross-local-pairer) pour appairer
  un appareil Meross ;
- [Meross Cloud IoT](https://github.com/mazkagaz/meross-cloud) pour créer les
  entités Home Assistant.

## Démarrage

1. Démarrer l'add-on.
2. Ouvrir son panneau et créer un **compte local** (login et mot de passe).
3. Ce compte est strictement local : aucun identifiant cloud Meross n’est utilisé.
4. Appairer l'appareil avec Meross Local Pairer.
5. Ajouter l'intégration Home Assistant en mode **LAN-only broker**.

L'add-on expose :

- **2001/tcp** : broker MQTT (TLS) ;
- **2003/tcp** : API HTTP et panneau web ;
- **10001/tcp** : débogage distant.

## Option `device_timezone`

Fuseau horaire IANA (par exemple `Europe/Paris`) envoyé aux appareils avec les
règles d'heure d'été, comme le fait le cloud Meross. Laisser vide pour utiliser
le fuseau de Home Assistant.

Sans fuseau, certains appareils de mesure (prises mss310, mss210p, etc.) ne
remontent ni tension, ni courant, ni consommation.

## Vérifications rapides

- Appareil connecté : `curl http://homeassistant.local:2003/_admin_/devices`.
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
