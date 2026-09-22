# Extraction — résultats par édition

Exécuté le 20 septembre 2026 avec `scripts/extract_titres.py`, méthode
`position`, sur toutes les éditions récupérables. **Aucun seuil n'a été ajusté
pour faire passer une édition.** Les échecs sont rapportés tels quels : c'est
l'information recherchée.

## Ce que l'API expose

`/wp-json/wp/v2/posts` renvoie **quatre** articles portant une liste de titres.
Un cinquième PDF ressort des recherches — *Décret portant procédures
d'attribution et modalités de gestion des titres miniers* — mais c'est un texte
réglementaire, pas une édition, et il n'est pas traité ici.

L'édition du **30 juin 2025 n'est pas exposée par l'API** : son URL vient du
mainteneur. Total : **cinq éditions**, pas six.

## Résultats

| Édition | Pages | `Producer` | Couche texte | Traits vectoriels | Stratégie | Lignes | Manquants | Doublons | Suspectes | % |
|---|---|---|---|---|---|---|---|---|---|---|
| 30 juin 2025 | 43 | Acrobat Paper Capture | oui | oui | (a) traits | **421** | 1 | 0 | 16 | **3,8 %** |
| 31 octobre 2025 | 45 | `cairo 1.18.0` | **non** | — | *(c) non exécutée* | — | — | — | — | — |
| 31 décembre 2025 | 46 | *(absent)* | oui | **aucun** | (b) abscisses | **391** | 1 | 0 | 13 | **3,3 %** |
| 31 mars 2026 | 45 | Acrobat Paper Capture | oui | oui | (a) traits | **383** | 3 | 0 | 6 | **1,6 %** |
| 30 juin 2026 | 46 | `HP Scan Extended Application` | **non** | — | (c) ocr | 116 | 172 | 0 | 114 | **98,3 %** |

**Trois éditions sur cinq sont exploitables** — celles qui ont une couche texte.
Les deux autres n'en ont aucune : la stratégie (c) les fait passer par l'OCR,
mais son rendement reste trop faible pour être utilisable (98,3 % de lignes
suspectes sur juin 2026, 35 pages rejetées sur 46).

## La cascade de stratégies

Les stratégies sont essayées dans l'ordre, page par page. Chaque enregistrement
porte dans sa colonne `strategie` celle qui a servi : **un utilisateur doit
pouvoir savoir si une donnée vient du texte d'origine ou d'un OCR refait.**

| Stratégie | Condition | État |
|---|---|---|
| `traits` | couche texte + traits verticaux | écrite — la plus fiable |
| `abscisses` | couche texte, aucun trait ; ancrage sur les libellés d'en-tête | écrite |
| `ocr` | aucune couche texte ; OCR complet de l'image | écrite et exécutée — rendement faible, voir ci-dessous |

### Stratégie (c) — OCR, et son prérequis système

(c) ne réinvente aucun découpage. `image_to_data` rend chaque mot avec sa boîte
englobante : exactement ce que consomme (b). La page est rendue avec `to_image()`
que pdfplumber embarque déjà — **ni poppler ni pdf2image**, aucune seconde
dépendance système. Mesuré : 0,11 à 0,16 s par page à 300 ppp.

Chaque mot conserve sa **confiance Tesseract**. Sous le seuil, le champ passe en
suspect ; la valeur n'est jamais corrigée. Les colonnes `<champ>_conf` et
`conf_min` accompagnent chaque enregistrement.

> **Prérequis système : Tesseract, avec la langue `fra`.** Ce n'est pas une
> bibliothèque Python. `pytesseract` n'en est que la liaison. Sur Windows,
> l'exécutable n'est pas ajouté au `PATH` par défaut ; le chemin se donne par
> la variable d'environnement `TESSERACT_CMD`.
>
> ```
> set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
> tesseract --list-langs      # doit lister « fra »
> ```
>
> `--sans-ocr` désactive la stratégie : les pages sans couche texte sont alors
> rejetées, pas devinées.

### Résultat réel sur juin 2026 — la stratégie tourne, le rendement est mauvais

Tesseract 5.4.0 avec `fra`, 300 ppp, 46 pages.

```
OCR              : 124,1 s   (2,70 s/page)
durée totale     : 125,3 s
lignes extraites : 116, toutes marquées « ocr »
pages rejetées   : 35 sur 46
numéros manquants: 172
lignes suspectes : 114 / 116  (98,3 %)
```

**L'OCR lit correctement le corps du tableau.** Exemple brut d'une ligne de
données reconnue :

```
16  4342  TiFORODO  SOLEIL MINING SA  21/05/2024  20/05/2027  BOUSSOU-KOULA
```

**Ce qui échoue, c'est l'ancrage.** (c) délègue le découpage à (b), qui déduit
les bornes des neuf libellés d'en-tête. Ces libellés sont en petits caractères
en haut d'une page scannée, et l'OCR les mutile :

```
p3  : 'N° = CODE DETENTEUR: PROVINCES COMMUNES'        -> 5 libellés sur 9
p26 : 'És SLATUT, 4| R RE REUEEIE ... D'OCTROI DATE'   -> STATUT lu « SLATUT »
p37 : 'STATUT DETENTEUR D'OCTROI DATE D'EXPIRATION ...' -> N°, CODE, NOM absents
```

**Seules 11 pages sur 46 rendent les neuf libellés.** Les 35 autres en rendent
4 à 10, et sont rejetées plutôt que devinées.

Conséquence architecturale : **(c) hérite de la fragilité de (b) précisément là
où l'OCR est le plus faible.** Ancrer le découpage sur du texte reconnu revient
à faire dépendre la structure de la qualité de reconnaissance du plus petit
texte de la page.

Sur les 11 pages qui passent, les bornes varient de 22 à 35 pt — bien au-delà
des 9 pt de dérive mesurés en (a). Une borne médiane de document n'est donc pas
utilisable telle quelle.

Trois pistes, non tranchées :

1. **Réutiliser les bornes d'une page voisine qui passe**, la géométrie étant
   stable à l'intérieur d'une section. Demande de traiter la dérive de scan.
2. **Déduire les bornes des lignes de données** par regroupement en abscisse,
   sans dépendre de l'en-tête. Le corps est mieux reconnu que l'en-tête.
3. **Rapprochement approché des libellés** — « SLATUT » vers « STATUT ». C'est
   une correction au jugé sur l'ancrage ; à considérer avec méfiance.

### État de vérification

Testés : la conversion pixels → points, le filtrage des mots sans confiance, la
cascade complète, le repérage des sections depuis les mots océrisés, la
propagation des confiances et les colonnes CSV. La stratégie tourne de bout en
bout sur juin 2026.

Non mesuré : l'édition du 31 octobre 2025, qui pèse 72,86 Mo.

### Stratégie (b) — ancrage sur les libellés d'en-tête

La page de décembre 2025 ne porte aucun objet vectoriel, mais ses neuf libellés
d'en-tête sont présents et stables en abscisse. Les bornes de colonnes se
déduisent du milieu de l'écart entre deux libellés consécutifs.

Trois points mesurés avant d'être codés :

- **La ligne d'en-tête se repère par son contenu, pas par une bande fixe.** Sur
  les pages courantes elle est à 13 % de la hauteur ; sur les pages d'ouverture
  de section, l'en-tête ministériel la repousse à 43 %. C'est la ligne portant
  le plus de libellés qui sert de repère, où qu'elle se trouve.
- **La fenêtre autour de cette ligne écarte le titre de section**, qui contient
  « DATE » dans « A LA DATE DU 31/12/2025 » et fausserait le découpage.
- **La fusion des libellés ne joue que sur des empans qui se chevauchent.**
  « DATE » est imprimé *dans* l'empan de « D'OCTROI » (écart −39 pt). Toute
  tolérance positive avalerait une vraie séparation : sur la page 33,
  « D'EXPIRATION » et « PROVINCES » ne sont distants que de 8,7 pt.

Le pied de page est retiré par son isolement vertical — 37 à 45 pt le séparent
de la dernière donnée, contre 5 à 15 pt entre deux lignes du tableau. Sans ce
retrait, il se rattacherait au dernier enregistrement et polluerait sa colonne
`COMMUNES`.

## Les deux éditions sans couche texte

### 31 octobre 2025 et 30 juin 2026

Sans OCR — avec `--sans-ocr` — le script s'arrête avant toute extraction, avec
son message dédié. Avec l'OCR, la stratégie (c) prend le relais, pour le
rendement décrit plus haut.

Trois producteurs différents apparaissent selon les éditions — Acrobat Paper
Capture, HP Scan, cairo — ce qui confirme que la chaîne de publication de la
DGCM n'est pas stabilisée. L'octobre 2025 pèse **72,86 Mo**, contre 5 à 26 Mo
pour les autres.

## 31 décembre 2025 — résolu par la stratégie (b)

La couche texte est présente et dense — 770 à 1 129 caractères par page, 128 à
180 mots — mais chaque page porte `lines = 0`, `rects = 0`, `curves = 0` : la
grille du tableau est dans l'image, pas dessinée en vecteurs. `extract_tables()`
rend zéro table, et la stratégie (a) zéro borne.

La stratégie (b) en sort **391 lignes, 1 numéro manquant, 0 doublon, 13 lignes
suspectes (3,3 %)**, réparties sur les neuf sections.

Le seul numéro manquant est le `No=1` de la section 7. Le seul rejet est une
ancre vide, écartée par construction.

Le bruit OCR de cette édition a une signature propre : des fragments du pied
de page migrent dans les cellules de la dernière ligne de chaque page.

```
date d'octroi     : '13/03/2025 Directeur Général'
date d'octroi     : '13/01/2023 dës1 duMérite• SE?'
date d'expiration : "D'EXPlRATION 30/12/2026"
statut            : 'Il Valide'      statut : 'I En renouvellement'
code              : '3751 SIB'
```

Aucune de ces valeurs n'a été corrigée.

### Défaut connu — le pied de page migre dans les cellules

Le retrait du pied de page par isolement vertical élimine la ligne « Page N »,
mais **pas le bloc de signature du Directeur Général**, qui est plus proche du
tableau que le seuil de 30 pt. Ses fragments se rattachent au dernier
enregistrement de la page et polluent ses cellules :

```
date d'octroi : '13/03/2025 Directeur Général'
date d'octroi : '13/01/2023 dës1 duMérite• SE?'
```

**Laissé en l'état, délibérément.** Le défaut est détecté — ces champs
ressortent tous dans les lignes suspectes — donc rien ne passe en silence. Le
corriger demanderait soit un seuil plus agressif, qui couperait de vraies
lignes, soit une reconnaissance du bloc de signature par son contenu, donc une
interprétation.

## L'ordre des sections change d'une édition à l'autre

Les neuf sections sont les mêmes, leur **ordre ne l'est pas** :

| Rang | 30 juin 2025 | 31 mars 2026 |
|---|---|---|
| 1 | Autorisations d'exploitation artisanale / carrières | Permis de recherche |
| 2 | Autorisations d'exploitation artisanale / mines | Permis d'exploitation semi-mécanisée / mines |
| … | … | … |
| 9 | *(271 lignes)* | Permis d'exploitation industrielle permanente / carrières |

Conséquence : **`section_ordre` n'est pas un identifiant stable entre éditions.**
Seul `section_titre`, lu dans le document, l'est — et encore : décembre 2025
écrit « LISTE DES PERMIS DE RECHERCHE **A LA DATE DU** » là où mars 2026 écrit
« **VALIDES A LA DATE DU** ». Tout rapprochement inter-éditions devra passer par
le champ `CODE`, seul identifiant que le mainteneur donne pour stable.

## Qualité comparée des deux éditions lisibles

L'OCR de juin 2025 est nettement plus sale que celui de mars 2026 — 3,8 % de
lignes suspectes contre 1,6 %, et surtout des dégâts d'une autre nature :

| Édition | Statuts hors vocabulaire |
|---|---|
| 31 mars 2026 | 1 — une cellule vide |
| 30 juin 2025 | 4 — dont `val-id-~e - .. _.\c, ctes A,}1/J`, `~ \, • ~ ,•• / . · "f ,·. . : 1` |

Sur juin 2025, le bruit atteint aussi des champs identifiants : un `CODE` sort
en `~.Jt=~`, un autre en `1~·, h •,. U . l / : : :~~ '`. Les caractères
parasites `~ { } \ _ =` touchent nom, détenteur, provinces et communes. Rien
n'a été corrigé.

Répartition des statuts normalisés :

| Statut | 30 juin 2025 | 31 mars 2026 |
|---|---|---|
| `valide` | 310 | 269 |
| `En renouvellement` | 100 | 109 |
| `Suspendu` | **7** | 0 |
| `En cours de renonciation` | 0 | 2 |
| `En Renonciation` | 0 | 1 |
| `Retiré` | 0 | 1 |
| *(hors vocabulaire)* | 4 | 1 |

`Suspendu` n'apparaît que dans juin 2025 ; les trois statuts de renonciation et
de retrait n'apparaissent que dans mars 2026. **Aucune édition seule ne donne le
vocabulaire complet** — ce qui confirme que la liste des statuts est un relevé
cumulatif, jamais clos. Voir `docs/SOURCES.md`.

## Continuité des numéros d'ordre

| Édition | Manquants | Doublons |
|---|---|---|
| 30 juin 2025 | 1 — section 7, `No=1` | 0 |
| 31 mars 2026 | 3 — section 1 `No=224`, section 6 `No=3`, section 9 `No=28` | 0 |

Le `No=3` de la section 6 en mars 2026 est un trou **voulu** : c'est une ancre
vide rejetée, visible par construction plutôt que fondue dans les données.

Juin 2025 sort 421 lignes contre 383 pour mars 2026, dont une section de
271 lignes — l'édition est simplement plus fournie.
