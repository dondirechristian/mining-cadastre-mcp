# Backlog

Tout ce qui est hors périmètre v0.1. Claude Code écrit ici au lieu de coder.

## Décidé, plus tard

- Recherche géospatiale : titres dans un rayon, chevauchements — v0.2
- Historisation SQLite : suivre les changements de titulaire et de statut d'une
  édition trimestrielle à l'autre. La clé de jointure existe et est stable —
  c'est le champ `CODE`. C'est l'actif qui prend de la valeur avec le temps — v0.2
- Détection automatique des nouvelles éditions trimestrielles, au-delà de la
  découverte manuelle de `scripts/fetch_titres.py` — v0.2
- Alertes d'expiration de permis — v0.3
- Données de production et rapports ITIE — v0.3
- Deuxième juridiction : Mali, référentiel MCAS — après la v0.1

## Tranché

- **Quelle juridiction en premier ?** Burkina Faso, seul, en v0.1.
  Tranché le 20 septembre 2026.
- **Landfolio comme socle commun ?** Non, écarté. Les services ArcGIS publics
  n'exposent que des couches de contexte ; les titres sont derrière le proxy du
  portail. Vérifié sur Côte d'Ivoire, Guinée et Kenya. Raison complète dans
  `docs/SOURCES.md`.
- **Les portails Landfolio partagent-ils un schéma de champs ?** Question sans
  objet désormais : leurs données de titres ne sont pas accessibles publiquement.
- **Cache local dès la v0.1 ?** Oui, de fait : la source est un fichier
  trimestriel qu'on télécharge une fois et qu'on relit. Il n'y a pas de portail
  à ménager à chaque requête.

## Proposé par l'agent, à arbitrer

<!-- Format : date — outil ou fonctionnalité — justification en une ligne -->

## Questions ouvertes

- Quelle bibliothèque pour l'extraction des tableaux d'un PDF scanné + OCR ?
  C'est une dépendance nouvelle, donc un arbitrage du mainteneur. Bloquant pour
  l'étape suivante.
- Quel taux d'erreur OCR sur un échantillon, et que doivent en dire les réponses
  d'outil ?
- Les neuf listes de l'édition de juin 2026 ont-elles bien la même structure que
  celles de juin 2025 — mêmes colonnes, mêmes valeurs de statut ?
- Que fait le serveur si une nouvelle édition change de gabarit ? Échec clair
  plutôt qu'interprétation de travers, mais reste à définir où le dire.
