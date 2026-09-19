# Sources — cadastres miniers d'Afrique de l'Ouest

Recherche effectuée le 19 septembre 2026. Chaque ligne doit être revérifiée
avant mise en production du pays concerné.

## Tableau de couverture

| Pays | Plateforme | Point d'entrée | Endpoint ArcGIS localisé | CGU lues | Statut |
|---|---|---|---|---|---|
| Côte d'Ivoire | Landfolio / FlexiCadastre | portals.landfolio.com/CoteDIvoire | non | non | à sonder |
| Togo | Landfolio | cadastreminier.tg | non | non | à sonder |
| Guinée | Landfolio | guinee.cadastreminier.org | non | non | à sonder |
| RDC | Landfolio | drclicences.cami.cd | non | non | hors périmètre v0.1 |
| Sénégal | Landfolio (annoncé) | à localiser | non | non | à localiser |
| Burkina Faso | spécifique | ecadastreminier.bf | non | non | à sonder |
| Mali | MCAS | référentiel en ligne | non | non | à sonder |

## Détail par pays

### Côte d'Ivoire
Portail cartographique public Landfolio, recherche par code de licence,
substance ou nom de société. Un « e-cadastre minier Côte d'Ivoire » a par
ailleurs été lancé le 22 septembre 2025 pour le dépôt et le suivi des demandes
par les opérateurs — c'est un guichet administratif, pas une source de données
publiques ; ne pas le confondre avec le portail cartographique.

### Burkina Faso
Trois sources distinctes :
- `ecadastreminier.bf` — Direction générale du cadastre minier, procédures et
  catégories de titres. Le code minier a été refondu par la loi n°016-2024/ALT
  du 18 juillet 2024 : les catégories de titres sont donc récentes.
- Le ministère publie des **listes datées de titres valides** (permis
  d'exploitation industrielle de mines et de carrières, autorisations de
  recherche et de prospection, autorisations d'exploitation artisanale et
  semi-mécanisée). Publication périodique à récupérer et à historiser.
- `geoportail.bumigeb.bf` — géoportail géologique et minier du BUMIGEB.

### Mali
Référentiel en ligne du ministère des Mines, ouvert au public, base bilingue
français-anglais. Recherche par numéro de titre, nom de société, type de
permis, statut, substance et région. Système MCAS. L'ITIE Mali renvoie
officiellement vers ce référentiel, ce qui conforte la légitimité de la
consultation — sans valoir licence de rediffusion.

### Le socle technique commun
Landfolio est édité par Spatial Dimension (Afrique du Sud) et repose sur
FlexiCadastre, lui-même adossé à des services ArcGIS REST. Des portails miniers
équivalents (Kenya, Tanzanie) sont publiquement référencés comme services
ArcGIS REST. La digitalisation des cadastres est une tendance continentale :
RDC, Botswana, Togo, Zambie, Sénégal, Tchad et Côte d'Ivoire ont tous adopté
Landfolio.

## Ce qui reste à vérifier avant d'écrire du code

1. **Localiser l'endpoint ArcGIS de chaque portail.** Il apparaît dans les
   requêtes réseau de la carte (onglet Réseau du navigateur, filtrer sur
   `/rest/services`). Utiliser `scripts/probe_arcgis.py` une fois l'URL trouvée.
2. **Lire les conditions d'utilisation de chaque portail.** Un objectif de
   transparence affiché n'est pas une licence de rediffusion. Tant que la
   colonne « CGU lues » est à non, le pays reste hors production.
3. **Relever les noms de champs réels** par juridiction. Ne présumer aucun
   schéma commun, même entre deux portails Landfolio.
4. **Mesurer `maxRecordCount`** sur chaque service : il détermine la stratégie
   de pagination.
