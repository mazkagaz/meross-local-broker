# Meross Local Broker

Cet add-on remplace le cloud Meross par un broker local (MQTT/TLS + API
HTTP/HTTPS) pour Home Assistant. HTTPS est activé par défaut. Il est prévu pour
être utilisé avec :

- [Meross Local Pairer](https://github.com/mazkagaz/meross-local-pairer) pour appairer
  un appareil Meross ;
- [Meross Local Cloud](https://github.com/mazkagaz/meross-local-cloud) pour créer les
  entités Home Assistant.

Le broker vise tous les appareils Meross qui acceptent un broker local. Le
**MRS100** (volet roulant) est la cible principalement testée ; les autres
modèles doivent continuer à fonctionner comme avec le broker d'origine.
Merci de signaler vos tests en précisant le modèle, le firmware et les
fonctions disponibles : ouvrez une issue sur le dépôt du broker. Les demandes
d'intégration spécifique sont bienvenues.

## Démarrage

1. Démarrer l'add-on.
2. Ouvrir son panneau et créer un **compte local** (login et mot de passe).
3. Ce compte est strictement local : aucun identifiant cloud Meross n’est utilisé.
4. Appairer l'appareil avec Meross Local Pairer.
5. Ajouter l'intégration Home Assistant et la configurer avec le compte local.
   Elle ne fonctionne qu'avec ce broker local ; aucun mode cloud n'est proposé.

L'add-on expose :

- **2001/tcp** : broker MQTT (TLS, toujours actif) ;
- **2003/tcp** : API HTTP et panneau web (ingress Home Assistant) ;
- **2004/tcp** : API HTTPS (TLS, activée par défaut).

Meross Local Pairer utilise **HTTPS sur 2004** par défaut. Le port **2003**
reste utile pour l'ingress et les clients qui ne peuvent pas valider le
certificat local.

L'API d'administration du panneau web n'est accessible qu'à travers l'ingress
Home Assistant, avec l'identité de l'utilisateur HA. Aucun port de débogage
n'est publié : en `debug_mode`, debugpy écoute uniquement sur `127.0.0.1`
dans le conteneur.

## Options

- **`enable_https`** (activé par défaut) : active le listener HTTPS 2004,
  partagé avec le certificat MQTT. Le désactiver ne touche ni MQTT/TLS sur
  2001 ni HTTP sur 2003.
- **`advertise`** : publie le broker et les ports API via mDNS.
- **`reinit_db`** : efface le compte local et les appareils appairés au
  démarrage (dépannage uniquement).
- **`device_timezone`** : fuseau IANA poussé aux appareils (voir ci-dessous).
- **`debug_mode`** : journaux détaillés.
- **`mqtt_integrity_mode`** : `observe` (défaut) journalise les signatures,
  horodatages ou rejeux invalides des appareils ; `enforce` les rejette.
  Laisser `observe` au moins une version avant d'activer `enforce`.

Chaque appareil MQTT est limité à ses propres topics
(`/appliance/<uuid>/publish` et `/appliance/<uuid>/subscribe`) ; un compte
applicatif ne peut publier que vers les appareils qu'il possède.

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
- Journal de l'add-on : recherche de `ONLINE`. Pour un MRS100, les messages
  `Stored roller-shutter config` / `Re-applied roller-shutter config` confirment
  la persistance des durées.
- Le broker MQTT doit être joignable sur le port 2001.

## Dépannage

| Problème                  | Vérifier                                                            |
| ------------------------- | ------------------------------------------------------------------- |
| L'appareil n'apparaît pas | appairage effectué, Wi-Fi 2,4 GHz WPA2, port 2001                   |
| Authentification refusée  | identifiants du compte local, `UserId`/`mqttKey`                    |
| Entités absentes dans HA  | intégration configurée avec le compte local, certificat MQTT ignoré |
| Consommation à zéro       | `device_timezone` renseigné ou fuseau HA correct                    |
| Durées MRS100 perdues     | logs `Stored` / `Re-applied`, reconnexion de l'appareil             |

## Licence

Fork non officiel, Apache-2.0. Voir `NOTICE`, `MODIFICATIONS.md` et `LEGAL.md`.
