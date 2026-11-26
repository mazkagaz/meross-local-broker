# Test E2E sous Supervisor réel

`tests/supervisor/run.sh` démarre un conteneur **Home Assistant Supervisor**
(comme la CI de `home-assistant/supervisor`), construit un add-on local à
partir de l'image broker publiée et du `rootfs` du dépôt, l'installe, le
démarre et vérifie le mode add-on.

## Prérequis

- Docker avec conteneurs privilégiés (le Supervisor monte le socket Docker).
- `jq`, `curl`, `openssl`.
- Image broker de base (`BASE_IMAGE`, défaut `1.4.8`) et image Supervisor
  (`SUPERVISOR_IMAGE`).
- Hôte Linux avec forwarding Docker fonctionnel ; ce test ne peut pas tourner
  sur une machine où le réseau inter-conteneurs est bloqué.

## Lancer

```bash
sudo mkdir -p /run/supervisor/core
bash tests/supervisor/run.sh
```

`KEEP=1` conserve le Supervisor, l'add-on et le dossier temporaire pour
inspection.

## Ce qui est vérifié

- installation et démarrage de l'add-on par le Supervisor ;
- état `started` ;
- HTTPS `/ca.crt` sur 2004 et MQTT/TLS sur 2001 ;
- utilisation de l'ingress Supervisor (`Substituting ingress_entry`) ;
- absence du mode autonome (`Standalone mode:` ne doit pas apparaître).

## Limites

- amd64 uniquement ;
- pas d'appareil Meross : l'appairage et les commandes device ne sont pas
  couverts ;
- l'add-on est construit en surcouche de l'image publiée, pas par la CI
  `Builder` complète ;
- ce test est long (démarrage du Supervisor et installation de Home Assistant
  Core) et tourne dans le job `Supervisor` du workflow `CI`.
