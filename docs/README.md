# Documentation du broker

## Organisation

- `architecture/` — vue système, décisions structurantes et diagrammes.
- `specs/` — documents normatifs : profils, API, capture, MRS100.
- `design/` — plans de lots, archives de conception et guides d’implémentation.
- `testing/` — stratégie, scénarios fonctionnels et matrice de traçabilité.
- `operations/` — build, publication et procédures d’exploitation.
- `guides/` — guides utilisateur : tuning, surcharge et exemples pas à pas.

Les documents de conception peuvent évoluer ; les fichiers de `specs/` font foi
pour les formats et les contrats.

## Index

### Architecture

- [Vue d’ensemble](architecture/OVERVIEW.md)
- [D0 — Architecture cible](architecture/D0-ARCHITECTURE.md)
- [Diagramme](architecture/arch.drawio)

### Spécifications

- [Auteur de profils](specs/PROFILE-AUTHORING.md)
- [Contrats API](specs/API-CONTRACTS.md)
- [Format de capture](specs/CAPTURE-FORMAT.md)
- [Volets MRS100](specs/MRS100.md)

### Conception

- [D2 — Schéma et moteur](design/D2-PLAN.md)
- [D2.2 — Chemins, matching, compilation](design/D2.2-PLAN.md)
- [D2b — Parité du catalogue](design/D2b-PARITY.md)
- [D4 — Surcharges, capture, rechargement](design/D4-GUIDE.md)
- [Page de tuning des appareils — plan V1 → V2](design/TUNING-PAGE.md)
- [Broker autonome pour HA Container — plan](design/DOCKER-STANDALONE.md)
- [Archive du patch MRS100](design/MRS100_PATCH.md)

### Guides

- [Interface web du broker](guides/WEB-UI.fr.md) · [English](guides/WEB-UI.md)
- [Tuning des appareils](guides/DEVICE-TUNING.fr.md)
- [Ajouter une fonctionnalité sans coder — exemple MRS100](guides/OVERRIDE-MRS100-MOVEMENT.fr.md)
- [Broker sous Home Assistant Container (Docker)](guides/DOCKER.fr.md)

### Tests

- [Stratégie et exécution](testing/TESTING.md)
- [Scénarios fonctionnels F1–F8](testing/FUNCTIONAL-TESTS.md)
- [Matrice de traçabilité](testing/TRACEABILITY.md)
- [Environnement de test Docker (HA Container + broker)](../tests/docker/README.md)
- [Test E2E sous Supervisor réel](../tests/supervisor/README.md)

### Exploitation

- [Construction et publication](operations/BUILDING.md)

### Traductions

- [Politique de traduction](TRANSLATIONS.md)
- [Glossaire français / anglais](TRANSLATION-GLOSSARY.md)

Les documents techniques restent en français pour l’instant ; le README et le
`DOCS.md` de l’add-on sont publiés en anglais avec une version française en
`*.fr.md`.
