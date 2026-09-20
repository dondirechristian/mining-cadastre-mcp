# Sources — v0.1 : Burkina Faso

Recherche initiale le 19 septembre 2026. Périmètre révisé le 20 septembre 2026
après vérification des services ArcGIS publics de trois portails Landfolio.
Source burkinabè caractérisée le 20 septembre 2026.

La v0.1 repose sur **une seule source** : les listes de titres miniers valides
publiées par la Direction générale du cadastre minier (DGCM), Ministère de
l'Énergie, des Mines et des Carrières du Burkina Faso.

## Tableau de couverture

| Pays | Source | Point d'entrée | Format | CGU lues | Statut |
|---|---|---|---|---|---|
| Burkina Faso | Listes de titres valides publiées par la DGCM | ecadastreminier.bf | PDF scanné, OCR selon les éditions | oui — voir réserve ci-dessous | source unique v0.1 |
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

### Publication

| | |
|---|---|
| Autorité | Direction générale du cadastre minier (DGCM), MEMC |
| Page de publication | https://www.ecadastreminier.bf/ |
| Dépôt des fichiers | `wp-content/uploads/AAAA/MM/` |
| Format | **PDF scanné, couche texte OCR présente sur certaines éditions seulement** — voir ci-dessous |
| Périodicité | trimestrielle : 31 mars, 30 juin, 31 octobre, 31 décembre |
| Délai de parution | quelques jours à quelques semaines après la date d'arrêt |
| Nature juridique | actes administratifs publiés (arrêtés) |

Le site est un WordPress. Chaque édition fait l'objet d'un **article** portant le
lien du PDF, ce qui rend la détection des nouvelles éditions fiable via l'API
REST :

```
https://www.ecadastreminier.bf/wp-json/wp/v2/posts?search=titres+miniers+valides
```

Relevé le 20 septembre 2026 — 4 éditions exposées :

| Édition | Article publié le | Nom du fichier PDF |
|---|---|---|
| 30 juin 2026 | 2026-07-10 | `Titres_Miniers_valides_au_30_juin_2026 (1) (1).pdf` |
| 31 mars 2026 | 2026-04-11 | `LISTE DES TITRES MINIERS VALIDES AU 31 MARS 2026.pdf` |
| 31 décembre 2025 | 2026-01-12 | `Liste des TM valides au 31 décembre 2025.pdf` |
| 31 octobre 2025 | 2025-11-12 | `LISTE DES TM VALIDES AU 31 OCTOBRE 2025.pdf` |

**Le nom de fichier n'est pas normalisé** : quatre éditions, quatre conventions
différentes — casse, abréviation « TM », séparateurs, accents, et un suffixe de
ré-upload `(1) (1)` sur l'édition de juin 2026. **Une URL d'édition ne se
construit donc jamais à partir d'une date.** Elle se découvre par l'API REST.
C'est ce que fait `scripts/fetch_titres.py`.

L'édition du **30 juin 2026** — la plus récente — a été téléchargée et vérifiée :
5 559 802 octets (5,30 Mo), PDF 1.7 linéarisé, `sha256`
`3909307b9539c05b3f98c28d982d22d2eb4eb3faf553ec623fc6ad553bde8fdb`.

L'édition de référence sur laquelle la structure ci-dessous a été **vérifiée par
le mainteneur** est celle du 30 juin 2025.

### Structure du document

Un **seul PDF contient neuf listes**, chacune sous son propre numéro d'arrêté :

1. Autorisations d'exploitation artisanale de substances de carrières
2. Autorisations d'exploitation artisanale de substances de mines
3. Autorisations de prospection
4. Autorisations de recherche de gîte de substances de carrières
5. Permis d'exploitation industrielle de mines
6. Permis d'exploitation industrielle permanente de substances de carrières
7. Permis d'exploitation semi-mécanisée de substances de carrières
8. Permis d'exploitation semi-mécanisée de substances de mines
9. Permis de recherche

Colonnes **identiques dans les neuf listes** :

```
No | CODE | NOM | STATUT | DETENTEUR | DATE D'OCTROI | DATE D'EXPIRATION
   | PROVINCES | COMMUNES
```

Règles de lecture, à respecter à la lettre :

| Champ | Règle |
|---|---|
| `CODE` | Identifiant numérique **stable entre éditions**. C'est la clé de jointure. **Ne jamais le reconstruire ni le normaliser.** |
| `STATUT` | Vocabulaire **établi par observation**, voir ci-dessous. Casse telle quelle dans le document. |
| `DATE D'OCTROI`, `DATE D'EXPIRATION` | Format `JJ/MM/AAAA`. |
| `PROVINCES`, `COMMUNES` | Peuvent porter plusieurs valeurs séparées par `/` ou `,`. Conserver **la chaîne brute ET une version découpée**. |

### Le vocabulaire des statuts n'est pas donné, il s'observe

**Aucun document ne publie la liste des valeurs possibles du champ `STATUT`.**
Celle du projet est établie par lecture des éditions, et **elle peut s'allonger
à chaque nouvelle édition**. Ce n'est pas un référentiel, c'est un relevé.

Vocabulaire à ce jour — **six valeurs, toutes trouvées par observation** :

| Valeur | Origine |
|---|---|
| `valide` | sources du mainteneur |
| `En renouvellement` | sources du mainteneur |
| `Suspendu` | sources du mainteneur |
| `En cours de renonciation` | découvert à l'extraction de mars 2026 |
| `En Renonciation` | découvert à l'extraction de mars 2026 (section 4, p31) |
| `Retiré` | découvert à l'extraction de mars 2026 (section 4, p32) — prévu par le code minier |

> **La liste n'est pas close.** Trois des six valeurs ont été découvertes en
> lisant une seule édition. Rien ne garantit que la prochaine n'en apportera
> pas d'autres. Cette table est un relevé daté, pas un référentiel.

`En Renonciation` et `En cours de renonciation` recouvrent la même réalité
d'après le mainteneur, mais sont conservées **comme deux valeurs distinctes** :
les fondre serait interpréter, et la forme imprimée doit rester lisible.

Conséquence pour l'implémentation : le vocabulaire est **fermé au moment de la
lecture** — la normalisation ne rapproche une cellule que d'une valeur déjà
retenue, et tout le reste part au rapport sans être corrigé. Élargir la liste
est une décision du mainteneur, jamais de l'extraction.

La mise en page éclate la cellule `STATUT` : « En » est imprimé au-dessus de
« renouvellement », et l'OCR coupe les mots (`renouvellem ent`,
`renouv E e n ll ement`). La normalisation compare donc les **lettres** de la
cellule, sans tenir compte de l'ordre des mots, de leur découpage, de la casse
ni des accents. **La forme brute est conservée telle qu'imprimée** dans une
colonne distincte : on doit pouvoir savoir ce que le document disait.

### Ancres vides : un trou plutôt qu'un fantôme

Une ligne peut porter un numéro d'ordre isolé sans aucun champ identifiant —
ni code, ni nom, ni détenteur, ni date. Deux cas sur mars 2026 : l'un ne portait
que du bruit OCR en `COMMUNES` (`,. r;;,`), l'autre un `STATUT` seul.

**Ces lignes sont rejetées et signalées, jamais transformées en enregistrement.**
Un fantôme dans les données est pire qu'un trou : un trou se voit dans la
continuité des numéros d'ordre, un fantôme ne se voit plus jamais.

### La contrainte OCR — et l'OCR qui manque

Les documents sont des **scans**. Quand une couche texte existe, elle est le
produit d'une reconnaissance de caractères, pas une donnée saisie : elle porte
des erreurs de lecture.

**Mais la couche texte n'est pas présente sur toutes les éditions.** Vérifié
avec pdfplumber le 20 septembre 2026 :

| Édition | Pages | Pages avec couche texte | Caractères | `Producer` observé |
|---|---|---|---|---|
| 30 juin 2025 | 43 | **43 / 43** | 49 139 | `Adobe Acrobat Pro (64-bit) 24 Paper Capture Plug-in` |
| 31 mars 2026 | 45 | **45 / 45** | 46 036 | `Adobe Acrobat Pro (64-bit) 24 Paper Capture Plug-in` |
| 30 juin 2026 | 46 | **0 / 46** | **0** | `HP Scan Extended Application` |

L'édition du **30 juin 2026 n'a aucune couche texte** : 46 pages, 46 images,
zéro caractère. `extract_tables()` n'y détecte rien. Sur l'édition de mars 2026,
`Creator` vaut `HP Scan` mais `Producer` vaut Paper Capture — le module OCR
d'Acrobat.

> **Interprétation, pas constat.** La lecture la plus simple de ces métadonnées
> est que l'OCR est une étape manuelle côté DGCM, appliquée aux éditions
> précédentes et omise sur celle de juin 2026. Ce n'est qu'une interprétation :
> rien ne permet de savoir ce qui s'est passé dans leur chaîne de publication,
> ni si une version OCRisée sera republiée.

Conséquences, arbitrées le 20 septembre 2026 :

- **La v0.1 s'appuie sur l'édition du 31 mars 2026**, la plus récente qui soit
  exploitable. Juin 2026 est traité comme une anomalie, pas comme le cas nominal.
- **Pas de Tesseract.** Une édition sur quatre sans couche texte ne justifie pas
  d'engager une dépendance système. `scripts/extract_titres.py` détecte l'absence
  de couche texte, s'arrête, et dit pourquoi.

Le bruit OCR, lui, reste entier là où la couche existe :

- une erreur d'OCR sur un `CODE` ou sur une date **ne se corrige pas
  silencieusement** — la règle « aucune interprétation » l'interdit ;
- la règle « ne jamais présenter la donnée comme faisant foi » vaut ici deux
  fois : à l'écart habituel entre une liste publiée et le registre s'ajoute
  l'incertitude de reconnaissance ;
- les réponses d'outil devront le dire explicitement.

### Conditions d'utilisation

Le site ne porte **pas de mention restrictive identifiée**. Les listes sont des
actes administratifs publiés par la DGCM dans un objectif déclaré de transparence
et de traçabilité.

> **Réserve explicite.** Cette lecture est celle du mainteneur, confirmée par lui
> le 20 septembre 2026. Ce n'est **pas une licence explicite** : aucun texte du
> site n'accorde formellement un droit de rediffusion. L'absence de mention
> restrictive n'est pas une autorisation écrite. À revoir si le site publie des
> conditions d'utilisation.

## Mali — hors périmètre v0.1

Référentiel en ligne du ministère des Mines, ouvert au public, bilingue
français-anglais, système MCAS. Recherche par numéro de titre, société, type de
permis, statut, substance, région. L'ITIE Mali y renvoie officiellement — ce qui
conforte la légitimité de la consultation, sans valoir licence de rediffusion.

Candidat n°1 pour la deuxième juridiction, une fois le Burkina Faso livré.

## Ce qui reste à faire

1. **Nettoyage du bruit OCR** — étape suivante. L'extraction est écrite
   (`scripts/extract_titres.py`) et ne corrige rien volontairement : 384 lignes
   sorties sur l'édition de mars 2026, dont 203 portent au moins un champ
   signalé comme suspect, et 22 lignes d'en-tête ont absorbé des données
   d'enregistrement. Le traitement de ce bruit se décide au vu du rapport
   d'extraction, pas avant.
2. **Mesurer le taux d'erreur OCR réel** sur un échantillon relu à la main.
   Les compteurs de l'extraction mesurent la géométrie et le format, pas la
   justesse d'un nom ou d'un code.
3. **Surveiller si la DGCM republie une version OCRisée de juin 2026.** Si les
   éditions suivantes arrivent sans couche texte, la question Tesseract se
   reposera — elle n'est pas tranchée, seulement repoussée.
4. **Décider du comportement entre deux éditions** : la v0.1 sert la dernière
   liste exploitable. Le suivi des changements d'une édition à l'autre relève de
   l'historisation, donc de la v0.2.
