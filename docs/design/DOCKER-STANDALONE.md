# Plan — broker autonome pour Home Assistant Container (Docker)

## Contexte

Le broker est livré comme add-on Home Assistant : images multi-arch publiées
(`ghcr.io/mazkagaz/{arch}-meross_local_broker`, tag `1.4.8`) mais démarrage et
administration supposent le Supervisor. **Cible retenue : HA Container**
(Docker sans Supervisor), le cas non couvert aujourd'hui ; HA OS/Supervised
gardent le parcours add-on existant. L'intégration HACS et le pairer
fonctionnent déjà sous HA Container. Objectif : permettre un déploiement
broker + intégration, sans régression du parcours add-on, et sans imposer plus
de trois valeurs à saisir.

## Décisions de conception

1. **Détection du mode** : `SUPERVISOR_TOKEN`/`HASSIO_TOKEN` présent = add-on,
   absent = autonome. Variable explicite `MEROSS_STANDALONE=1` pour forcer.
   Aucun appel `bashio::app.*` ne doit être exécuté en mode autonome (le
   `set -e` de bashio ferait échouer le script).
2. **Options** : conserver `/data/options.json` et la priorité déjà en place
   dans `get_option` (fichier, puis variable d'environnement, puis défaut).
   Documenter les cinq options (`reinit_db`, `advertise`, `debug_mode`,
   `device_timezone`, `mqtt_integrity_mode`).
3. **Admin** : le blueprint `/_admin_` n'a **aucune authentification** ; la
   sécurité repose sur l'ACL nginx Supervisor. En autonome :
   - bind par défaut `127.0.0.1:2003` (`ADMIN_BIND`, `ADMIN_PORT`) ;
   - accès LAN uniquement sur demande explicite (`ADMIN_ALLOW_CIDR`), avec
     avertissement dans la doc ; accès recommandé par tunnel SSH ou reverse
     proxy authentifié ;
   - ne jamais exposer `/_admin_` sans protection.
4. **mDNS** : `advertise` par défaut **false** en autonome. Option avancée :
   `network_mode: host` + socket D-Bus de l'hôte pour `systemd-resolved`.
   Sinon, l'intégration se configure manuellement (hôte, 2004, 2001, compte).
5. **TLS** : les SAN sont calculés via le réseau Supervisor. Ajouter
   `TLS_SAN_EXTRA` (liste IP/DNS) et, si `network_mode: host`,
   `TLS_SAN_AUTO=1` pour détecter les IPv4 locales. Le pinning CA reste la
   sécurité principale ; l'intégration tolère l'absence de correspondance.
6. **Données** : volume `/data` (base, certificats, clés de signature,
   profils, captures). Sauvegarde = copie du volume.
7. **Ports** : 2001 MQTT/TLS et 2004 HTTPS exposés ; 2003 admin local.
8. **Réduction de la friction (objectif : 3 commandes + 3 champs)** :
   - fournir un bundle `deploy/` (compose + `.env.example` + `install.sh`) qui
     crée `./data` et `.env`, démarre le conteneur et affiche les valeurs à
     saisir dans l'intégration (pas de `options.json`, pour que l'environnement
     ne soit pas masqué par sa priorité) ;
   - préremplir les ports **2004** et **2001** dans le formulaire de
     l'intégration, même sans découverte mDNS (deux champs en moins) ;
   - générer les certificats au premier démarrage (déjà le cas) et détecter
     l'IP locale pour les SAN ;
   - afficher la commande de tunnel SSH pour l'admin (`ssh -L 2003:...`).

## Étapes d'implémentation

### A. Broker — mode autonome

- `rootfs/opt/utils/bashutils.sh` : exposer `is_standalone()` et les valeurs
  par défaut (pas de bashio).
- `rootfs/etc/cont-init.d/60-nginx.sh` : si autonome, ne pas appeler
  `bashio::app.ingress_*` ; rendre `ADMIN_BIND`, `ADMIN_PORT`,
  `ADMIN_ALLOW_CIDR` dans `ingress.conf` (placeholders supplémentaires).
- `rootfs/etc/nginx/ingress.conf` : ACL paramétrable ; en autonome, autoriser
  le CIDR admin (défaut 127.0.0.1), garder `/v1` et `/ca.crt` LAN sur 2004.
- `rootfs/etc/cont-init.d/50-mosquitto.sh` : SAN via `TLS_SAN_EXTRA` et
  détection locale si demandée.
- `rootfs/etc/services.d/{api,mosquitto}/run` : si autonome, forcer
  `advertise=false` et éviter `bashio::app.port` (ports fixes 2004/2001).
- `meross_local_broker/config.yaml` : inchangé (options add-on) ; documenter
  les équivalents environnement.
- `Dockerfile` : healthcheck `curl -f https://127.0.0.1:2004/ca.crt -k` si
  pertinent ; pas de changement de base.

### B. Déploiement

- Bundle réel `deploy/docker-compose.yml` : `network_mode: host` (IP LAN de
  l'hôte, admin sur la boucle locale), volume `./data`, variables dans `.env`.
  ```yaml
  services:
    meross-broker:
      image: ${BROKER_IMAGE:-ghcr.io/mazkagaz/amd64-meross_local_broker:latest}
      network_mode: host
      volumes: ["./data:/data"]
      environment:
        MEROSS_STANDALONE: "1"
        ADMIN_BIND: "127.0.0.1"
        TLS_SAN_AUTO: "1"
  ```
- Variante bridge documentée : publier 2001/2004, et 2003 uniquement avec un
  `ADMIN_ALLOW_CIDR` explicite (l'admin n'a pas d'authentification).

### C. Confort d'installation

- Bundle `deploy/` : `docker-compose.yml`, `.env.example`, `install.sh`
  (création du volume et de `.env`, démarrage, résumé des valeurs).
- Intégration : valeurs par défaut `2004`/`2001` dans `config_flow.py`
  (schéma `_build_form_schema`) ; test du formulaire sans découverte.
- Guide en 3 étapes : lancer `install.sh`, ajouter l'intégration (hôte +
  compte local), appairer avec le pairer.

### D. HA Container et intégration

- HACS s'installe manuellement (ou copie de `custom_components/`)
  ; l'intégration ne dépend pas du Supervisor.
- Configuration manuelle : hôte/IP Docker, HTTPS 2004, MQTT 2001, compte
  local ; la découverte mDNS reste optionnelle.
- Vérifier le téléchargement de `/ca.crt` et le pinning ; prévoir un bouton
  de réinitialisation du certificat si l'IP change.
- Le pairer ne change pas : adresse du broker = IP de l'hôte Docker.

### E. Tests

- Unitaires Python : `get_option` (fichier/env/défaut), génération SAN,
  sélection des valeurs autonomes.
- Test de rendu nginx : placeholders remplacés en mode autonome et add-on.
- Smoke test CI Docker : build de l'image, démarrage sans Supervisor,
  `curl -k https://localhost:2004/ca.crt` = 200, port 2001 en TLS,
  `/_admin_` accessible en localhost mais refusé depuis un autre conteneur,
  absence d'erreur bashio au démarrage.
- Non-régression add-on : parcours Supervisor inchangé (tests existants).

### F. Documentation et release

- `meross_local_broker/DOCS.md` + `DOCS.fr.md` : section HA Container.
- `README.md` + `README.fr.md` : matrice OS/Supervised vs Container/Core.
- `docs/guides/DOCKER.md` + `DOCKER.fr.md` (guide pas à pas), mis à jour
  dans `docs/translations.json` et le garde-fou CI.
- `CHANGELOG.md`, version broker **1.5.0**, config version 1.5.0, release.

## Vérification finale

- Démarrage autonome sans Supervisor, logs sans erreur bashio.
- Intégration HA Container : configuration manuelle, entités créées, commandes
  MQTT, diagnostics.
- Pairer : appairage, certificat, commandes.
- Admin : accessible en localhost/tunnel uniquement, refusé depuis le LAN sans
  CIDR explicite.
- Redémarrage : données et certificats persistés dans `/data`.
- Parcours add-on : inchangé, CI verte.

## Risques

- **Exposition admin** : point le plus sensible ; bind localhost par défaut.
- **SAN/IP changeante** : documenter `TLS_SAN_EXTRA` et la réinitialisation du
  pin côté pairer/intégration.
- **mDNS** : non garanti en bridge ; configuration manuelle par défaut.
- **Support** : deux modes à maintenir ; marquer le mode autonome comme
  pris en charge à partir de la 1.5.0.

## Estimation

- Broker autonome : 1–2 jours.
- Bundle (compose, `install.sh`), défauts du formulaire, guide HA Container,
  docs bilingues : 1,5 jour.
- Tests + CI Docker : 0,5–1 jour.
- Total : **3–4,5 jours**, hors validation utilisateur sur une instance réelle.
