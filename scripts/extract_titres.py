"""
Extraction des tableaux d'une édition des listes de titres miniers valides.

Écrit à partir de l'édition du 31 mars 2026, observée — pas supposée.

DEUX MÉTHODES, COMPARABLES
  `position` (défaut) — découpe par coordonnées. Les colonnes viennent des
      traits verticaux de CHAQUE page, les lignes du regroupement des mots sur
      leur ordonnée. Mesuré sur mars 2026 : 10 traits verticaux sur les 45
      pages, mais des abscisses qui changent d'une section à l'autre (la 3e
      borne passe de 97 en section 5 à 164 en section 7) et qui dérivent de
      ~9 pt à l'intérieur de la section 1. D'où des bornes relues page par page,
      jamais un gabarit figé.
  `tables` — l'ancienne méthode, `page.extract_tables()`. Conservée pour
      comparaison, pas pour la production.

  `--comparer` exécute les deux et met les résultats côte à côte.

CE QUI EST CONSERVÉ
  Chaque cellule figure DEUX FOIS : `_brut` avec ses retours à la ligne
  internes, `_plat` avec les retours à la ligne remplacés par une espace.

CE QUE CE SCRIPT NE FAIT PAS
  Aucune correction de valeur. Le document est un scan OCRisé : « KOTl2 »,
  « KABOUi », « renouvellem ent » sortent tels quels. On répare le découpage,
  jamais le texte. Les champs douteux sont SIGNALÉS, jamais réparés.

USAGE
    python scripts/extract_titres.py <chemin.pdf>
    python scripts/extract_titres.py <chemin.pdf> --methode tables
    python scripts/extract_titres.py <chemin.pdf> --comparer
"""

import argparse
import csv
import os
import re
import time
import unicodedata
from collections import Counter
from pathlib import Path

import pdfplumber

# Chemin de l'exécutable Tesseract, si absent du PATH. Sur Windows il n'y est
# pas toujours : TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
TESSERACT_CMD = os.environ.get("TESSERACT_CMD", "")

COLONNES = [
    "no",
    "code",
    "nom",
    "statut",
    "detenteur",
    "date_octroi",
    "date_expiration",
    "provinces",
    "communes",
]

# Sans au moins l'un de ces champs, il n'y a pas de titre identifiable.
# Ni STATUT, ni PROVINCES, ni COMMUNES n'identifient un titre à eux seuls.
COLONNES_IDENTIFIANTES = ("code", "nom", "detenteur", "date_octroi", "date_expiration")

MOTIF_SECTION = re.compile(r"^LISTE\s+DES\s+", re.I)
MOTIF_FIN_SECTION = re.compile(r"VALIDES?\s+A\s+LA\s+DATE\s+DU", re.I)

MOTS_ENTETE = ("CODE", "NOM", "STATUT", "DETENTEUR")
# Vocabulaire complet d'une ligne d'en-tête. Une ligne dont TOUS les mots sont
# ici est un en-tête ou un fragment d'en-tête, où qu'elle se trouve.
VOCABULAIRE_ENTETE = {
    "NO", "N°", "CODE", "NOM", "STATUT", "DETENTEUR", "DATE",
    "D'OCTROI", "D'EXPIRATION", "PROVINCES", "COMMUNES",
}

MOTIF_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
MOTIF_CODE = re.compile(r"^\d+$")
CARACTERES_SUSPECTS = set("|\\~^`{}[]<>_@#$%*+=")

# Vocabulaire des statuts, arbitré par le mainteneur. Fermé au moment de la
# lecture — une cellule ne se rapproche que d'une de ces valeurs — mais
# LA LISTE N'EST PAS CLOSE : elle est établie par observation et s'allonge à
# mesure des éditions. « En cours de renonciation », « En Renonciation » et
# « Retiré » ont tous trois été découverts à l'extraction de mars 2026.
# L'élargir est une décision du mainteneur, jamais de l'extraction.
# Voir docs/SOURCES.md.
STATUTS_CANONIQUES = (
    "valide",
    "En renouvellement",
    "Suspendu",
    "En cours de renonciation",
    "En Renonciation",
    "Retiré",
)

# Paramètres géométriques, tous mesurés sur mars 2026 avant d'être codés.
TOLERANCE_BORNE = 6.0     # regroupe les traits verticaux doublés
X_MINI_BORNE = 20.0       # écarte le trait de bord de page (vu sur 4 pages)
NB_BORNES = 10            # 9 colonnes
ECART_LIGNE = 5.0         # au-delà, deux mots sont sur deux lignes visuelles
MARGE_BOITE = 3.0         # tolérance sur la boîte du tableau

# Stratégie (b) — sans traits. Paramètres mesurés sur l'édition de décembre 2025
# avant d'être codés, jamais ajustés après coup pour faire passer un fichier.
# « DATE » est imprimé DANS l'empan de « D'OCTROI » (écart -39 pt) : la fusion
# ne doit donc jouer que sur des empans qui se chevauchent. Toute tolérance
# positive avalerait une vraie séparation — sur la page 33 de décembre 2025,
# « D'EXPIRATION » et « PROVINCES » ne sont séparés que de 8,7 pt.
FUSION_LIBELLE = 0.0
MARGE_COLONNE = 8.0       # débord de part et d'autre du 1er et du dernier libellé
FENETRE_ENTETE = 20.0     # les libellés tiennent sur 3 lignes, y=250 à y=265
MINI_LIBELLES = 5         # en deçà, la ligne n'est pas la ligne d'en-tête
ECART_PIED_PAGE = 30.0    # mesuré : 37 à 45 pt entre dernière donnée et « Page N »

# Stratégie (c) — OCR. Ne réinvente aucun découpage : Tesseract rend chaque mot
# avec sa boîte englobante, exactement ce que consomme (b).
RESOLUTION_OCR = 300      # points par pouce du rendu envoyé à Tesseract
LANGUE_OCR = "fra"
SEUIL_CONFIANCE = 60.0    # en deçà, le champ passe en suspect — jamais corrigé
CONFIANCE_TEXTE = 100.0   # une couche texte d'origine n'a pas de confiance OCR


def aplatir(valeur: str | None) -> str:
    if valeur is None:
        return ""
    return re.sub(r"\s*\n\s*", " ", valeur).strip()


def brut(valeur: str | None) -> str:
    return "" if valeur is None else valeur


def _lettres(texte: str) -> str:
    """Lettres nues, sans accents, sans espaces, en minuscules."""
    sans_accent = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return "".join(c for c in sans_accent.lower() if c.isalpha())


_EMPREINTES_STATUT = {
    "".join(sorted(_lettres(s))): s for s in STATUTS_CANONIQUES
}


def normaliser_statut(valeur: str) -> str | None:
    """Rend le statut canonique correspondant, ou None.

    La mise en page éclate la cellule : « En » est imprimé au-dessus de
    « renouvellement », et l'OCR coupe les mots (« renouvellem ent »,
    « renouv E e n ll ement »). On compare donc les LETTRES de la cellule,
    indépendamment de l'ordre des mots, de leur découpage, de la casse et
    des accents — sans quoi le problème revient à chaque édition.

    Ce qui ne correspond à aucune valeur du vocabulaire revient None et part
    au rapport. Rien n'est corrigé au jugé.

    La forme brute est conservée telle qu'imprimée dans `statut_brut` et
    `statut_plat` : on doit pouvoir savoir ce que le document disait.
    """
    empreinte = "".join(sorted(_lettres(valeur)))
    return _EMPREINTES_STATUT.get(empreinte)


def nom_fichier(texte: str) -> str:
    sans_accent = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", sans_accent.lower()).strip("_")[:80]


# --------------------------------------------------------------------------
# Couche texte et sections — communes aux deux méthodes
# --------------------------------------------------------------------------

def verifier_couche_texte(pdf, chemin: Path) -> None:
    total = sum(len(page.chars) for page in pdf.pages)
    if total > 0:
        return
    producer = (pdf.metadata or {}).get("Producer", "(non déclaré)")
    raise SystemExit(
        f"\nAUCUNE COUCHE TEXTE dans {chemin.name}\n"
        f"  {len(pdf.pages)} pages, 0 caractère, Producer = {producer!r}\n\n"
        "Ce fichier est un scan qui n'est jamais passé à l'OCR. pdfplumber ne\n"
        "peut rien en tirer : il n'y a pas de texte dégradé à lire, il n'y a pas\n"
        "de texte du tout. Ce n'est pas un défaut du script.\n\n"
        "C'est le cas de l'édition du 30 juin 2026. L'OCR est une étape manuelle\n"
        "côté DGCM, appliquée aux éditions précédentes et omise sur celle-ci.\n\n"
        "Que faire :\n"
        "  - se rabattre sur la dernière édition exploitable, celle du\n"
        "    31 mars 2026, listée par : python scripts/fetch_titres.py --list\n"
        "  - vérifier si la DGCM a republié une version OCRisée depuis\n"
        "  - ne PAS engager Tesseract sans arbitrage : c'est une dépendance\n"
        "    système, pas une bibliothèque Python.\n"
    )


def reperer_sections(pdf, cache: dict | None = None, avec_ocr: bool = False) -> list[dict]:
    sections = []
    for page in pdf.pages:
        lignes = (
            lignes_texte(page, cache, avec_ocr)
            if cache is not None
            else [l.strip() for l in (page.extract_text() or "").splitlines()]
        )
        for i, ligne in enumerate(lignes):
            if not MOTIF_SECTION.match(ligne):
                continue
            titre = ligne
            if not MOTIF_FIN_SECTION.search(titre) and i + 1 < len(lignes):
                titre = f"{titre} {lignes[i + 1].strip()}"
            sections.append(
                {"titre_brut": titre, "page_debut": page.page_number, "entete_page": lignes[:i]}
            )
            break
    for rang, section in enumerate(sections):
        section["page_fin"] = (
            sections[rang + 1]["page_debut"] - 1 if rang + 1 < len(sections) else len(pdf.pages)
        )
        section["ordre"] = rang + 1
    return sections


def section_de_page(sections: list[dict], numero: int) -> dict | None:
    courante = None
    for section in sections:
        if section["page_debut"] <= numero:
            courante = section
        else:
            break
    return courante


# --------------------------------------------------------------------------
# Méthode `position`
# --------------------------------------------------------------------------

def traits_verticaux(page) -> list[dict]:
    return [
        l for l in page.lines
        if abs(l["x0"] - l["x1"]) < 2 and abs(l["top"] - l["bottom"]) > 20
        and l["x0"] > X_MINI_BORNE
    ]


def bornes_colonnes(traits: list[dict]) -> list[float]:
    """Regroupe les traits verticaux doublés en bornes de colonnes."""
    grappes: list[float] = []
    courante: list[float] = []
    for x in sorted(t["x0"] for t in traits):
        if courante and x - courante[-1] > TOLERANCE_BORNE:
            grappes.append(sum(courante) / len(courante))
            courante = []
        courante.append(x)
    if courante:
        grappes.append(sum(courante) / len(courante))
    return grappes


def boite_tableau(traits: list[dict]) -> tuple[float, float]:
    """Étendue verticale du tableau, donnée par les traits eux-mêmes.

    Sert à écarter l'en-tête ministériel et le numéro de page, qui tombent
    hors de la boîte. Positionnel, donc aucune lecture du texte.
    """
    return (
        min(t["top"] for t in traits) - MARGE_BOITE,
        max(t["bottom"] for t in traits) + MARGE_BOITE,
    )


def mots_du_texte(page) -> list[dict]:
    """Mots de la couche texte d'origine, au format commun aux trois stratégies."""
    mots = page.extract_words()
    for mot in mots:
        mot["conf"] = CONFIANCE_TEXTE
    return mots


def mots_ocr(page, resolution: int = RESOLUTION_OCR) -> list[dict]:
    """Stratégie (c) : rend la page en image et l'OCRise, avec les positions.

    Le rendu passe par `to_image()`, que pdfplumber embarque déjà — donc pas de
    poppler ni de pdf2image, aucune seconde dépendance système.

    `image_to_data` rend chaque mot avec sa boîte englobante et sa confiance.
    Les boîtes sont en pixels du rendu : elles sont ramenées en points PDF pour
    que la suite du traitement soit exactement celle de (b).

    La confiance est conservée mot par mot. Elle ne corrige rien : elle fait
    passer un champ en suspect.
    """
    try:
        import pytesseract  # importé ici : inutile tant qu'aucune page n'en a besoin
    except ImportError:
        raise SystemExit(
            "pytesseract n'est pas installé.\n"
            "  pip install pytesseract\n"
            "C'est la liaison Python ; le moteur Tesseract lui-même est un "
            "prérequis système, à installer séparément avec la langue « fra »."
        )

    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD

    image = page.to_image(resolution=resolution).original
    echelle = 72.0 / resolution
    try:
        donnees = pytesseract.image_to_data(
            image, lang=LANGUE_OCR, output_type=pytesseract.Output.DICT
        )
    except (pytesseract.TesseractNotFoundError, OSError):
        raise SystemExit(
            f"Tesseract est introuvable (commande essayée : "
            f"{pytesseract.pytesseract.tesseract_cmd!r}).\n\n"
            "La stratégie OCR en a besoin : c'est un prérequis SYSTÈME, pas une\n"
            "bibliothèque Python. Sur Windows il n'est pas ajouté au PATH par\n"
            "défaut. Indiquer son chemin :\n\n"
            '    set TESSERACT_CMD=C:\\Program Files\\Tesseract-OCR\\tesseract.exe\n\n'
            "Vérifier aussi que la langue « fra » est installée :\n"
            "    tesseract --list-langs\n\n"
            "Pour extraire sans OCR — les pages sans couche texte seront alors\n"
            "rejetées, pas devinées :\n"
            "    python scripts/extract_titres.py <pdf> --sans-ocr"
        )
    except pytesseract.TesseractError as exc:
        raise SystemExit(
            f"Tesseract a échoué : {exc}\n"
            f"Vérifier que la langue {LANGUE_OCR!r} est installée : tesseract --list-langs"
        )

    mots = []
    for i, texte in enumerate(donnees["text"]):
        if not texte.strip():
            continue
        try:
            conf = float(donnees["conf"][i])
        except (TypeError, ValueError):
            conf = -1.0
        if conf < 0:
            continue
        gauche, haut = donnees["left"][i], donnees["top"][i]
        mots.append(
            {
                "text": texte,
                "x0": gauche * echelle,
                "x1": (gauche + donnees["width"][i]) * echelle,
                "top": haut * echelle,
                "bottom": (haut + donnees["height"][i]) * echelle,
                "conf": conf,
            }
        )
    return mots


def cache_ocr_neuf() -> dict:
    """Mémoire des pages déjà océrisées. Une page n'est OCRisée qu'une fois,
    et le même résultat sert au repérage des sections et à l'extraction."""
    return {"mots": {}, "duree": 0.0, "pages": 0}


def mots_ocr_caches(page, cache: dict) -> list[dict]:
    numero = page.page_number
    if numero not in cache["mots"]:
        debut = time.perf_counter()
        cache["mots"][numero] = mots_ocr(page)
        cache["duree"] += time.perf_counter() - debut
        cache["pages"] += 1
    return cache["mots"][numero]


def lignes_de_mots(mots: list[dict]) -> list[str]:
    """Reconstitue des lignes de texte à partir de mots positionnés."""
    groupes: list[list[dict]] = []
    for mot in sorted(mots, key=lambda w: (w["top"], w["x0"])):
        if groupes and mot["top"] - groupes[-1][-1]["top"] <= ECART_LIGNE:
            groupes[-1].append(mot)
        else:
            groupes.append([mot])
    return [
        " ".join(m["text"] for m in sorted(g, key=lambda w: w["x0"])) for g in groupes
    ]


def lignes_texte(page, cache: dict, avec_ocr: bool) -> list[str]:
    """Lignes de texte de la page : couche d'origine, ou OCR si elle est vide."""
    lignes = [l.strip() for l in (page.extract_text() or "").splitlines()]
    if any(lignes):
        return lignes
    if not avec_ocr:
        return []
    return lignes_de_mots(mots_ocr_caches(page, cache))


def ligne_entete_y(mots: list[dict]) -> float | None:
    """Ordonnée de la ligne d'en-tête, repérée par son contenu.

    Pas par une bande fixe : l'en-tête ministériel des pages d'ouverture de
    section repousse les libellés à 43 % de la hauteur, contre 13 % sur les
    pages courantes. C'est donc la ligne portant le PLUS de libellés qui sert
    de repère, où qu'elle se trouve.
    """
    mots = sorted(mots, key=lambda w: w["top"])
    if not mots:
        return None

    groupes: list[list[dict]] = []
    for mot in mots:
        if groupes and mot["top"] - groupes[-1][-1]["top"] <= ECART_LIGNE:
            groupes[-1].append(mot)
        else:
            groupes.append([mot])

    meilleure, score = None, 0
    for groupe in groupes:
        compte = sum(1 for m in groupe if _est_mot_entete(m["text"]))
        if compte > score:
            meilleure, score = groupe, compte
    if meilleure is None or score < MINI_LIBELLES:
        return None
    return min(m["top"] for m in meilleure)


def bornes_par_entete(mots: list[dict], y_entete: float) -> list[float] | None:
    """Stratégie (b) : bornes déduites des libellés d'en-tête, sans aucun trait.

    Sur l'édition de décembre 2025, la page ne porte aucun objet vectoriel —
    `lines`, `rects` et `curves` sont vides, la grille est dans l'image. Les
    neuf libellés, eux, sont présents et stables en abscisse d'une page à
    l'autre. Ils servent donc d'ancrage, comme les traits servent en (a).

    Les libellés tiennent sur trois lignes — « DATE DATE » au-dessus, les sept
    autres au milieu, « D'OCTROI D'EXPIRATION » en dessous — d'où la fenêtre
    autour de `y_entete`. Elle écarte aussi le titre de section, qui contient
    « DATE » dans « A LA DATE DU 31/12/2025 » et fausserait le découpage.

    « DATE » est imprimé au-dessus de « D'OCTROI » : leurs empans se
    chevauchent et sont fusionnés en un seul libellé.

    Rend None si les neuf libellés ne ressortent pas — la page est alors
    rejetée, jamais devinée.
    """
    libelles = [
        w for w in mots
        if _est_mot_entete(w["text"]) and abs(w["top"] - y_entete) <= FENETRE_ENTETE
    ]
    if not libelles:
        return None

    empans: list[list[float]] = []
    for mot in sorted(libelles, key=lambda w: w["x0"]):
        if empans and mot["x0"] - empans[-1][1] <= FUSION_LIBELLE:
            empans[-1][1] = max(empans[-1][1], mot["x1"])
        else:
            empans.append([mot["x0"], mot["x1"]])

    if len(empans) != len(COLONNES):
        return None

    bornes = [empans[0][0] - MARGE_COLONNE]
    for precedent, suivant in zip(empans, empans[1:]):
        bornes.append((precedent[1] + suivant[0]) / 2)
    bornes.append(empans[-1][1] + MARGE_COLONNE)
    return bornes


def bande_sans_traits(mots: list[dict], y_entete: float) -> tuple[float, float] | None:
    """Étendue verticale du tableau quand aucun trait ne la donne.

    Le haut est la ligne d'en-tête elle-même : tout ce qui la précède est
    l'en-tête ministériel et le titre de section, qui n'appartiennent pas au
    tableau.

    Le bas s'obtient en retirant les lignes isolées du pied de page : le
    « Page N » est séparé de la dernière donnée par 37 à 45 pt, contre 5 à
    15 pt entre deux lignes du tableau. Sans ce retrait, le pied de page se
    rattacherait au dernier enregistrement et polluerait sa colonne COMMUNES.
    """
    ordonnes = sorted(mots, key=lambda w: w["top"])
    if not ordonnes:
        return None

    sommets: list[float] = []
    for mot in ordonnes:
        if not sommets or mot["top"] - sommets[-1] > ECART_LIGNE:
            sommets.append(mot["top"])

    while len(sommets) >= 2 and sommets[-1] - sommets[-2] > ECART_PIED_PAGE:
        sommets.pop()

    bas = sommets[-1] + MARGE_BOITE
    haut = y_entete - MARGE_BOITE
    return (haut, bas) if bas > haut else None


def lignes_visuelles(
    mots: list[dict], bornes: list[float], haut: float, bas: float
) -> list[dict]:
    """Regroupe les mots en lignes visuelles, puis chaque mot dans sa colonne.

    Consomme une liste de mots, d'où qu'elle vienne : couche texte d'origine
    ou Tesseract. C'est ce qui permet à (c) de ne rien réinventer.
    """
    retenus = [
        w for w in mots
        if bornes[0] <= (w["x0"] + w["x1"]) / 2 < bornes[-1] and haut <= w["top"] <= bas
    ]
    retenus.sort(key=lambda w: (w["top"], w["x0"]))

    groupes: list[list[dict]] = []
    courant: list[dict] = []
    for mot in retenus:
        if courant and mot["top"] - courant[-1]["top"] > ECART_LIGNE:
            groupes.append(courant)
            courant = []
        courant.append(mot)
    if courant:
        groupes.append(courant)

    lignes = []
    for groupe in groupes:
        cellules: list[list[str]] = [[] for _ in COLONNES]
        confiances: list[list[float]] = [[] for _ in COLONNES]
        for mot in sorted(groupe, key=lambda w: w["x0"]):
            centre = (mot["x0"] + mot["x1"]) / 2
            for i in range(len(COLONNES)):
                if bornes[i] <= centre < bornes[i + 1]:
                    cellules[i].append(mot["text"])
                    confiances[i].append(mot.get("conf", CONFIANCE_TEXTE))
                    break
        lignes.append(
            {
                "y": min(m["top"] for m in groupe),
                "cellules_mots": cellules,
                "cellules": [" ".join(c) for c in cellules],
                "confiances": confiances,
                "mots": [m["text"] for m in groupe],
            }
        )
    return lignes


def _est_mot_entete(mot: str) -> bool:
    return mot.upper().strip(":.") in VOCABULAIRE_ENTETE


def separer_entete(ligne: dict) -> tuple[bool, dict | None]:
    """Sépare les mots d'en-tête des données dans une même ligne visuelle.

    Trois cas :
      - aucun mot d'en-tête  -> (False, ligne) : ligne de données ordinaire
      - que des mots d'en-tête -> (True, None) : en-tête répété, écarté
      - les deux mêlés -> (True, ligne nettoyée) : FUSION. L'en-tête et une
        ligne de données se sont retrouvés sur la même bande. On retire les
        mots d'en-tête et on rend les données, au lieu de jeter la ligne.

    Attrape aussi les fragments (« DATE DATE », « D'OCTROI D'EXPIRATION »),
    qu'ils soient au-dessus ou au-dessous de la ligne d'en-tête.
    """
    mots = [m for m in ligne["mots"] if m.strip()]
    if not mots:
        return False, None
    nb_entete = sum(1 for m in mots if _est_mot_entete(m))
    if nb_entete == 0:
        return False, ligne
    if nb_entete == len(mots):
        return True, None

    cellules_mots: list[list[str]] = []
    confiances: list[list[float]] = []
    for cellule, confs in zip(ligne["cellules_mots"], ligne["confiances"]):
        gardes = [
            (m, c) for m, c in zip(cellule, confs + [CONFIANCE_TEXTE] * len(cellule))
            if not _est_mot_entete(m)
        ]
        cellules_mots.append([m for m, _ in gardes])
        confiances.append([c for _, c in gardes])

    restants = [m for cellule in cellules_mots for m in cellule]
    if not restants:
        return True, None
    return True, {
        "y": ligne["y"],
        "cellules_mots": cellules_mots,
        "cellules": [" ".join(c) for c in cellules_mots],
        "confiances": confiances,
        "mots": restants,
    }


def est_ancre(ligne: dict) -> bool:
    """Une ligne ouvre un enregistrement si elle porte un No ou un CODE.

    Vérifié sur les sections 1 et 9 : aucune ligne de continuation ne remplit
    ces deux colonnes.
    """
    return bool(ligne["cellules"][0].strip() or ligne["cellules"][1].strip())


def rattacher(lignes: list[dict], ancres: list[int]) -> dict[int, list[int]]:
    """Rattache chaque ligne de continuation à l'ancre la plus proche.

    Frontière au milieu de deux ancres consécutives. Une cellule qui déborde
    revient donc à son enregistrement, qu'elle soit au-dessus ou au-dessous.
    """
    attaches: dict[int, list[int]] = {a: [] for a in ancres}
    for i, _ in enumerate(lignes):
        if i in attaches:
            continue
        y = lignes[i]["y"]
        meilleure, distance = None, None
        for a in ancres:
            d = abs(lignes[a]["y"] - y)
            if distance is None or d < distance:
                meilleure, distance = a, d
        if meilleure is not None:
            attaches[meilleure].append(i)
    return attaches


def extraire_par_position(
    pdf, sections, avec_ocr: bool = True, cache: dict | None = None
) -> tuple[list[dict], list[dict]]:
    enregistrements: list[dict] = []
    rejets: list[dict] = []
    nb_fusions = 0
    if cache is None:
        cache = cache_ocr_neuf()

    for page in pdf.pages:
        section = section_de_page(sections, page.page_number)
        titre = section["titre_brut"] if section else ""
        # Cascade de stratégies, essayées dans l'ordre. Chaque enregistrement
        # portera celle qui a servi : un utilisateur doit pouvoir savoir d'où
        # vient la donnée qu'il lit.
        #   (a) traits    — couche texte + traits verticaux, la plus fiable
        #   (b) abscisses — couche texte sans traits, ancrage sur les libellés
        #   (c) ocr       — non implémentée
        mots = mots_du_texte(page)
        traits = traits_verticaux(page)
        bornes = bornes_colonnes(traits)
        strategie, boite = "traits", None

        if len(bornes) == NB_BORNES:
            boite = boite_tableau(traits)
        else:
            strategie, bornes, boite = "abscisses", None, None
            for tentative, source in (("abscisses", mots), ("ocr", None)):
                if source is None:
                    if not avec_ocr:
                        break
                    source = mots_ocr_caches(page, cache)
                y_entete = ligne_entete_y(source)
                candidat = bornes_par_entete(source, y_entete) if y_entete is not None else None
                bande = bande_sans_traits(source, y_entete) if candidat else None
                if candidat and bande:
                    strategie, bornes, boite, mots = tentative, candidat, bande, source
                    break

            if bornes is None or boite is None:
                rejets.append(
                    {
                        "page": page.page_number,
                        "section": titre,
                        "motif": "aucune stratégie applicable : ni traits, ni libellés "
                                 f"dans la couche texte{'' if avec_ocr else ', OCR désactivé'}"
                                 f"{', ni après OCR' if avec_ocr else ''}",
                        "ligne": repr({"traits": len(bornes_colonnes(traits))}),
                    }
                )
                continue

        haut, bas = boite
        lignes = lignes_visuelles(mots, bornes, haut, bas)

        # Les en-têtes répétés sont des lignes à part entière : écartées en tant
        # que telles, sans rien absorber. Ce ne sont PAS des rejets — les
        # compter comme tels laisserait croire à une perte de données.
        # Une ligne qui mêle en-tête et données est découpée, jamais jetée.
        analyse = [separer_entete(l) for l in lignes]
        premier_entete = next((i for i, (e, _) in enumerate(analyse) if e), None)

        corps = []
        for i, (est_entete, reste) in enumerate(analyse):
            if premier_entete is not None and i < premier_entete:
                continue  # hors-tableau résiduel, au-dessus de l'en-tête
            if reste is None:
                continue
            if est_entete:
                nb_fusions += 1
            corps.append(reste)

        ancres = [i for i, l in enumerate(corps) if est_ancre(l)]
        if not ancres:
            if corps:
                rejets.append(
                    {
                        "page": page.page_number,
                        "section": titre,
                        "motif": f"aucune ancre (No ou CODE) sur {len(corps)} lignes",
                        "ligne": repr([l["cellules"] for l in corps][:3]),
                    }
                )
            continue

        attaches = rattacher(corps, ancres)

        for ancre in ancres:
            indices = sorted([ancre] + attaches[ancre], key=lambda i: corps[i]["y"])
            cellules_brutes = []
            confiances_min = []
            for colonne in range(len(COLONNES)):
                morceaux = [corps[i]["cellules"][colonne] for i in indices]
                cellules_brutes.append("\n".join(m for m in morceaux if m.strip()))
                confs = [c for i in indices for c in corps[i]["confiances"][colonne]]
                confiances_min.append(min(confs) if confs else None)

            enreg = {
                "section_ordre": section["ordre"] if section else 0,
                "section_titre": titre,
                "page": page.page_number,
                "methode": "position",
                "strategie": strategie,
            }
            for colonne, cellule, conf in zip(COLONNES, cellules_brutes, confiances_min):
                enreg[f"{colonne}_brut"] = brut(cellule)
                enreg[f"{colonne}_plat"] = aplatir(cellule)
                enreg[f"{colonne}_conf"] = conf

            # Ancre vide : un chiffre isolé dans la colonne No, sans aucun champ
            # identifiant. On la REJETTE. Fabriquer un enregistrement à partir
            # de là créerait un fantôme, et un fantôme est pire qu'un trou :
            # un trou se voit dans la continuité des No, un fantôme ne se voit
            # plus jamais.
            #
            # « Vide » se mesure sur les champs IDENTIFIANTS, car les deux
            # fantômes observés sur mars 2026 ne sont pas littéralement vides :
            # l'un porte du bruit OCR en COMMUNES (',. r;;,'), l'autre un
            # STATUT seul. Ni un statut ni un nom de commune n'identifient un
            # titre ; sans code, ni nom, ni détenteur, ni date, il n'y a pas
            # d'enregistrement.
            if not any(enreg[f"{c}_plat"] for c in COLONNES_IDENTIFIANTES):
                rejets.append(
                    {
                        "page": page.page_number,
                        "section": titre,
                        "motif": "ancre vide : aucun champ identifiant "
                                 "(code, nom, détenteur, dates)",
                        "ligne": repr({c: enreg[f"{c}_plat"] for c in COLONNES
                                       if enreg[f"{c}_plat"]}),
                    }
                )
                continue

            enregistrements.append(finaliser(enreg))

    if nb_fusions:
        print(f"[position] {nb_fusions} lignes mêlant en-tête et données ont été découpées")
    if cache["pages"]:
        print(
            f"[ocr] {cache['pages']} pages océrisées en {cache['duree']:.1f} s "
            f"({cache['duree'] / cache['pages']:.2f} s/page, "
            f"{LANGUE_OCR}, {RESOLUTION_OCR} ppp)"
        )
    return enregistrements, rejets


# --------------------------------------------------------------------------
# Méthode `tables` — conservée pour comparaison
# --------------------------------------------------------------------------

def est_entete_table(cellules: list[str]) -> bool:
    joint = " ".join(aplatir(c).upper() for c in cellules)
    return sum(1 for mot in MOTS_ENTETE if mot in joint) >= 3


def absorption_entete(cellules: list[str]) -> list[str]:
    absorbe = []
    for cellule in cellules:
        if not cellule:
            continue
        surplus = [m for m in aplatir(cellule).split() if m.upper() not in VOCABULAIRE_ENTETE]
        if surplus:
            absorbe.append(" ".join(surplus))
    return absorbe


def extraire_par_tables(pdf, sections) -> tuple[list[dict], list[dict]]:
    enregistrements: list[dict] = []
    rejets: list[dict] = []

    for page in pdf.pages:
        section = section_de_page(sections, page.page_number)
        titre = section["titre_brut"] if section else ""
        for table in page.extract_tables():
            for ligne in table:
                cellules = list(ligne)
                if not [c for c in cellules if c and str(c).strip()]:
                    continue

                if est_entete_table(cellules):
                    absorbe = absorption_entete(cellules)
                    if absorbe:
                        rejets.append(
                            {
                                "page": page.page_number,
                                "section": titre,
                                "motif": "ligne d'en-tête ayant absorbé des données "
                                         f"({', '.join(absorbe)})",
                                "ligne": repr(cellules),
                            }
                        )
                    continue

                if len(cellules) != len(COLONNES):
                    rejets.append(
                        {
                            "page": page.page_number,
                            "section": titre,
                            "motif": f"{len(cellules)} cellules au lieu de {len(COLONNES)}",
                            "ligne": repr(cellules),
                        }
                    )
                    continue

                enreg = {
                    "section_ordre": section["ordre"] if section else 0,
                    "section_titre": titre,
                    "page": page.page_number,
                    "methode": "tables",
                    "strategie": "extract_tables",
                }
                for colonne, cellule in zip(COLONNES, cellules):
                    enreg[f"{colonne}_brut"] = brut(cellule)
                    enreg[f"{colonne}_plat"] = aplatir(cellule)
                enregistrements.append(finaliser(enreg))

    return enregistrements, rejets


# --------------------------------------------------------------------------
# Signalement — jamais de correction
# --------------------------------------------------------------------------

def finaliser(enreg: dict) -> dict:
    """Ajoute le statut normalisé puis le relevé des champs suspects.

    `statut_brut` et `statut_plat` ne sont JAMAIS modifiés : la normalisation
    vit dans une colonne à part.
    """
    enreg["statut_normalise"] = normaliser_statut(enreg["statut_plat"]) or ""
    confs = [enreg.get(f"{c}_conf") for c in COLONNES]
    presentes = [c for c in confs if c is not None]
    enreg["conf_min"] = round(min(presentes), 1) if presentes else ""
    suspects = champs_suspects(enreg)
    enreg["suspects"] = " | ".join(suspects)
    enreg["nb_suspects"] = len(suspects)
    return enreg


def champs_suspects(enreg: dict) -> list[str]:
    suspects = []
    if not MOTIF_CODE.match(enreg["code_plat"]):
        suspects.append(f"code non numérique: {enreg['code_plat']!r}")
    if not MOTIF_DATE.match(enreg["date_octroi_plat"]):
        suspects.append(f"date d'octroi hors format: {enreg['date_octroi_plat']!r}")
    if not MOTIF_DATE.match(enreg["date_expiration_plat"]):
        suspects.append(f"date d'expiration hors format: {enreg['date_expiration_plat']!r}")
    if not enreg["statut_normalise"]:
        suspects.append(f"statut hors vocabulaire: {enreg['statut_plat']!r}")
    if not enreg["no_plat"]:
        suspects.append("numéro d'ordre absent")
    for colonne in ("nom", "detenteur", "provinces", "communes"):
        valeur = enreg[f"{colonne}_plat"]
        if not valeur:
            suspects.append(f"{colonne} vide")
        elif set(valeur) & CARACTERES_SUSPECTS:
            parasites = "".join(sorted(set(valeur) & CARACTERES_SUSPECTS))
            suspects.append(f"{colonne} contient {parasites!r}")

    # Confiance OCR : un mot mal reconnu fait passer son champ en suspect.
    # La valeur n'est jamais corrigée pour autant.
    for colonne in COLONNES:
        conf = enreg.get(f"{colonne}_conf")
        if conf is not None and conf < SEUIL_CONFIANCE:
            suspects.append(f"confiance OCR faible sur {colonne}: {conf:.0f}")
    return suspects


# --------------------------------------------------------------------------
# Sorties
# --------------------------------------------------------------------------

def colonnes_csv() -> list[str]:
    entetes = ["section_ordre", "section_titre", "page", "methode", "strategie"]
    for colonne in COLONNES:
        entetes += [f"{colonne}_brut", f"{colonne}_plat", f"{colonne}_conf"]
        if colonne == "statut":
            entetes.append("statut_normalise")
    return entetes + ["conf_min", "nb_suspects", "suspects"]


def ecrire_csv(dossier: Path, sections, enregistrements) -> Path:
    dossier.mkdir(parents=True, exist_ok=True)
    entetes = colonnes_csv()
    consolide = dossier / "titres_consolide.csv"
    with consolide.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=entetes)
        writer.writeheader()
        writer.writerows(enregistrements)
    for section in sections:
        lignes = [e for e in enregistrements if e["section_ordre"] == section["ordre"]]
        fichier = dossier / f"{section['ordre']:02d}_{nom_fichier(section['titre_brut'])}.csv"
        with fichier.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=entetes)
            writer.writeheader()
            writer.writerows(lignes)
        section[f"nb_{enregistrements[0]['methode'] if enregistrements else 'x'}"] = len(lignes)
    return consolide


def continuite(enregistrements) -> dict:
    """Mesure les lignes perdues par la continuité des numéros d'ordre.

    Le champ No est une suite 1..N par section : ce qui manque dans la suite
    est un enregistrement que l'extraction n'a pas reconstitué. C'est la seule
    mesure de perte qui ne dépende pas de la méthode.
    """
    manquants_total, doublons_total, par_section = 0, 0, {}
    for ordre in sorted({e["section_ordre"] for e in enregistrements}):
        numeros = [
            int(e["no_plat"].strip())
            for e in enregistrements
            if e["section_ordre"] == ordre and e["no_plat"].strip().isdigit()
        ]
        if not numeros:
            continue
        manquants = sorted(set(range(1, max(numeros) + 1)) - set(numeros))
        doublons = sorted(n for n, c in Counter(numeros).items() if c > 1)
        par_section[ordre] = {"max": max(numeros), "manquants": manquants, "doublons": doublons}
        manquants_total += len(manquants)
        doublons_total += len(doublons)
    return {"total": manquants_total, "doublons": doublons_total, "sections": par_section}


def bilan(enregistrements, rejets) -> dict:
    avec = [e for e in enregistrements if e["nb_suspects"]]
    c = continuite(enregistrements)
    return {
        "lignes": len(enregistrements),
        "rejets": len(rejets),
        "suspectes": len(avec),
        "manquants": c["total"],
        "doublons": c["doublons"],
        "continuite": c,
        "taux": (100.0 * len(avec) / len(enregistrements)) if enregistrements else 0.0,
        "motifs": Counter(
            s.split(":")[0] for e in avec for s in e["suspects"].split(" | ")
        ),
    }


def rapport_methode(dire, titre, sections, enregistrements, rejets) -> None:
    b = bilan(enregistrements, rejets)
    dire(f"\n### {titre}")
    dire(f"lignes extraites : {b['lignes']}")
    dire(f"lignes rejetées  : {b['rejets']}")
    dire(f"lignes suspectes : {b['suspectes']} / {b['lignes']}  ({b['taux']:.1f} %)")
    dire(f"numéros manquants dans la suite : {b['manquants']}   doublons : {b['doublons']}")

    parts = Counter(e.get("strategie", "?") for e in enregistrements)
    if parts:
        dire("\nstratégie ayant servi :")
        for nom, nombre in parts.most_common():
            dire(f"  {nombre:>4}  {nom}")

    dire("\ncontinuité des numéros d'ordre (mesure des lignes perdues) :")
    for ordre, c in b["continuite"]["sections"].items():
        dire(f"  section {ordre} : suite 1–{c['max']}, "
             f"{len(c['manquants'])} manquants {c['manquants'][:12]}, "
             f"{len(c['doublons'])} doublons {c['doublons'][:6]}")

    dire("\nlignes par section :")
    for section in sections:
        n = len([e for e in enregistrements if e["section_ordre"] == section["ordre"]])
        dire(f"  [{section['ordre']}] pages {section['page_debut']}–{section['page_fin']:>3} "
             f": {n:>4}  {section['titre_brut'][:60]}")

    dire("\nmotifs de rejet :")
    for motif, nombre in Counter(r["motif"] for r in rejets).most_common(10):
        dire(f"  {nombre:>4}  {motif[:110]}")
    if not rejets:
        dire("  (aucun)")

    dire("\nchamps suspects, par motif :")
    for motif, nombre in b["motifs"].most_common():
        dire(f"  {nombre:>4}  {motif}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrait les tableaux d'une édition des listes de titres miniers valides."
    )
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, default=Path("data/extraction"))
    parser.add_argument("--methode", choices=("position", "tables"), default="position")
    parser.add_argument("--comparer", action="store_true", help="Exécute les deux méthodes")
    parser.add_argument(
        "--sans-ocr", action="store_true",
        help="Désactive la stratégie (c) : les pages sans couche texte sont rejetées",
    )
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"Fichier introuvable : {args.pdf}")

    lignes_rapport: list[str] = []

    def dire(ligne: str = "") -> None:
        print(ligne)
        lignes_rapport.append(ligne)

    with pdfplumber.open(args.pdf) as pdf:
        avec_ocr = not args.sans_ocr
        sans_texte = sum(len(page.chars) for page in pdf.pages) == 0
        if sans_texte and not avec_ocr:
            verifier_couche_texte(pdf, args.pdf)

        cache = cache_ocr_neuf()
        sections = reperer_sections(pdf, cache, avec_ocr)

        dire("=" * 78)
        dire(f"EXTRACTION — {args.pdf.name}")
        dire(f"pages : {len(pdf.pages)}  |  sections repérées : {len(sections)}")
        if sans_texte:
            producer = (pdf.metadata or {}).get("Producer", "(non déclaré)")
            dire(f"AUCUNE COUCHE TEXTE (Producer = {producer!r}) — la stratégie OCR prend")
            dire("le relais. Les valeurs proviennent d'une reconnaissance, pas du document.")
        dire("=" * 78)

        resultats = {}
        methodes = ("position", "tables") if args.comparer else (args.methode,)
        for methode in methodes:
            if methode == "position":
                resultats[methode] = extraire_par_position(pdf, sections, avec_ocr, cache)
            else:
                resultats[methode] = extraire_par_tables(pdf, sections)

    for methode, (enregistrements, rejets) in resultats.items():
        dossier = args.out / methode if args.comparer else args.out
        consolide = ecrire_csv(dossier, sections, enregistrements)
        rapport_methode(dire, f"MÉTHODE « {methode} »", sections, enregistrements, rejets)
        dire(f"\nCSV : {consolide}")

    if args.comparer:
        dire("\n" + "=" * 78)
        dire("### COMPARAISON")
        dire("=" * 78)
        bp = bilan(*resultats["position"])
        bt = bilan(*resultats["tables"])
        dire(f"{'':<28}{'tables':>12}{'position':>12}{'écart':>12}")
        for libelle, cle, unite in (
            ("lignes extraites", "lignes", ""),
            ("lignes rejetées", "rejets", ""),
            ("lignes suspectes", "suspectes", ""),
            ("lignes perdues (suite No)", "manquants", ""),
            ("doublons de No", "doublons", ""),
        ):
            dire(f"{libelle:<28}{bt[cle]:>12}{bp[cle]:>12}{bp[cle] - bt[cle]:>+12}{unite}")
        dire(f"{'taux de lignes suspectes':<28}{bt['taux']:>11.1f}%{bp['taux']:>11.1f}%"
             f"{bp['taux'] - bt['taux']:>+11.1f}pt")
        dire("\npar section :")
        dire(f"{'section':<10}{'tables':>10}{'position':>10}{'écart':>10}")
        for section in sections:
            nt = len([e for e in resultats["tables"][0] if e["section_ordre"] == section["ordre"]])
            np_ = len([e for e in resultats["position"][0] if e["section_ordre"] == section["ordre"]])
            dire(f"[{section['ordre']}]{'':<7}{nt:>10}{np_:>10}{np_ - nt:>+10}")

    dire("\n" + "-" * 78)
    dire("Aucune valeur n'a été corrigée. On répare le découpage, jamais le texte.")

    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "rapport.txt").write_text("\n".join(lignes_rapport), encoding="utf-8")
    print(f"\n[rapport écrit dans {args.out / 'rapport.txt'}]")


if __name__ == "__main__":
    main()
