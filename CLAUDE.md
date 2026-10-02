# CLAUDE.md — mining-cadastre-mcp

## Ce qu'est ce projet

Serveur MCP donnant à un agent l'accès aux **cadastres miniers publics
d'Afrique de l'Ouest** : permis de recherche, permis d'exploitation,
autorisations artisanales — titulaires, périmètres, substances, statuts,
échéances.

Aucun serveur MCP minier n'existe, dans aucune région du monde. Vérifié en
septembre 2026.

Mainteneur : SOTECHDI (Ouagadougou, Burkina Faso).

## Périmètre v0.1 — un seul pays, une seule source

**Burkina Faso, à partir des listes de titres miniers valides publiées par le
Ministère de l'Énergie, des Mines et des Carrières.** Rien d'autre.

Ce sont des **documents publiés**, pas un service interrogeable : la v0.1 les
récupère, les lit et les restitue. L'URL et le format réels sont fournis par le
mainteneur — ils ne se devinent pas.

Détail de la source dans `docs/SOURCES.md`.

### Landfolio est écarté

L'hypothèse de départ était qu'un seul client ArcGIS couvrirait la majorité des
pays, Landfolio / FlexiCadastre reposant sur des services ArcGIS REST.

Vérification faite sur **Côte d'Ivoire, Guinée et Kenya** : les services ArcGIS
publics ne contiennent que des **couches de contexte**. Les titres miniers sont
dans un **dossier non listé, protégé par jeton**, atteignable seulement via le
proxy du portail. **On n'y touche pas** — ce serait sortir de « ce qu'un citoyen
peut consulter librement en ligne ».

Conséquence : il n'y a pas de socle technique commun. Pas de client ArcGIS, pas
de table de correspondance multi-pays, pas de sondage de portail. Ces pays
restent au tableau de `docs/SOURCES.md` pour mémoire, pas comme piste de travail.

Une deuxième juridiction viendra après la v0.1, à partir de ce que son ministère
publie réellement — le Mali est le candidat n°1.

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

Inchangée. Le périmètre géographique se réduit, pas la surface d'outils.

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

`cadastre_list_jurisdictions` reste dans la liste avec une seule juridiction
couverte : c'est lui qui dit à l'agent ce qui est couvert et ce qui ne l'est pas.

## Règles de travail

1. **Un outil à la fois, un commit par outil.**
2. **Aucun appel écrit à l'aveugle.** Avant d'implémenter une requête, demande-moi
   la réponse brute réelle du service. Je la colle dans le contexte. Tu codes à
   partir de la réponse observée, jamais d'une supposition.
3. **Tu exécutes ce que tu écris.** `py_compile` ne suffit pas : lance le serveur
   et vérifie qu'il répond au handshake avant de dire que c'est fini.
4. **Pas de dépendance ajoutée** sans me demander. Lire un PDF ou un XLSX
   demande une bibliothèque : c'est une question à poser, pas une décision à
   prendre.
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
   vient la donnée et quand elle a été lue. Pour une liste publiée, citer aussi
   **la date de publication de la liste**, distincte de la date de lecture.
5. **Ne jamais présenter la donnée comme faisant foi.** Le registre officiel est
   la seule référence opposable. Les descriptions d'outils doivent le dire.
6. **Aucune interprétation.** Le serveur restitue, il ne qualifie pas. Pas de
   « permis suspect », pas de score, pas de rapprochement entre sociétés.
7. **Aucun accès protégé.** Pas de jeton, pas de proxy de portail, pas de
   contournement d'authentification. Si une donnée n'est pas accessible en clair
   à un visiteur, elle est hors périmètre — définitivement, pas jusqu'à ce qu'on
   trouve un moyen.

## Conventions de code

- Noms d'outils en `snake_case`, préfixés `cadastre_`.
- Paramètres **à plat**, pas de modèle Pydantic imbriqué sous `params`.
- Annotations MCP sur chaque outil : `title`, `readOnlyHint`, `destructiveHint`,
  `idempotentHint`, `openWorldHint`.
- Retour des outils : JSON sérialisé en `str`, avec un bloc source systématique.
- Messages d'erreur actionnables : dire ce qui a échoué et quoi faire ensuite.
- Toute fonction d'I/O est `async`.

## Spécificités de la source à ne pas sous-estimer

- **Le format n'est pas connu et ne se suppose pas.** PDF, XLSX, CSV, page HTML :
  tant que le mainteneur n'a pas fourni le fichier réel, rien ne se parse.
- **Les noms de colonnes sont ceux du document**, pas un schéma inventé. Les
  relever sur le fichier réel.
- **Une liste est datée.** Elle est valable à sa date de publication, pas
  aujourd'hui. Ne jamais laisser croire qu'une réponse reflète l'état du jour.
- **Une nouvelle liste remplace la précédente** sans forcément suivre le même
  gabarit. Le parseur doit échouer clairement plutôt que d'interpréter de
  travers.
- **Disponibilité variable.** Un site ministériel tombe. Timeout court, message
  clair, jamais de plantage du serveur MCP.
- **Ne pas marteler le site.** Un portail public ministériel n'est pas
  dimensionné pour un agent en boucle. Limiter le débit, et préférer une lecture
  du fichier déjà téléchargé.

## Définition du « terminé » pour la v0.1

Vérifié par exécution le 2 octobre 2026 — `python scripts/run_evals.py`.

- [x] Les trois outils répondent sur le Burkina Faso
- [x] Handshake MCP vérifié en exécution réelle
- [x] `evals/questions.xml` : 10 questions vérifiées contre le serveur
- [x] `docs/SOURCES.md` complet, colonne CGU renseignée
- [x] README en anglais, avec GIF de démonstration
- [x] Licence MIT

Détail de la vérification :

| Case | Constat |
|---|---|
| Trois outils | `cadastre_list_jurisdictions`, `cadastre_search_licences`, `cadastre_get_licence` — 383 titres de l'édition du 31 mars 2026 |
| Handshake | `mining_cadastre_mcp 0.1.0`, protocole `2025-11-25`, session stdio réelle |
| Évaluations | 10 / 10, 41 assertions, dont 5 pièges où le serveur doit refuser de répondre |
| SOURCES.md | colonne « CGU lues » = `oui — voir réserve ci-dessous` pour le Burkina ; la réserve dit que ce n'est pas une licence explicite |
| README | anglais, section française en pied ; `docs/demo.gif` présent, 49 images, 880 Ko |
| Licence | `LICENSE` présent, 24 lignes, MIT ; `pyproject.toml` concordant ; note distinguant le logiciel des données |

Le GIF n'est pas une capture d'écran : `scripts/demo.py` joue une vraie session
MCP et journalise ce qu'elle affiche, `scripts/make_demo_gif.py` en dessine les
images. Le contenu vient d'une exécution réelle, le rendu est reproductible, et
rien n'a été rejoué de mémoire.

## Hors périmètre v0.1

Tout pays autre que le Burkina Faso. Landfolio et tout accès ArcGIS. Recherche
géospatiale, historisation SQLite, détection de chevauchements, alertes
d'expiration, données de production, rapports ITIE. Tout cela va dans
`docs/BACKLOG.md`.
