# Matrice de traçabilité — broker

Cette matrice relie les exigences, les composants et les tests. Les scénarios
`F1`–`F8` sont définis dans [FUNCTIONAL-TESTS.md](FUNCTIONAL-TESTS.md). Les
vérifications matérielles restent manuelles.

## Exigences et couverture automatique

| ID             | Exigence                                                  | Composant                                         | Tests unitaires / contrat                                                                      | Scénario   |
| -------------- | --------------------------------------------------------- | ------------------------------------------------- | ---------------------------------------------------------------------------------------------- | ---------- |
| BRK-AUTH-001   | Authentification locale, sessions, mots de passe Argon2id | `blueprints/auth`, `db_helper`, `auth`            | `test_http_api.py`                                                                             | F1         |
| BRK-DEV-001    | Comptes, appairage, liste `devList`                       | `blueprints/device`, `db_helper`                  | `test_http_api.py`, `test_broker_agent_forwarding.py`                                          | F1, F3     |
| BRK-PROF-001   | Catalogue, surcharges, lint, signature Ed25519            | `profiles.py`, `profile_signing.py`               | `test_profiles.py`, `test_profile_lint.py`, `test_profile_signing.py`                          | F6         |
| BRK-API-001    | Contrats API versionnés et fixtures                       | `contracts/`, `blueprints/device.py`              | `test_http_api.py`                                                                             | F6         |
| BRK-PROF-002   | Multiprises : template par canal et sélection indexée     | `device_profiles/mss425.yaml`                     | `test_profile_lint.py` (catalogue) ; moteur côté intégration                                   | F3, F6     |
| BRK-ROLL-001   | Cache volet, position/état/config/calibration             | `broker_agent.py`, `db_helper.py`, profils MRS100 | `test_mrs100_roller_shutter.py`                                                                | F3, F6     |
| BRK-MQTT-001   | Routage MQTT, ACK, ACL, anti-rejeu, fraîcheur             | `broker_agent.py`, `mqtt_integrity.py`            | `test_broker_agent_forwarding.py`, `test_broker_agent_disconnect.py`, `test_mqtt_integrity.py` | F4, F5, F7 |
| BRK-UNBIND-001 | Oubli, révocation MAC, publication Unbind                 | `broker_agent.py`, `blueprints/device.py`         | `test_broker_agent_unbind.py`                                                                  | F7         |
| BRK-CAP-001    | Capture bornée, assainissement, brouillon                 | `capture.py`, `blueprints/admin.py`               | `test_capture.py`                                                                              | F6         |
| BRK-TZ-001     | Fuseau et règles d’heure des appareils                    | `broker_agent.py`, `timezone_utils.py`            | `test_broker_agent_timezone.py`, `test_timezone_utils.py`                                      | F7         |
| BRK-NET-001    | Accès Supervisor/ingress et réseau                        | `nginx`, `blueprints/admin.py`                    | `test_supervisor_network.py`                                                                   | F1, F7     |
| BRK-SEC-001    | Obfuscation et non-fuite des secrets                      | `log_redaction.py`, `logger.py`                   | `test_log_redaction.py`                                                                        | F7         |
| BRK-WEB-001    | Panneau web (comptes, appareils, logs)                    | `addon_web_ui/`                                   | Build Angular + revue manuelle                                                                 | F1         |

## Fonctions → tests

| Fonction / module                       | Test principal                                            |
| --------------------------------------- | --------------------------------------------------------- |
| `ProfileCatalog.load`, surcharges, diff | `test_profiles.py`                                        |
| `profile_lint` schéma et identités      | `test_profile_lint.py`                                    |
| Profil multiprise et template de canal  | `test_profile_lint.py`, `mss425.yaml`                     |
| Signature et clé publique               | `test_profile_signing.py`                                 |
| `CaptureManager` et brouillon           | `test_capture.py`                                         |
| Routage des publications et ACK         | `test_broker_agent_forwarding.py`                         |
| Déconnexion/reconnexion agent           | `test_broker_agent_disconnect.py`                         |
| Unbind et oubli                         | `test_broker_agent_unbind.py`                             |
| Timezone                                | `test_broker_agent_timezone.py`, `test_timezone_utils.py` |
| Intégrité MQTT                          | `test_mqtt_integrity.py`                                  |
| Redaction des journaux                  | `test_log_redaction.py`                                   |
| Roller shutter MRS100                   | `test_mrs100_roller_shutter.py`                           |
| Réseau Supervisor                       | `test_supervisor_network.py`                              |
| API HTTP et contrats                    | `test_http_api.py`                                        |

## Couverture non automatisée

| Élément                  | Moyen de validation                   |
| ------------------------ | ------------------------------------- |
| Interface web Angular    | build CI + checklist manuelle         |
| Volets sur matériel réel | checklist P0 de `FUNCTIONAL-TESTS.md` |
| Autres familles Meross   | catalogue D2b + retours terrain       |
| Compatibilité HA/pairer  | scénarios F1/F8                       |
