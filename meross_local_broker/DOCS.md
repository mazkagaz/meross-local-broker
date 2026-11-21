# Meross Local Broker

Cet add-on remplace le cloud Meross par un broker local (MQTT/TLS + API
HTTP/HTTPS) pour Home Assistant. HTTPS est activé par défaut. Il est prévu pour
être utilisé avec :

- [Meross Local Pairer](https://github.com/mazkagaz/meross-local-pairer) pour appairer
  un appareil Meross ;
- [Meross Local Cloud](https://github.com/mazkagaz/meross-local-cloud) pour créer les
  entités Home Assistant.

Le broker vise tous les appareils Meross qui acceptent un broker local. Le
**MRS100** (volet roulant) sert de référence ; toutes les autres familles du
catalogue attendent des testeurs sur matériel réel. Merci de signaler vos
tests en précisant le modèle, le firmware et les fonctions disponibles :
ouvrez une issue sur le dépôt du broker. Les demandes d'intégration
spécifiques sont bienvenues.

## Démarrage

1. Démarrer l'add-on.
2. Ouvrir son panneau et créer un **compte local** (login et mot de passe).
3. Ce compte est strictement local : aucun identifiant cloud Meross n’est utilisé.
4. Appairer l'appareil avec Meross Local Pairer.
5. Ajouter l'intégration Home Assistant et la configurer avec le compte local.
   Elle ne fonctionne qu'avec ce broker local ; aucun mode cloud n'est proposé.

L'add-on expose :

- **2001/tcp** : broker MQTT (TLS, toujours actif) ;
- **2003/tcp** : API HTTP réservée à l'ingress Home Assistant (Supervisor), non accessible depuis le LAN ;
- **2004/tcp** : API HTTPS (TLS, toujours active).

Meross Local Pairer et l'intégration utilisent exclusivement **HTTPS 2004**.
Le port **2003** n'est plus accessible depuis le LAN : il n'est servi qu'à
l'ingress du Supervisor pour le panneau web et l'administration.

L'API d'administration du panneau web n'est accessible qu'à travers l'ingress
Home Assistant, avec l'identité de l'utilisateur HA. Aucun port de débogage
n'est publié : `debug_mode` ne fait qu'activer les journaux détaillés.

## Options

- **`advertise`** (`true`) : publie le broker MQTT et l'API **HTTPS** via mDNS.
  Laisser actif sauf si mDNS est indisponible sur le réseau.
- **`reinit_db`** (`false`) : efface le compte local et les appareils appairés
  au démarrage (dépannage uniquement).
- **`device_timezone`** (vide) : fuseau IANA poussé aux appareils (voir
  ci-dessous).
- **`debug_mode`** (`false`) : journaux détaillés (niveau `DEBUG`).
- **`mqtt_integrity_mode`** (`observe`) : contrôle de chaque publication
  d'appareil :

  - signature `md5(messageId + mqttKey + timestamp)` ;
  - horodatage à ±900 s ;
  - anti-rejeu par `device:messageId:signature`.

  `observe` journalise les écarts et laisse passer le message ; `enforce` le
  rejette. Laisser `observe` au moins une version avant d'activer `enforce`.

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
certification locale, stockée dans `/data/mqtt/certs`. Cette CA est valide
(`basicConstraints=CA:TRUE`) et peut être importée pour vérifier le broker.

Le certificat serveur contient `homeassistant.local`, `localhost`, `127.0.0.1`
et les adresses IPv4 LAN détectées. Il est re-signé automatiquement quand ces
adresses changent. Meross Local Pairer épingle le certificat au premier
contact : après une mise à jour du broker ou un changement d'adresse, le pin
peut devoir être réinitialisé dans les réglages de l'application.

La passphrase de la CA est aléatoire et stockée dans
`/data/mqtt/certs/ca.pass`. Les anciennes CA invalides (sans `CA:TRUE`) ou
proches de l'expiration sont régénérées automatiquement, avec une sauvegarde
dans `/data/mqtt/certs.bak-*`. La CA est téléchargeable sur
`https://homeassistant.local:2004/ca.crt`.

## Vérifications rapides

- Appareil connecté : ouvrir **Paired devices** dans le panneau web (accessible
  uniquement via l'ingress Home Assistant).
- Journal de l'add-on : recherche de `ONLINE`. Pour un MRS100, les messages
  `Stored roller-shutter config` / `Re-applied roller-shutter config` confirment
  la persistance des durées.
- Le broker MQTT doit être joignable sur le port 2001 et l'API HTTPS sur 2004
  depuis le LAN.

## Journaux

Cliquer sur l'une des quatre diodes du panneau ouvre la page **Journaux**, sur
l'onglet du service choisi. La flèche Retour ramène à l'accueil. La page offre
la recherche avec surlignage, le filtre par niveau, la copie des lignes
visibles, le téléchargement du journal complet, la pause/suivi et le retour à
la ligne. Seul l'onglet affiché interroge l'API.

## Oublier un appareil

**Forget device** révoque le MAC et publie `Appliance.Control.Unbind` vers
l'intégration Home Assistant, au plus tard 60 secondes après la suppression.
L'intégration supprime alors l'appareil et ses entités ; un appareil qui
disparaît sans Unbind est proposé à la suppression après 48 heures.

## Dépannage

| Problème                  | Vérifier                                                    |
| ------------------------- | ----------------------------------------------------------- |
| L'appareil n'apparaît pas | appairage effectué, Wi-Fi 2,4 GHz WPA2, port 2001           |
| Authentification refusée  | identifiants du compte local, `UserId`/`mqttKey`            |
| Entités absentes dans HA  | intégration configurée avec le compte local, broker 1.3.1+  |
| Entités fantômes          | intégration 3.1.0+, réparation 48 h ou suppression manuelle |
| Consommation à zéro       | `device_timezone` renseigné ou fuseau HA correct            |
| Durées MRS100 perdues     | logs `Stored` / `Re-applied`, reconnexion de l'appareil     |

## Licence

Fork non officiel, Apache-2.0. Voir `NOTICE`, `MODIFICATIONS.md` et `LEGAL.md`.
