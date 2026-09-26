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

## Besoin exprimé, non satisfaisable par la source actuelle

- **Distinguer l'or du manganèse.** Demandé par le mainteneur le 24 septembre
  2026. **Impossible depuis les listes de la DGCM** : leurs neuf colonnes
  (`No, CODE, NOM, STATUT, DETENTEUR, DATE D'OCTROI, DATE D'EXPIRATION,
  PROVINCES, COMMUNES`) ne portent pas la substance. Les titres de section ne
  séparent que les substances **de mines** de celles **de carrières**.
  La v0.1 fait donc porter la recherche sur la catégorie de titre, et le dit
  dans la description de l'outil et dans `cadastre_list_jurisdictions`.
  Pistes pour y répondre plus tard, aucune vérifiée :
  - les arrêtés d'octroi eux-mêmes, qui nomment la substance — à localiser ;
  - les rapports ITIE Burkina, qui recoupent société et substance ;
  - le géoportail du BUMIGEB.
  Chacune est une source nouvelle, donc une décision de périmètre.

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

## Écarté après mesure — ne pas refaire

- **Débloquer les éditions sans couche texte par la géométrie.** Trois pistes
  essayées et mesurées le 26 septembre 2026, trois échecs : corridors vides
  (1 à 10 par page, inexploitables), calage sur les colonnes de dates (signal
  excellent, 11/11, mais report du gabarit à ±12,2 pt sur des colonnes de
  25,5 pt, et six sections sur neuf sans gabarit disponible), résolution plus
  haute (600 ppp lit moins bien que 300 et coûte 2,5 fois plus).
  Chiffres complets dans `docs/EDITIONS.md`.
  Reste non essayé : un prétraitement d'image avant Tesseract — redressement,
  binarisation, débruitage. C'est la seule piste technique qui ne repose pas
  sur une supposition de structure.
