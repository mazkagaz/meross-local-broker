# Format de capture (mode avancé)

Le mode capture observe les échanges d'un appareil appairé et produit un
**brouillon de profil**. Il ne modifie jamais le profil actif.

## Activation

- Toggle **Capture** dans la page avancée, par appareil, avec durée maximale
  et taille maximale.
- Démarrage/arrêt explicites + arrêt automatique à la limite.
- Chaque session est horodatée et journalisée dans l'audit de l'add-on.
- Aucune capture pour un appareil non appairé ou non authentifié.

## Données enregistrées

Session (`session.json`) :

```json
{
  "schema_version": 1,
  "session_id": "2026-11-19T10:00:00Z-<uuid>",
  "device": { "uuid": "<uuid>", "type": "mrs100", "firmware": "7.3.3" },
  "abilities": ["Appliance.RollerShutter.State", "..."],
  "descriptor": { "productname": "...", "model": "..." },
  "started_at": "2026-11-19T10:00:00Z",
  "stopped_at": "2026-11-19T10:05:00Z",
  "reason": "user|duration|size"
}
```

Trames (`frames.jsonl`, une ligne par message) :

```json
{
  "ts": 1763546400.123,
  "dir": "rx",
  "topic": "/appliance/<uuid>/publish",
  "namespace": "Appliance.RollerShutter.Position",
  "method": "GETACK",
  "payload": { "channel": 0, "position": 42, "state": 1 }
}
```

- `dir` : `rx` (appareil -> broker) ou `tx` (broker/app -> appareil).
- Les `GETACK`/`SETACK`/`PUSH` sont conservés ; les doublons exacts consécutifs
  sont fusionnés avec un compteur.
- Les digests `System.All` sont enregistrés comme instantanés (`snapshots`).

## Assainissement

- `sign` et `messageId` retirés ; les identifiants de message éventuellement
  utiles sont remplacés par un hash court.
- Horodatages conservés, jamais les clés, tokens ou mots de passe.
- MAC affichable en clair ou masquée selon le réglage de la page avancée.
- Trame tronquée au-delà d'une taille configurable, avec marqueur
  `"truncated": true`.
- Fichiers créés en `0600` dans `/data/capture/`, hors du dossier servi en
  HTTP.

## Obfuscation pour partage (issues GitHub)

La capture brute reste locale. L'export destiné à une issue passe par un mode
**obfusqué par défaut** :

- **Pseudonymisation stable** : UUID, MAC, adresse IP locale, SSID, nom
  d'appareil et identifiants matériels sont remplacés par des jetons
  déterministes (`device-1`, `mac-1`, `ip-1`, `ssid-1`…) calculés avec un sel
  aléatoire propre à l'export. Les relations entre trames restent lisibles ;
  le sel n'est jamais exporté et les jetons ne sont pas réversibles.
- **Champs sensibles supprimés** : clés, tokens, `sign`, `messageId`, valeurs
  de `Appliance.Config.Key`, mots de passe Wi-Fi.
- **Horodatages** : remplacés par des offsets relatifs au début de session.
- **Conservé** : type d'appareil, sous-type, firmware (optionnel), noms de
  namespaces, méthodes, structure et valeurs des payloads utiles au diagnostic.
- **Revue obligatoire** : aperçu avant export (ce qui sera remplacé ou
  supprimé), possibilité de masquer un champ ou une trame supplémentaire.
- **Manifeste** : l'archive d'export contient `obfuscation.json` (mode, liste
  des champs remplacés, date, version du format), sans le sel.

Export recommandé : archive `capture-share.zip` avec `session.json`,
`frames.jsonl`, `draft.yaml`, `obfuscation.json` et `README.txt` rappelant
qu'il s'agit de données obfusquées. Un utilisateur avancé peut choisir
`none` en connaissance de cause, mais le défaut d'export est toujours obfusqué.

L'obfuscation est une réduction de risque, pas une garantie : la revue humaine
reste la dernière barrière avant publication.

## Génération du brouillon (`draft.yaml`)

Le générateur propose, avec un niveau de confiance :

- **identité** : type, sous-type, abilities, préfixes MAC ;
- **namespaces** : méthodes et champs observés, types/échelles déduits ;
- **entités candidates** : d'après les namespaces connus et les champs trouvés
  (`togglex`, `electricity`, `light`, `RollerShutter.*`) ;
- **inconnues** : champs ou namespaces non rattachés, listés en `x-capture.unknown`.

Règles :

- aucune inférence destructive : le brouillon est un fichier séparé, jamais
  appliqué ;
- champs non reconnus conservés sous `x-capture` avec échantillons ;
- le brouillon porte `x-capture: {session_id, confidence, sampled_frames}`.

## Cycle de validation

1. Capture -> `draft.yaml` + `frames.jsonl`.
2. Revue en mode avancé : compléter/renommer les entités, rattacher les
   inconnues.
3. Validation du schéma (`schema_version`, `requires_engine`).
4. Test à blanc : diff d'entités avant activation.
5. Activation en surcharge locale (`source: custom`) ou proposition de PR pour
   le catalogue livré.
6. Arrêt de la capture et purge selon la politique de rétention.

## Limites

- Capture limitée aux échanges de l'appareil choisi.
- Pas de capture des identifiants de compte, ni du trafic d'autres appareils.
- Les trames ne remplacent pas la validation matérielle : un profil issu d'une
  capture doit être testé sur l'appareil avant publication.
