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

| Édition | Pages | `Producer` | Couche texte | Traits vectoriels | Lignes | Manquants | Doublons | Suspectes | % |
|---|---|---|---|---|---|---|---|---|---|
| 30 juin 2025 | 43 | Acrobat Paper Capture | oui | oui | **421** | 1 | 0 | 16 | **3,8 %** |
| 31 octobre 2025 | 45 | `cairo 1.18.0` | **non** | — | — | — | — | — | — |
| 31 décembre 2025 | 46 | *(absent)* | oui | **aucun** | **0** | — | — | — | — |
| 31 mars 2026 | 45 | Acrobat Paper Capture | oui | oui | **383** | 3 | 0 | 6 | **1,6 %** |
| 30 juin 2026 | 46 | `HP Scan Extended Application` | **non** | — | — | — | — | — | — |

**Deux éditions sur cinq sont exploitables.** Les trois autres échouent pour
trois causes distinctes, et chacune échoue bruyamment.

## Les trois échecs

### 31 octobre 2025 et 30 juin 2026 — aucune couche texte

Le script s'arrête avant toute extraction, avec son message dédié. Rien à
tirer de ces fichiers sans OCR.

Trois producteurs différents apparaissent selon les éditions — Acrobat Paper
Capture, HP Scan, cairo — ce qui confirme que la chaîne de publication de la
DGCM n'est pas stabilisée. L'octobre 2025 pèse **72,86 Mo**, contre 5 à 26 Mo
pour les autres.

### 31 décembre 2025 — du texte, mais aucun objet vectoriel

Cas le plus instructif. La couche texte est présente et dense — 770 à 1 129
caractères par page, 128 à 180 mots. Mais sur chaque page :

```
lines = 0    rects = 0    curves = 0    images = 1
extract_tables() = 0
```

**La grille du tableau est dans l'image, pas dessinée en vecteurs.** La méthode
`position` dérive ses colonnes des traits verticaux : sans traits, zéro borne,
et les 46 pages sont rejetées avec le motif `0 bornes de colonnes au lieu de 10`.
`extract_tables()` échoue identiquement, pour la même raison.

Ce n'est donc pas une régression de la méthode par position : aucune des deux
méthodes ne peut lire cette édition en l'état. Une troisième approche —
regroupement des mots par abscisse, sans traits — serait nécessaire. Elle n'est
pas écrite, et ne le sera pas sans arbitrage.

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
