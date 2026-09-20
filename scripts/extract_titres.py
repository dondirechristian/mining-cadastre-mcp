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
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pdfplumber

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
STATUTS_CONNUS = {"valide", "en renouvellement", "suspendu"}
CARACTERES_SUSPECTS = set("|\\~^`{}[]<>_@#$%*+=")

# Paramètres géométriques, tous mesurés sur mars 2026 avant d'être codés.
TOLERANCE_BORNE = 6.0     # regroupe les traits verticaux doublés
X_MINI_BORNE = 20.0       # écarte le trait de bord de page (vu sur 4 pages)
NB_BORNES = 10            # 9 colonnes
ECART_LIGNE = 5.0         # au-delà, deux mots sont sur deux lignes visuelles
MARGE_BOITE = 3.0         # tolérance sur la boîte du tableau


def aplatir(valeur: str | None) -> str:
    if valeur is None:
        return ""
    return re.sub(r"\s*\n\s*", " ", valeur).strip()


def brut(valeur: str | None) -> str:
    return "" if valeur is None else valeur


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


def reperer_sections(pdf) -> list[dict]:
    sections = []
    for page in pdf.pages:
        lignes = [l.strip() for l in (page.extract_text() or "").splitlines()]
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


def lignes_visuelles(page, bornes: list[float], haut: float, bas: float) -> list[dict]:
    """Regroupe les mots en lignes visuelles, puis chaque mot dans sa colonne."""
    mots = [
        w for w in page.extract_words()
        if bornes[0] <= (w["x0"] + w["x1"]) / 2 < bornes[-1] and haut <= w["top"] <= bas
    ]
    mots.sort(key=lambda w: (w["top"], w["x0"]))

    groupes: list[list[dict]] = []
    courant: list[dict] = []
    for mot in mots:
        if courant and mot["top"] - courant[-1]["top"] > ECART_LIGNE:
            groupes.append(courant)
            courant = []
        courant.append(mot)
    if courant:
        groupes.append(courant)

    lignes = []
    for groupe in groupes:
        cellules: list[list[str]] = [[] for _ in COLONNES]
        for mot in sorted(groupe, key=lambda w: w["x0"]):
            centre = (mot["x0"] + mot["x1"]) / 2
            for i in range(len(COLONNES)):
                if bornes[i] <= centre < bornes[i + 1]:
                    cellules[i].append(mot["text"])
                    break
        lignes.append(
            {
                "y": min(m["top"] for m in groupe),
                "cellules": [" ".join(c) for c in cellules],
                "mots": [m["text"] for m in groupe],
            }
        )
    return lignes


def est_ligne_entete(ligne: dict) -> bool:
    """Vrai si TOUS les mots de la ligne appartiennent au vocabulaire d'en-tête.

    Attrape la ligne d'en-tête complète comme ses fragments (« DATE DATE »,
    « D'OCTROI D'EXPIRATION »), qu'ils soient au-dessus ou au-dessous d'elle.
    """
    mots = [m.upper().strip(":.") for m in ligne["mots"] if m.strip()]
    return bool(mots) and all(m in VOCABULAIRE_ENTETE for m in mots)


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


def extraire_par_position(pdf, sections) -> tuple[list[dict], list[dict]]:
    enregistrements: list[dict] = []
    rejets: list[dict] = []

    for page in pdf.pages:
        section = section_de_page(sections, page.page_number)
        titre = section["titre_brut"] if section else ""
        traits = traits_verticaux(page)
        bornes = bornes_colonnes(traits)

        if len(bornes) != NB_BORNES:
            rejets.append(
                {
                    "page": page.page_number,
                    "section": titre,
                    "motif": f"{len(bornes)} bornes de colonnes au lieu de {NB_BORNES}",
                    "ligne": repr([round(b) for b in bornes]),
                }
            )
            continue

        haut, bas = boite_tableau(traits)
        lignes = lignes_visuelles(page, bornes, haut, bas)

        # Les en-têtes répétés sont des lignes à part entière : écartées en tant
        # que telles, sans rien absorber. Ce ne sont PAS des rejets — les
        # compter comme tels laisserait croire à une perte de données.
        entetes = [i for i, l in enumerate(lignes) if est_ligne_entete(l)]

        # Tout ce qui précède le premier en-tête est du hors-tableau résiduel.
        depart = min(entetes) + 1 if entetes else 0
        corps = [l for i, l in enumerate(lignes) if i >= depart and i not in entetes]

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
            for colonne in range(len(COLONNES)):
                morceaux = [corps[i]["cellules"][colonne] for i in indices]
                cellules_brutes.append("\n".join(m for m in morceaux if m.strip()))

            enreg = {
                "section_ordre": section["ordre"] if section else 0,
                "section_titre": titre,
                "page": page.page_number,
                "methode": "position",
            }
            for colonne, cellule in zip(COLONNES, cellules_brutes):
                enreg[f"{colonne}_brut"] = brut(cellule)
                enreg[f"{colonne}_plat"] = aplatir(cellule)
            suspects = champs_suspects(enreg)
            enreg["suspects"] = " | ".join(suspects)
            enreg["nb_suspects"] = len(suspects)
            enregistrements.append(enreg)

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
                }
                for colonne, cellule in zip(COLONNES, cellules):
                    enreg[f"{colonne}_brut"] = brut(cellule)
                    enreg[f"{colonne}_plat"] = aplatir(cellule)
                suspects = champs_suspects(enreg)
                enreg["suspects"] = " | ".join(suspects)
                enreg["nb_suspects"] = len(suspects)
                enregistrements.append(enreg)

    return enregistrements, rejets


# --------------------------------------------------------------------------
# Signalement — jamais de correction
# --------------------------------------------------------------------------

def champs_suspects(enreg: dict) -> list[str]:
    suspects = []
    if not MOTIF_CODE.match(enreg["code_plat"]):
        suspects.append(f"code non numérique: {enreg['code_plat']!r}")
    if not MOTIF_DATE.match(enreg["date_octroi_plat"]):
        suspects.append(f"date d'octroi hors format: {enreg['date_octroi_plat']!r}")
    if not MOTIF_DATE.match(enreg["date_expiration_plat"]):
        suspects.append(f"date d'expiration hors format: {enreg['date_expiration_plat']!r}")
    if enreg["statut_plat"].lower() not in STATUTS_CONNUS:
        suspects.append(f"statut inconnu: {enreg['statut_plat']!r}")
    if not enreg["no_plat"]:
        suspects.append("numéro d'ordre absent")
    for colonne in ("nom", "detenteur", "provinces", "communes"):
        valeur = enreg[f"{colonne}_plat"]
        if not valeur:
            suspects.append(f"{colonne} vide")
        elif set(valeur) & CARACTERES_SUSPECTS:
            parasites = "".join(sorted(set(valeur) & CARACTERES_SUSPECTS))
            suspects.append(f"{colonne} contient {parasites!r}")
    return suspects


# --------------------------------------------------------------------------
# Sorties
# --------------------------------------------------------------------------

def colonnes_csv() -> list[str]:
    entetes = ["section_ordre", "section_titre", "page", "methode"]
    for colonne in COLONNES:
        entetes += [f"{colonne}_brut", f"{colonne}_plat"]
    return entetes + ["nb_suspects", "suspects"]


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
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"Fichier introuvable : {args.pdf}")

    lignes_rapport: list[str] = []

    def dire(ligne: str = "") -> None:
        print(ligne)
        lignes_rapport.append(ligne)

    with pdfplumber.open(args.pdf) as pdf:
        verifier_couche_texte(pdf, args.pdf)
        sections = reperer_sections(pdf)

        dire("=" * 78)
        dire(f"EXTRACTION — {args.pdf.name}")
        dire(f"pages : {len(pdf.pages)}  |  sections repérées : {len(sections)}")
        dire("=" * 78)

        resultats = {}
        methodes = ("position", "tables") if args.comparer else (args.methode,)
        for methode in methodes:
            fonction = extraire_par_position if methode == "position" else extraire_par_tables
            resultats[methode] = fonction(pdf, sections)

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
