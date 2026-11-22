# ADR 001 — Moteur de profils partagé entre l’intégration et le broker

- **Statut** : accepté
- **Date** : 2026-11-22

## Contexte

Les profils d’appareils sont compilés deux fois : par l’intégration Home
Assistant pour créer les entités, et par le broker pour l’aperçu, la
simulation et le catalogue. Deux implémentations divergentes produiraient des
entités, des valeurs ou des commandes différentes pour le même profil, ce qui
rendrait la page de tuning trompeuse.

## Décision

Les modules purs du moteur (`compiler`, `constants`, `match`, `models`,
`paths`, `registry`, `runtime`) sont extraits dans un paquet canonique sans
dépendance Home Assistant. Le broker embarque une copie **octet pour octet**
dans `profile_engine/`, générée par `tools/sync_profile_engine.py`.

- La provenance (commit de l’intégration et hashes) est enregistrée dans
  `profile_engine/UPSTREAM.md`.
- La CI broker épingle le commit de l’intégration, vérifie la synchro des
  fichiers puis exécute les tests de parité.
- Les tests compilent tout le catalogue et rejouent des trames MRS100 de
  référence dans les deux artefacts.
- Les profils déclarent `requires_engine` pour refuser un moteur trop ancien.

## Conséquences

- Un seul comportement de compilation entre Home Assistant et le broker.
- Le broker reste autonome : aucune importation de l’intégration à
  l’exécution, aucune dépendance Home Assistant.
- Toute évolution du moteur passe par l’intégration, puis par une nouvelle
  exécution du script de synchronisation et la mise à jour du commit épinglé.
- Les types et la syntaxe du moteur doivent rester compatibles avec les
  environnements cibles du broker et de l’intégration.

## Alternatives écartées

- **Dupliquer le moteur dans le broker** : dérive garantie et tests de parité
  impossibles à maintenir.
- **Importer l’intégration à l’exécution** : dépendance lourde à Home
  Assistant et couplage des cycles de livraison.
- **Sous-module Git** : complexité de build et de distribution pour un besoin
  de copie statique épinglée.
