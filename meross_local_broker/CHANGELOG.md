## 1.2.1

- Profils MRS100 et `mrs` corrigés d’après les trames réelles :
  `position`/`state`/`config`/`adjust` sont des listes ; les commandes
  Position, Config et Adjust utilisent un objet sous la clé du namespace.
- Volets : ouvrir/fermer/stop/position passent par
  `Appliance.RollerShutter.Position` (`100`, `0`, `-1`).
- Durées : lecture de `config[0].signalOpen/signalClose` et écriture
  `{"config":{"channel":…,"signalOpen":…}}`.
- Calibration : statut `adjust[0].status`, démarrage `value=1`, arrêt `value=2`.
- Aucun changement d’API ; l’intégration détecte la nouvelle révision du
  catalogue et se recharge.

## 1.2.0

- API de profils : `/v1/Device/profiles/rev`, `/profiles` et
  `/profiles/pubkey`, catalogue signé Ed25519, révision et source par profil.
- Surcharges `/data/device_profiles` (remplacement ou ajout), rechargement
  admin avec diff `added/removed/changed` et détection automatique à la
  lecture du catalogue.
- Capture de trames par appareil : sessions bornées, secrets retirés,
  identifiants pseudonymisés, brouillon de profil.
- Endpoint `/v1/Device/rollerShutterConfig` pour le cache volet côté
  intégration.
- Contrats API v1 et validation des réponses/fixtures.
- Le broker n’importe plus `meross_iot` (enums/exceptions locaux).

## 1.1.3

- Journaux DEBUG du routage : enregistrement `messageId → topic de réponse`,
  méthode/namespace des publications d'appareil et topics de livraison.
- Obfuscation automatique des journaux : UUID, MAC, IP, emails, identifiants
  d'application et secrets (`sign`, `key`, `token`, `password`, `Basic`)
  remplacés par des pseudonymes stables (clé aléatoire persistée dans
  `/data/log_redaction.key`).

## 1.1.2

- Correctif du routage des ACK : les appareils répondent avec
  `header.from = /appliance/<uuid>/publish`, pas avec le topic applicatif. Le
  broker mémorise désormais, par `messageId`, le topic de réponse de la requête
  d'origine (validé comme appartenant au propriétaire) et y délivre l'ACK.
  Le mode temporaire `legacy_user_topic_acks` s'applique à ce routage.

## 1.1.1

- Routage des réponses d'appareil : en plus de `/app/<userId>/subscribe`, une
  publication dont le `header.from` est un topic applicatif
  (`/app/<userId>-<appId>/subscribe`) est aussi délivrée sur ce topic, comme le
  fait le cloud Meross. Les clients standard (merossclient) reçoivent ainsi
  leurs ACK. Seul le topic du propriétaire de l'appareil est accepté.
- Nouvelle option temporaire `legacy_user_topic_acks` (défaut `true`) pour
  désactiver la copie des ACK sur le topic utilisateur pendant les tests. Elle
  sera supprimée avec le nettoyage D5.1.

## 1.1.0

- Catalogue de profils d'appareils (lecture seule) : profils livrés MRS100,
  mss310 et msl120, validation JSON Schema au démarrage, révision SHA-256
  stable. Un profil invalide est exclu sans bloquer l'add-on.
- Nouvelles routes signées `POST /v1/Device/profiles/rev` et
  `POST /v1/Device/profiles`.
- Dépendances épinglées `PyYAML==6.0.2` et `jsonschema==4.23.0`.
- Documentation et messages alignés sur la version stable 1.0.0 ; version
  locale du panneau web alignée (le CI la reprend de `config.yaml`).

## 1.0.0

Première version stable du fork. Les évolutions depuis le fork, les
changements cassants et la procédure de mise à jour sont récapitulés dans
[RELEASE_NOTES.md](../RELEASE_NOTES.md).

- HTTPS 2004 obligatoire pour les clients LAN ; le port 2003 reste réservé à
  l'ingress du Supervisor.
- CA locale valide et épinglée par l'intégration ; options de contournement
  supprimées.
- Surface d'options réduite à `advertise`, `debug_mode`, `device_timezone`,
  `mqtt_integrity_mode` et `reinit_db`.
- Compatible avec Meross Local Cloud 2.3.2 et Meross Local Pairer 2.0.8.

## 0.0.1-alpha106

- Nettoyage de la surface publique avant la version stable :
  - suppression de `enable_https` (HTTPS 2004 toujours actif, seul port LAN
    annoncé en mDNS) ;
  - suppression de `auto_regenerate_legacy_ca` (une CA legacy ou invalide est
    toujours régénérée) ;
  - suppression de l'option interne morte `expose_admin_api` ;
  - `debug_mode` ne fait plus que passer les journaux en `DEBUG` : debugpy, le
    mode debug Flask et la dépendance `debugpy` sont retirés ;
  - le mode d'intégrité MQTT `off` (non exposé dans le schéma) est retiré.
- Traductions complétées pour `mqtt_integrity_mode` et texte mDNS corrigé.
- Documentation entièrement revue (README, DOCS, TESTING, BUILDING, MRS100,
  MODIFICATIONS) et notes de version consolidées dans `RELEASE_NOTES.md`.
- En-têtes de modification Apache 2.0 ajoutés aux fichiers issus de l'upstream.

## 0.0.1-alpha105

- Panneau web, page Journaux : les champs de recherche et de niveau passent à
  gauche, juste après les boutons ; le compteur reste à droite. La barre
  d'outils passe à la ligne au lieu de déborder sur les petits écrans.

## 0.0.1-alpha104

- Panneau web : un clic sur une diode ouvre une page **Journaux** pleine page
  à quatre onglets, positionnée sur le service cliqué, avec flèche Retour.
  Recherche avec surlignage, filtre par niveau, copie des lignes visibles,
  téléchargement du journal complet, pause/suivi et retour à la ligne.
- Seul l'onglet affiché interroge l'API : changer d'onglet ou quitter la page
  arrête le flux précédent.

## 0.0.1-alpha103

- Déconnexion d'un appareil oublié : l'événement
  `$SYS/client-disconnections` est ignoré proprement quand l'appareil n'existe
  plus en base. L'agent ne lève plus `Device … was not present into the database` après un oubli.

## 0.0.1-alpha102

- Correctif : la purge des unbinds en attente relisait `device_uuid` sur la
  ligne qu'elle venait de supprimer. SQLAlchemy levait alors
  `ObjectDeletedError` et l'agent journalisait `Periodic device refresh failed` après chaque oubli. Les valeurs sont lues avant la suppression et
  la purge est sérialisée par le verrou de l'agent. L'Unbind était déjà publié
  correctement ; seule la journalisation échouait.

## 0.0.1-alpha101

- Oubli d'un appareil (`/v1/Device/delete` et suppression depuis le panneau
  web) : le broker met l'événement en file et l'agent publie un
  `Appliance.Control.Unbind` sur `/app/<userId>/subscribe`, signé avec la clé
  du propriétaire. L'intégration Home Assistant supprime alors l'appareil et
  ses entités au lieu de laisser des entités fantômes.
- La publication est tentée à la (re)connexion de l'agent et à chaque cycle
  de rafraîchissement (60 s) ; une entrée sans propriétaire est simplement
  abandonnée. Le délai maximal entre la suppression et la disparition des
  entités Home Assistant est donc de 60 secondes (ou immédiat à la reconnexion
  de l'agent).

## 0.0.1-alpha100

- Le port **2003** (HTTP) n'est plus exposé sur le LAN : il est réservé à
  l'ingress du Supervisor (défense en profondeur par ACL nginx) et son mapping
  hôte est supprimé. Les clients LAN doivent utiliser **HTTPS 2004**.
- mDNS : `http_port` n'est plus publié ; le SRV `_meross-api._tcp` pointe sur
  le port HTTPS.
- Documentation mise à jour (ingress, HTTPS obligatoire côté LAN).

## 0.0.1-alpha99

- TLS : la CA locale est désormais valide (`basicConstraints=critical,CA:TRUE`,
  `keyUsage=keyCertSign,cRLSign`) et peut être vérifiée par les clients. Les
  anciennes CA invalides sont détectées et régénérées automatiquement, avec
  sauvegarde dans `/data/mqtt/certs.bak-*` (option `auto_regenerate_legacy_ca`).
- Le certificat serveur inclut les adresses IPv4 LAN dans ses SAN et n'est
  re-signé que lorsque ces adresses changent. La vérification du nom d'hôte
  devient possible.
- La passphrase de la CA est aléatoire et stockée dans
  `/data/mqtt/certs/ca.pass` (600) ; plus de passphrase codée en dur.
- Migration : un reset du certificat épinglé (pairer, import manuel) est
  nécessaire une fois.

## 0.0.1-alpha98

- Démarrage : l'agent ne sonde plus le port 2001 en TCP brut
  (`bashio::net.wait_for`). Cette sonde fermait la connexion avant la poignée
  de main TLS, ce qui faisait journaliser à Mosquitto
  `unexpected eof while reading` à chaque démarrage. L'agent retente désormais
  sa vraie connexion TLS (1 s d'intervalle, 60 s max) jusqu'à ce que Mosquitto
  soit prêt.

## 0.0.1-alpha97

- ACL MQTT : un appareil peut publier les réponses de commande sur les topics
  de l'application propriétaire (`/app/<userId>/subscribe` et
  `/app/<userId>-<appId>/subscribe`). Sans cette autorisation, les ACK étaient
  rejetés en 403 et l'intégration Home Assistant expirait sur
  `Appliance.System.Ability`. L'écriture reste limitée aux topics de
  l'utilisateur qui possède l'appareil.

## 0.0.1-alpha96

- nginx transmet `X-Forwarded-Proto` et Flask utilise `ProxyFix` : l'API
  annonce désormais `https://…:2004` derrière le listener TLS, au lieu de
  `http://…:2004`. Corrige la connexion de l'intégration Home Assistant, qui
  appelait `/v1/log/user` en clair sur le port chiffré (400 renvoyé par nginx).

## 0.0.1-alpha95

- nginx attend que l'API écoute sur `127.0.0.1:2002` (60 s max) avant de
  démarrer, évitant les 502 transitoires et les fausses erreurs au démarrage.
  s6 n'utilise pas systemd : l'ordre est assuré par une attente de disponibilité.

## 0.0.1-alpha94

- Empêche la mise en cache de l'interface (`Cache-Control: no-store`) : les
  mises à jour de l'UI (diodes, logs) sont visibles sans vidage manuel du cache.
- L'état des diodes analyse 500 lignes de logs par service au lieu de 200,
  afin de conserver plus longtemps une erreur transitoire.

## 0.0.1-alpha93

- Les diodes d'état des services reflètent désormais les logs : **grise** si
  les logs sont vides, **verte** si le service tourne sans incident,
  **orange** si des warnings sont présents, **rouge** si une erreur est
  présente. `/_admin_/services` expose `logStatus` (analyse des 200 dernières
  lignes).

## 0.0.1-alpha92

- Corrige l'appel à `supervisor_network.py` (`Permission denied`) : le script
  est exécuté via `python3` et dispose du bit exécutable. Le TXT mDNS `host`
  est de nouveau renseigné, rétablissant la découverte automatique.

## 0.0.1-alpha91

- L'API tourne sous **Waitress** au lieu du serveur de développement Flask :
  plus d'avertissement « development server », et plus de logs de requête par
  défaut.
- Ajout de `hassio_api` : l'add-on peut interroger les interfaces réseau du
  Supervisor et publier l'adresse LAN dans les TXT mDNS. La découverte
  automatique du broker fonctionne à nouveau.
- Si aucune adresse LAN n'est trouvée, le motif est journalisé.

## 0.0.1-alpha90

- Autorise l'agent interne à lire les topics concrets
  `/appliance/<uuid>/publish|subscribe` et `/_nat_/<id>` utilisés par les
  contrôles de livraison MQTT, en plus des wildcards d'abonnement. Corrige les
  403 `username=_agent ... acc=1` et rétablit la réception des messages appareil.
- Le login `_agent` attendu par le backend HTTP n'est plus journalisé en erreur.

## 0.0.1-alpha89

- Corrige `auth_opt_log_level` : la valeur reconnue par go-auth est `warn`
  (et non `warning`). Les codes 403 ne sont plus répétés au niveau `info` ;
  les refus ACL restent journalisés une fois par l'API avec le topic et `acc`.

## 0.0.1-alpha88

- Remplace `bashio::addon.port` par `bashio::app.port` dans les services API et
  MQTT (supprime l'avertissement de dépréciation).
- Déclare `auth_opt_hasher pbkdf2`, supprimant l'avertissement go-auth
  « unknown or empty hasher ».
- Autorise les appareils à publier leurs messages `/_agent` et vérifie la
  signature de ces messages comme les publications d'appareil.

## 0.0.1-alpha87

- Corrige les refus ACL MQTT lors des désabonnements (`acc=8`) : ils suivent
  désormais la politique de lecture. Chaque type de refus est journalisé une
  fois avec utilisateur, clientid, topic et acc, au lieu de saturer les logs.
- Réduit le bruit : les requêtes `/_devs_/acl` ne sont plus journalisées par
  Werkzeug et go-auth passe au niveau `warning`.
- Panneau web : fenêtre de logs revue avec copie par ligne, copie complète,
  pause, retour à la ligne, téléchargement et défilement intelligent.

## 0.0.1-alpha86

- `devList` renvoie `bindTime` sous forme d'entier (0 si inconnu), supprimant
  les avertissements `Provided bind_time is not int neither datetime` de
  `meross_iot` dans l'intégration Home Assistant.

## 0.0.1-alpha85

- Corrige la connexion des clients qui envoient l'horodatage de signature en
  nombre JSON (pairer Android et `meross_iot`) : le contrôle de type ajouté en
  alpha82 rejetait ces requêtes avec « Key verification failed ». Les deux
  formats, nombre et chaîne, sont désormais acceptés.

## 0.0.1-alpha84

- Corrige l'accès au panneau et à la configuration du compte local : le backend
  n'exige plus les en-têtes d'identité ingress sur `/_admin_`, qui bloquaient
  les requêtes du panneau. nginx conserve la restriction au Supervisor.

## 0.0.1-alpha83

- Corrige l'ACL MQTT de l'intégration Home Assistant : le topic de réponse
  `/app/<userId>-<appId>/subscribe` est désormais autorisé en lecture pour le
  compte concerné. Sans cela, les accusés de réception des commandes envoyées
  via l'intégration n'étaient plus reçus.

## 0.0.1-alpha82

Sécurité de l'API, des sessions et du broker MQTT.

- Journaux expurgés et niveau INFO par défaut : plus de tokens, corps de
  requêtes, mots de passe ou hashes d'appareils. Les logs détaillés restent
  disponibles en `debug_mode`.
- Débogage strictement local : debugpy écoute uniquement sur `127.0.0.1` et le
  port 10001 n'est plus publié.
- API d'administration limitée à l'ingress Home Assistant, avec vérification
  des en-têtes d'identité HA. Exposition publique possible uniquement avec
  `debug_mode` et `expose_admin_api`.
- CORS désactivé par défaut ; réponses d'erreur génériques côté client.
- Sessions : tokens stockés uniquement hachés (SHA-256), expiration absolue de
  30 jours et inactivité de 7 jours, sans refresh token. Toutes les sessions
  existantes sont invalidées : le pairer et l'intégration doivent se
  reconnecter. Les erreurs de jeton conservent le format Meross
  (`CODE_TOKEN_ERROR`) avec un motif précis (`token_invalid`, `token_expired`,
  `token_idle_expired`) pour rester compatibles avec `meross_iot`.
- Protection contre le brute force : limitation des échecs de connexion par IP
  et par compte, avec `Retry-After`.
- Mots de passe de compte hachés avec **Argon2id** ; les anciens hashes sont
  vérifiés une dernière fois puis migrés automatiquement à la connexion.
- MQTT : chaque appareil est limité à ses propres topics et chaque compte
  applicatif à ses appareils. Vérification de signature, fraîcheur et
  anti-rejeu des publications, avec la nouvelle option
  `mqtt_integrity_mode` : `observe` par défaut (journalisation), `enforce`
  pour rejeter les messages invalides.

## 0.0.1-alpha81

- Present the broker as compatible with Meross devices in general instead of
  focusing on the MRS100, and invite users to report test results and request
  specific integrations.
- Describe Bluetooth LE pairing instead of firmware 7/8 in the setup guidance.
- Drop the obsolete "LAN-only broker" integration mode from the setup and
  documentation: the integration only supports the local broker.
- Restore the brown coffee icon on the About page.

## 0.0.1-alpha80

- Fix switching between Setup and Pair devices: the section now follows route
  data instead of being fixed when the page first opens.
- Follow the Home Assistant theme inside ingress by importing the parent
  theme variables (header, cards, text, dark mode). Standalone installs keep
  the HA default colours as fallbacks.
- Devices no longer stay UNKNOWN after a broker restart. Online statuses are
  reset during container init, before mosquitto accepts connections, so the
  ONLINE status set by device authentication is no longer overwritten by the
  broker agent.
- Add-on documentation and option descriptions now cover the HTTPS API on
  port 2004 (enabled by default), HTTP on 2003, and the `enable_https` option.

## 0.0.1-alpha79

- Re-publish the alpha78 Web UI with the final theme polish: Home Assistant
  header and card variables, default HA colours as fallbacks, readable active
  toolbar icons and redirects for the old URLs. Earlier alpha78 images were
  built before these last commits.

## 0.0.1-alpha78

- Replace the three-dot menu with three toolbar icons: Setup, Pair devices and
  About.
- Merge the Home Assistant instructions into the Setup page and move the
  device pairing procedure to the Pair devices page, with a link to the
  official pairer user guide.
- Follow the Home Assistant theme variables (surfaces, text, primary/accent,
  warning and error colours) with standalone fallbacks.
- Colour warning and error lines in the service log dialog and add a Copy
  button.

## 0.0.1-alpha77

- Paired devices page: show the repository banner, add meaningful device
  icons (roller shutters vs. plugs), rename "Assign name" to "Rename", and
  hide the subdevice table when no subdevice is paired.
- Replace the standalone service status page with four compact status tiles
  on the devices page. Each tile shows a green/red LED and opens a closable
  live log window for that service when clicked.
- The guided setup only appears on a broker without a local account. After
  that, the menu exposes four separate setup blocks: broker access, pairer
  app, device pairing and Home Assistant.
- Add a standard/advanced toggle to the devices table. Standard mode hides the
  UUID, MAC address and user id; the choice is remembered.
- Expand the About page with the banner, principles, attributions, source
  links and an optional coffee link.

## 0.0.1-alpha76

- Replace the deprecated `bashio::addon.ingress_entry`, `ingress_port` and
  `ip_address` calls with `bashio::app.*`, removing the repeated deprecation
  warnings from the add-on log.

## 0.0.1-alpha75

- The API mDNS service now carries TXT records with the usable LAN data:
  `host` (comma-separated Home Assistant IPv4 addresses from the Supervisor),
  `http_port` and `https_port` (host-mapped ports, or 0 when HTTPS is
  disabled). The pairing app can prefill a reachable endpoint instead of
  relying on the add-on's Docker hostname.

## 0.0.1-alpha74

- Device names are now unique (case-insensitive). Both the authenticated
  `POST /v1/Device/name` endpoint and the Web UI rename action refuse a name
  already used by another device; renaming a device to its own name is allowed.
- The Web UI rename validates the name (non-empty, at most 128 characters).
- Devices without an online status no longer make the admin/Web UI device
  serialization fail.

## 0.0.1-alpha73

- Add the authenticated `POST /v1/Device/name` endpoint so the pairing app can
  set the device display name during pairing. The name is validated (non-empty,
  at most 128 characters) and stored in the broker device list.

## 0.0.1-alpha72

- The Web UI device and subdevice tables now refresh automatically every
  10 seconds, so a device forgotten (or added) from the pairing app disappears
  without a page reload.

## 0.0.1-alpha71

- Add an HTTPS listener on port **2004**, sharing the CA and server
  certificate already used by the MQTT/TLS listener on port 2001. Port 2003
  stays available in plain HTTP for Home Assistant ingress and existing
  clients.
- The listener is controlled by the new `enable_https` add-on option
  (default `true`). Turning it off removes only the HTTPS server block;
  MQTT/TLS on 2001 and HTTP on 2003 are unchanged.
- Serve the local CA at `/ca.crt` on both listeners so clients can import or
  pin it. Compare the fingerprint out of band before trusting it.
- New certificates carry `homeassistant.local`, `localhost` and `127.0.0.1`
  in their subject alternative names. Existing certificates are kept; delete
  `/data/mqtt/certs` (or the add-on data) to regenerate them.

## 0.0.1-alpha70

- Forgotten devices are now revoked, not just deleted: the broker refuses their
  MQTT login with the credentials they still hold, so a forgotten device cannot
  reconnect by itself.
- Add the authenticated `POST /v1/Device/claim` endpoint. After a successful
  re-pairing, the pairing app calls it to lift the revocation; the device keeps
  the same UUID, so Home Assistant entity identities and automations survive a
  forget/re-pair cycle.

## 0.0.1-alpha69

- Add the authenticated `POST /v1/Device/delete` endpoint, so the Android
  pairing app can forget a device owned by the logged-in local account.

## 0.0.1-alpha68

- Keep devices marked online in the HTTP device list when they are connected
  to the local broker. The firmware-reported `system.online.status` can be 0
  when a device is not bound to the Meross cloud, which previously made Home
  Assistant entities unavailable even though MQTT was connected.

## 0.0.1-alpha67

- Add the standard back arrow in the header of Setup, Service status and About
  so these pages return to the paired-devices page.

## 0.0.1-alpha66

- Service logs are decoded with replacement instead of failing with a 500
  when a log contains non-UTF-8 bytes (e.g. nginx binary data).

## 0.0.1-alpha65

- Add **Forget device** to the device menu: removes the device, its channels,
  subdevices and roller-shutter state from the broker database.
- Regenerate the add-on icon from the transparent logo artwork.

## 0.0.1-alpha64

- Fix remaining product-name inconsistencies: the Home Assistant sidebar panel,
  service descriptions and event messages now say **Meross Local Broker**.

## 0.0.1-alpha63

- Refer to the Home Assistant integration as **Meross Local Cloud** in the
  wizard and the installation guide, and document the local-login flow.

## 0.0.1-alpha62

- Rename the add-on to **Meross Local Broker** and add the new banner and icon.
- Remove MRS100 from user-facing titles.

## 0.0.1-alpha61

- Clarify add-on options with names and descriptions in the configuration tab.
- Simplify the Web UI: the device and subdevice tiles are the only front page;
  Setup, Service status and About move to a `...` menu in the top-right.
- Remove the language selector while only English is available.

## 0.0.1-alpha60

- Refer to the Android pairing app as **Meross Local Pairer** in the Web UI
  and documentation.

## 0.0.1-alpha59

- The About page now shows the add-on version declared in `config.yaml`.
  The build workflow copies that version into the Web UI package before
  building, so the displayed value can no longer drift (#10).

## 0.0.1-alpha58

- Fix the upgrade path for accounts created with alpha56 or earlier: their
  password was double-hashed by the admin panel. The first successful login
  now repairs the stored hash transparently, so no account is locked out.

## 0.0.1-alpha57

- Local-only account configuration: remove the Meross Link toggle and the
  cloud federation path. The add-on never contacts or stores Meross cloud
  credentials.
- Clarify the account form: "Login (email or username)", local account only.
- Point the setup wizard to Local Pairer (GitHub Releases) and to the
  `mazkagaz/meross-local-cloud` HACS integration instead of the legacy Play Store app.

## 0.0.1-alpha56

- Fix add-on startup: `get_option` no longer aborts under `set -e` when an
  option is `false` or missing. This repairs `40-api.sh` and `60-nginx.sh`
  exits during container init.

## 0.0.1-alpha55

- Migrate CI to the maintained `home-assistant/builder` composable actions (2026.09.0).
- Build only amd64 and aarch64; the 32-bit architectures are no longer supported by the builder.
- Keep the Web UI build before the Docker image build.

## 0.0.1-alpha54

- Premier commit du fork MRS100.
- Découverte du canal volet roulant (digest `System.All`, ability
  `RollerShutter.State`, ou type MRS100).
- Persistance de `Appliance.RollerShutter.Config` et réapplication après
  reconnexion/`System.All`, comme le cloud Meross.
- Cache de `RollerShutter.Position/State`, `RollerShutter.Adjust` et
  `Appliance.System.Ability`.
- `devList` expose l'ability et les métadonnées `rollerShutter`.
- Corrections Python 3 (import `hashlib`, suppression d'`asyncore`).

## 0.0.1-alpha53

- Fix the alpha52 startup crash by upgrading Flask to 3.1.3, Werkzeug to 3.1.8, and Flask-CORS to 6.0.5.
- Preserve signed form requests and explicit MQTT authentication denials with Flask 3's stricter JSON handling.
- Check Flask imports and request handling during image builds to catch dependency incompatibilities before release.

## 0.0.1-alpha52

- Push the timezone and DST rules (`Appliance.System.Time`) to devices whose reported timezone is empty or
  different from the configured one, as the Meross cloud does on every connection. Without it, power-metering
  plugs (e.g. mss310, mss210p) keep reporting 0 V / 0 A / 0 W and an empty consumption history (#42).
  New optional `device_timezone` setting, defaulting to the Home Assistant timezone.
- The agent now polls `Appliance.System.All` every 60 seconds from devices whose info is stale. Devices
  reconnecting after a broker restart publish nothing on their own, so without this poll their online status
  (and the timezone check above) never refreshed.
- Fix CICD bulding pipeline

## 0.0.1-alpha46

- Dropped support for armhf platform
- Improved s6 restart procedure
- Updated dependency with meross_iot low level library
- Add new endpoint to support latest version of MerossIot library version

## 0.0.1-alpha45

- Fix meross link parameter being ingored at configuration phase
