# Sources — v0.1 : Burkina Faso

Recherche initiale le 19 septembre 2026. Périmètre révisé le 20 septembre 2026
après vérification des services ArcGIS publics de trois portails Landfolio.

La v0.1 repose sur **une seule source** : les listes de titres miniers valides
publiées par le Ministère de l'Énergie, des Mines et des Carrières du Burkina
Faso.

## Tableau de couverture

| Pays | Source | Point d'entrée | Format relevé | CGU lues | Statut |
|---|---|---|---|---|---|
| Burkina Faso | Listes de titres valides publiées par le MEMC | à renseigner | non | non | source unique v0.1 |
| Côte d'Ivoire | Landfolio | portals.landfolio.com/CoteDIvoire | — | — | **écarté** |
| Guinée | Landfolio | guinee.cadastreminier.org | — | — | **écarté** |
| Togo | Landfolio | cadastreminier.tg | — | — | **écarté** |
| Sénégal | Landfolio (annoncé) | à localiser | — | — | **écarté** |
| RDC | Landfolio | drclicences.cami.cd | — | — | **écarté** |
| Mali | MCAS | référentiel en ligne | — | — | hors périmètre v0.1 |

## Pourquoi Landfolio est écarté

Vérification menée sur trois pays — **Côte d'Ivoire, Guinée, Kenya**. Résultat
identique dans les trois cas :

- les services ArcGIS REST accessibles publiquement ne contiennent que des
  **couches de contexte** (fonds de carte, limites administratives, hydrographie,
  géologie) ;
- les **couches de titres miniers** — permis de recherche, permis
  d'exploitation, autorisations — résident dans un **dossier non listé du
  serveur**, protégé par jeton, et ne sont atteignables qu'à travers le **proxy
  du portail** ;
- il n'existe donc pas d'API publique interrogeable pour les titres.

**Décision : on n'y touche pas.** Contourner un jeton ou passer par le proxy
d'authentification d'un portail sortirait du cadre « ce qu'un citoyen peut
consulter librement en ligne » posé par les règles de domaine du projet. Les
lignes Landfolio restent au tableau pour mémoire, sans être une piste de travail.

Conséquence directe : l'hypothèse « un seul client ArcGIS couvre la majorité des
pays » tombe. Il n'y a pas de socle technique commun exploitable. Chaque
juridiction redevient une intégration distincte, à partir de ce que le ministère
concerné publie effectivement.

## Burkina Faso — source unique de la v0.1

Le Ministère de l'Énergie, des Mines et des Carrières publie **des listes datées
de titres miniers valides**. Ce sont des documents publiés, pas un service
interrogeable : la v0.1 les récupère, les lit et les restitue telles quelles.

Catégories attendues dans ces listes :

- permis d'exploitation industrielle de mines ;
- permis d'exploitation industrielle de carrières ;
- autorisations de recherche et de prospection ;
- autorisations d'exploitation artisanale et semi-mécanisée.

Éléments à établir avant d'écrire la moindre ligne de client :

| Point | Statut |
|---|---|
| URL de la page de publication | **à fournir par le mainteneur** |
| URL du dernier fichier publié | **à fournir par le mainteneur** |
| Format du fichier (PDF, XLSX, CSV, HTML) | **à fournir par le mainteneur** |
| Périodicité de publication | inconnue |
| Noms de colonnes réels | inconnus — à relever sur le fichier réel |
| Valeurs possibles du champ statut | inconnues |
| Format des dates (octroi, expiration) | inconnu |
| Conditions d'utilisation du site | **non lues** |

Tant que la colonne « CGU lues » est à **non**, le Burkina Faso ne passe pas en
production. C'est la règle de domaine n°3, elle n'a pas changé avec le périmètre.

`scripts/fetch_titres.py` sert à récupérer le fichier publié et à décrire ce
qu'il contient. Il ne présume aucun format : il est complété une fois l'URL et
le format réels connus.

### Contexte réglementaire

Le code minier burkinabè a été refondu par la **loi n°016-2024/ALT du 18 juillet
2024**. Les catégories de titres et leur nomenclature sont donc récentes : ne pas
les rapprocher d'anciennes listes sans vérification.

### Autres sources burkinabè — connues, non retenues en v0.1

- `ecadastreminier.bf` — Direction générale du cadastre minier. Procédures et
  catégories de titres. Pas identifié à ce jour comme fournissant une liste
  téléchargeable de titres ; à réexaminer après la v0.1.
- `geoportail.bumigeb.bf` — géoportail géologique et minier du BUMIGEB. Données
  géologiques, pas un registre de titres.

## Mali — hors périmètre v0.1

Référentiel en ligne du ministère des Mines, ouvert au public, bilingue
français-anglais, système MCAS. Recherche par numéro de titre, société, type de
permis, statut, substance, région. L'ITIE Mali y renvoie officiellement — ce qui
conforte la légitimité de la consultation, sans valoir licence de rediffusion.

Candidat n°1 pour la deuxième juridiction, une fois le Burkina Faso livré.

## Ce qui reste à faire avant d'écrire du code

1. **Obtenir l'URL de publication et le format réel** du dernier fichier de
   titres valides du MEMC. Rien ne se code avant.
2. **Lire les conditions d'utilisation** du site de publication. Un objectif de
   transparence affiché n'est pas une licence de rediffusion.
3. **Relever les noms de colonnes réels** sur le fichier téléchargé, et les
   valeurs effectivement présentes dans le champ statut.
4. **Établir la périodicité** de publication et la manière dont une nouvelle
   liste remplace la précédente — c'est ce qui déterminera plus tard la
   stratégie d'historisation (v0.2).
