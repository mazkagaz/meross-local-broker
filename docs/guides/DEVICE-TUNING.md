# Tuning des appareils

La page de tuning permet d’exporter, importer, modifier et tester les profils
d’appareils, puis d’envoyer des commandes typées à un appareil. Elle est
accessible uniquement via l’ingress admin de Home Assistant : icône **tune**
dans l’en-tête, ou route `/tuning`.

Aucune action de cette page ne fonctionne hors ingress. Le catalogue livré
n’est jamais modifié : seules les surcharges sous `/data/device_profiles` sont
écrites, après validation.

## Onglet Profils

- Liste des profils effectifs : version, source (`bundled`/`override`), hash et
  nombre d’appareils impactés. Par défaut, seuls les profils détectés sont
  affichés ; la recherche couvre tout le catalogue et l’option **Show all**
  affiche aussi les profils non détectés (choix mémorisé).
- La révision et les hashes sont tronqués avec la valeur complète en infobulle
  et un bouton de copie.
- Éditeur YAML avec validation continue : erreurs avec ligne et colonne,
  avertissements du moteur partagé, diff unifié contre la base effective
  (`bundled` ou `override`).
- **Apply override** : confirmation avec impact, écriture atomique, sauvegarde
  préalable, verrou optimiste par hash et rechargement du catalogue.
- **Revert to bundled** : supprime la surcharge (avec backup préalable).
- **Backups** : liste horodatée ; chaque restauration est elle aussi
  sauvegardée avant écriture.
- **Import** : fichier YAML ou ZIP, validation et dry-run d’abord, application
  après confirmation. Les doublons d’id, entrées hors limites et chemins
  d’archive sont refusés.
- **Export** : YAML d’un profil ou ZIP (surcharges ou catalogue effectif) avec
  manifeste.

Limites serveur : 256 Ko et 5000 lignes par profil, profondeur 32 ; import
2 Mo et 200 profils. Les fichiers sont écrits avec fsync et permissions
restreintes.

## Onglet Appareils

- Descripteur, profil associé (source et hash), entités attendues, plan de
  polling, document de capacité et cache volet (`status`, `config`, `adjust`).
- **Simulate a frame** : rejoue une trame `GETACK`, `SETACK` ou `PUSH` dans le
  moteur partagé sans rien envoyer à l’appareil. Les canaux peuvent être
  déduits du payload ; un sous-appareil peut être ciblé par id et type.
- **Live read** : GET signé en lecture seule, limité aux namespaces déclarés
  par le profil (plus `Appliance.System.All`). Cooldown par appareil, timeout
  borné ; la réponse est assainie et les valeurs typées sont extraites.
- **Commands** : commandes déclarées par le profil, générées par substitution
  des canaux et valeurs (`$channel`, `$value`) — jamais de payload brut.
  Chaque envoi exige une confirmation à usage unique (jeton de 60 s lié à
  l’appareil et à la commande), un appareil en ligne, une seule commande à la
  fois et un cooldown. L’action est auditée avec un snapshot avant/après.
- **Capture** : démarrer/arrêter une session, puis injecter le brouillon YAML
  dans l’éditeur. Le brouillon est un point de départ (`draft.<type>`) à
  compléter et valider avant application.

## Onglet Audit

Journal des actions : acteur Home Assistant, date, action, profil, révision,
hash avant/après, et pour les commandes le résultat et les snapshots. L’API
accepte `?profile_id=` et `?device_uuid=` pour filtrer.

## Codes d’erreur utiles

- `400` : YAML ou commande invalide, valeur/canal hors contraintes.
- `404` : profil, appareil ou backup inconnu.
- `409` : conflit de hash, appareil hors ligne, jeton expiré/réutilisé,
  commande déjà en cours.
- `429` : cooldown de lecture ou de commande (`Retry-After`).
- `503` : broker MQTT local indisponible.
- `504` : l’appareil n’a pas répondu dans le délai.

## Fichiers

| Chemin                      | Contenu                                            |
| --------------------------- | -------------------------------------------------- |
| `/data/device_profiles`     | surcharges YAML (catalogue livré en lecture seule) |
| `/data/profile_backups`     | backups horodatés (20 par profil)                  |
| `/data/profile_audit.jsonl` | audit des profils et des commandes                 |
| `/data/capture`             | sessions de capture et brouillons                  |

Les jetons de confirmation et les identifiants MQTT de lecture restent en
mémoire et ne sont jamais persistés.

## Aucun profil associé à un appareil

Si la fiche affiche **No profile matches this device**, le broker n’a pas encore
reçu le document de capacités (`Appliance.System.Ability`). Depuis la 1.4.1,
l’agent le demande automatiquement au démarrage, lors des rafraîchissements et
à la première publication de l’appareil (cooldown de 5 min, rafraîchissement
quotidien). Recharger la page après la réponse de l’appareil. Si l’appareil ne
répond jamais à cette requête, le matching reste indisponible pour ce modèle.
