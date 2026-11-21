# Vue d’architecture du broker

## Rôle

Le broker est l’unique source de vérité locale pour l’authentification, les
appareils Meross, les topics MQTT et le catalogue de profils. L’intégration
Home Assistant et le pairer sont des clients ; aucun service cloud Meross
n’intervient dans l’usage quotidien.

## Composants

| Composant         | Responsabilité                                                      |
| ----------------- | ------------------------------------------------------------------- |
| nginx / ingress   | TLS, exposition HTTPS 2004, accès Supervisor à `/ _admin_`          |
| API Flask         | authentification, `devList`, profils, configuration volet, admin    |
| Broker MQTT       | TLS 2001, ACL par appareil/compte, routage des ACK                  |
| Base SQLite       | comptes, sessions, appareils, canaux, statuts, cache volet          |
| Catalogue profils | profils YAML, surcharges `/data/device_profiles`, signature Ed25519 |
| Capture           | sessions bornées, assainissement, brouillon de profil               |
| Agent             | reconnexion des appareils, application du fuseau, Unbind            |
| Panneau web       | comptes, appareils, logs, configuration                             |

## Flux principaux

```text
Pairer ──appairage──> broker (compte, clé, topics)
Appareil ──MQTT/TLS 2001──> broker ──publications──> intégration HA
Intégration ──HTTPS 2004 + signature──> API Flask
API ──catalogue signé + métadonnées──> intégration HA
```

## Invariants

- HTTPS obligatoire pour les clients LAN ; le port 2003 est réservé à l’ingress.
- Les topics d’un appareil sont limités à son propriétaire et à son UUID.
- Le catalogue chargé est validé et sa signature vérifiée côté intégration.
- Les surcharges remplacent les profils livrés sans modifier l’image.
- L’API d’administration n’est accessible qu’au Supervisor.
- Les journaux sont obfusqués avant écriture.

## Documentation liée

- [Décisions et cible détaillée](D0-ARCHITECTURE.md)
- [Diagramme](arch.drawio)
- [Contrats API](../specs/API-CONTRACTS.md)
- [Traçabilité des tests](../testing/TRACEABILITY.md)
