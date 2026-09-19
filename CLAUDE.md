# CLAUDE.md — mining-cadastre-mcp

## Ce qu'est ce projet

Serveur MCP donnant à un agent l'accès aux **cadastres miniers publics
d'Afrique de l'Ouest** : permis de recherche, permis d'exploitation,
autorisations artisanales — titulaires, périmètres, substances, statuts,
échéances.

Aucun serveur MCP minier n'existe, dans aucune région du monde. Vérifié en
septembre 2026.

Mainteneur : SOTECHDI (Ouagadougou, Burkina Faso).

## La découverte qui structure le projet

La majorité des cadastres miniers africains tournent sur **Landfolio /
FlexiCadastre** (éditeur : Spatial Dimension), qui s'appuie sur des
**services ArcGIS REST**. Il existe donc une API interrogeable derrière
chaque carte : endpoints `/query`, réponses JSON, filtrage et pagination.

Conséquence : **un seul client ArcGIS couvre la majorité des pays.** Ce n'est
pas dix intégrations, c'est une intégration plus deux cas particuliers.

| Pays | Plateforme | Point d'entrée connu |
|---|---|---|
| Côte d'Ivoire | Landfolio | portals.landfolio.com/CoteDIvoire |
| Togo | Landfolio | cadastreminier.tg |
| Guinée | Landfolio | guinee.cadastreminier.org |
| RDC | Landfolio | drclicences.cami.cd |
| Sénégal | Landfolio | à localiser |
| Burkina Faso | spécifique | ecadastreminier.bf + geoportail.bumigeb.bf |
| Mali | MCAS | référentiel en ligne bilingue FR/EN |

Détail des sources dans `docs/SOURCES.md`.

## Stack imposée — ne pas proposer d'alternative

- Python 3.11+
- SDK MCP officiel. **Cibler le SDK 2.x (`MCPServer`) dès le départ**, pas
  FastMCP : le projet précédent a été écrit en v1 et doit être migré. On ne
  refait pas cette erreur ici.
- `pydantic` v2, `httpx` asynchrone
- SQLite pour l'historisation — mais **pas en v0.1**
- Transport stdio uniquement en v0.1

Nom du serveur : `mining_cadastre_mcp`.

## Les trois outils de la v0.1 — liste figée

| Outil | Rôle | readOnly |
|---|---|---|
| `cadastre_list_jurisdictions` | Pays couverts, plateforme, statut de couverture | oui |
| `cadastre_search_licences` | Rechercher par société, substance, statut, code | oui |
| `cadastre_get_licence` | Détail d'un titre par son code | oui |

**RÈGLE ABSOLUE : n'ajoute jamais un quatrième outil sans que je le demande.**
Pas de recherche géospatiale par polygone, pas d'export, pas de statistiques
agrégées, pas d'alerte sur expiration. Si tu penses qu'un outil manque, écris-le
dans `docs/BACKLOG.md` et continue.

Les trois outils sont en lecture seule. Ce serveur ne modifie jamais rien.

## Règles de travail

1. **Un outil à la fois, un commit par outil.**
2. **Aucun appel écrit à l'aveugle.** Avant d'implémenter une requête, demande-moi
   la réponse brute réelle du service. Je la colle dans le contexte. Tu codes à
   partir de la réponse observée, jamais d'une supposition.
3. **Tu exécutes ce que tu écris.** `py_compile` ne suffit pas : lance le serveur
   et vérifie qu'il répond au handshake avant de dire que c'est fini.
4. **Pas de dépendance ajoutée** sans me demander.
5. Si une étape te bloque, arrête-toi et pose la question. Ne contourne pas en
   inventant une valeur ou en simulant une réponse.

## Règles propres à ce domaine — non négociables

1. **Sources officielles publiées uniquement.** Portails gouvernementaux et
   publications ministérielles. Rien d'autre.
2. **Aucune donnée provenant d'un employeur ou d'un acteur privé.** Le mainteneur
   travaille dans le secteur minier. Le serveur ne contient que ce qu'un citoyen
   peut consulter librement en ligne.
3. **Conditions d'utilisation vérifiées par portail avant toute ingestion.** Les
   portails affichent un objectif de transparence, ce qui n'est pas une licence.
   `docs/SOURCES.md` porte une colonne « CGU lues » qui doit passer à oui avant
   qu'un pays entre en production.
4. **Citer la source et la date dans chaque réponse d'outil.** Un titre minier a
   des conséquences juridiques et financières. Toute réponse doit indiquer d'où
   vient la donnée et quand elle a été lue.
5. **Ne jamais présenter la donnée comme faisant foi.** Le registre officiel est
   la seule référence opposable. Les descriptions d'outils doivent le dire.
6. **Aucune interprétation.** Le serveur restitue, il ne qualifie pas. Pas de
   « permis suspect », pas de score, pas de rapprochement entre sociétés.

## Conventions de code

- Noms d'outils en `snake_case`, préfixés `cadastre_`.
- Paramètres **à plat**, pas de modèle Pydantic imbriqué sous `params`.
- Annotations MCP sur chaque outil : `title`, `readOnlyHint`, `destructiveHint`,
  `idempotentHint`, `openWorldHint`.
- Retour des outils : JSON sérialisé en `str`, avec un bloc source systématique.
- Messages d'erreur actionnables : dire ce qui a échoué et quoi faire ensuite.
- Toute fonction d'I/O est `async`.

## Spécificités ArcGIS à ne pas sous-estimer

- **`maxRecordCount`** plafonne les résultats, souvent à 1000 ou 2000. Toute
  requête doit paginer avec `resultOffset` et `resultRecordCount`.
- **Noms de champs hétérogènes** d'un pays à l'autre. Prévoir une table de
  correspondance par juridiction, pas un schéma unique supposé.
- **Disponibilité variable.** Ces portails tombent. Timeout court, message clair,
  jamais de plantage du serveur MCP.
- **Ne pas marteler les services.** Un portail public ministériel n'est pas
  dimensionné pour un agent en boucle. Limiter le débit.

## Définition du « terminé » pour la v0.1

- [ ] Les trois outils répondent sur au moins deux juridictions
- [ ] Handshake MCP vérifié en exécution réelle
- [ ] `evals/questions.xml` : 10 questions vérifiées contre le serveur
- [ ] `docs/SOURCES.md` complet, colonne CGU renseignée
- [ ] README en anglais, avec GIF de démonstration
- [ ] Licence MIT

## Hors périmètre v0.1

Recherche géospatiale, historisation SQLite, détection de chevauchements,
alertes d'expiration, données de production, rapports ITIE, pays hors Afrique
de l'Ouest. Tout cela va dans `docs/BACKLOG.md`.
