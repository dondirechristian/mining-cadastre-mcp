"""
Extraction des tableaux d'une édition des listes de titres miniers valides.

Écrit à partir de l'édition du 31 mars 2026, observée — pas supposée.

CE QUE FAIT CE SCRIPT
  - refuse de travailler si le PDF n'a pas de couche texte, et dit pourquoi
  - repère les neuf sections par leur ligne « LISTE DES ... VALIDES A LA DATE DU »
  - sort une ligne par titre minier, avec sa section d'origine
  - conserve chaque cellule DEUX FOIS : `_brut` avec ses retours à la ligne
    internes tels quels, `_plat` avec les retours à la ligne remplacés par une
    espace. Rien d'autre n'est touché.
  - écrit un CSV par section, plus un CSV consolidé
  - écrit un rapport : lignes par section, lignes rejetées avec leur motif,
    champs suspects

CE QUE CE SCRIPT NE FAIT PAS
  Aucune correction. Le document est un scan OCRisé : « KOTl2 », « KABOUi »,
  « En renouvellem ent » sortent tels quels. Les champs douteux sont SIGNALÉS
  dans le rapport, jamais réparés. Le nettoyage est une étape séparée, et il
  se décide en regardant ce bruit-là.

USAGE
    python scripts/extract_titres.py <chemin.pdf>
    python scripts/extract_titres.py <chemin.pdf> --out data/extraction
"""

import argparse
import csv
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pdfplumber

# Les neuf colonnes, dans l'ordre où elles apparaissent dans le document.
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

# Une section s'ouvre sur cette ligne. Le libellé est parfois coupé en deux.
MOTIF_SECTION = re.compile(r"^LISTE\s+DES\s+", re.I)
MOTIF_FIN_SECTION = re.compile(r"VALIDES?\s+A\s+LA\s+DATE\s+DU", re.I)

# Repères de ligne d'en-tête de tableau, répétée en haut de chaque page.
MOTS_ENTETE = ("CODE", "NOM", "STATUT", "DETENTEUR")

MOTIF_DATE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
MOTIF_CODE = re.compile(r"^\d+$")
STATUTS_CONNUS = {"valide", "en renouvellement", "suspendu"}

# Caractères rarement légitimes dans ce document : indicateurs de bruit OCR.
CARACTERES_SUSPECTS = set("|\\~^`{}[]<>_@#$%*+=")


def aplatir(valeur: str | None) -> str:
    """Remplace les retours à la ligne par une espace. Ne touche à rien d'autre."""
    if valeur is None:
        return ""
    return re.sub(r"\s*\n\s*", " ", valeur).strip()


def brut(valeur: str | None) -> str:
    """Valeur telle que pdfplumber la rend, retours à la ligne compris."""
    return "" if valeur is None else valeur


def nom_fichier(texte: str) -> str:
    """Slug ASCII pour nommer un CSV de section. N'affecte aucune donnée."""
    sans_accent = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", sans_accent.lower()).strip("_")[:80]


def verifier_couche_texte(pdf, chemin: Path) -> None:
    """S'arrête clairement si le PDF est un scan sans couche texte."""
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
    """Repère les sections et la page où chacune commence.

    Lit la ligne « LISTE DES ... » telle qu'elle est écrite. Ne normalise pas
    le libellé et ne le rapproche d'aucune liste attendue.
    """
    sections = []
    for page in pdf.pages:
        lignes = [l.strip() for l in (page.extract_text() or "").splitlines()]
        for i, ligne in enumerate(lignes):
            if not MOTIF_SECTION.match(ligne):
                continue
            titre = ligne
            # Le libellé déborde parfois sur la ligne suivante.
            if not MOTIF_FIN_SECTION.search(titre) and i + 1 < len(lignes):
                titre = f"{titre} {lignes[i + 1].strip()}"
            sections.append(
                {
                    "titre_brut": titre,
                    "page_debut": page.page_number,
                    "entete_page": lignes[:i],  # bloc d'en-tête, arrêté compris
                }
            )
            break  # une seule ouverture de section par page
    for rang, section in enumerate(sections):
        if rang + 1 < len(sections):
            section["page_fin"] = sections[rang + 1]["page_debut"] - 1
        else:
            section["page_fin"] = len(pdf.pages)
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


def est_entete(cellules: list[str]) -> bool:
    joint = " ".join(aplatir(c).upper() for c in cellules)
    return sum(1 for mot in MOTS_ENTETE if mot in joint) >= 3


def absorption_entete(cellules: list[str]) -> list[str]:
    """Dit ce qu'une ligne d'en-tête a absorbé d'un enregistrement, mot à mot.

    Une cellule d'en-tête saine vaut « CODE », « NOM », « DATE D'OCTROI »...
    Tout ce qui déborde de ce vocabulaire est une donnée capturée par erreur.
    """
    vocabulaire = {
        "NO", "CODE", "NOM", "STATUT", "DETENTEUR", "DATE", "D'OCTROI",
        "D'EXPIRATION", "PROVINCES", "COMMUNES", "-",
    }
    absorbe = []
    for cellule in cellules:
        if not cellule:
            continue
        surplus = [m for m in aplatir(cellule).split() if m.upper() not in vocabulaire]
        if surplus:
            absorbe.append(" ".join(surplus))
    return absorbe


def champs_suspects(enreg: dict) -> list[str]:
    """Signale ce qui ne ressemble pas à ce qu'on attend. Ne corrige rien."""
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
        suspects.append("numéro d'ordre absent (souvent absorbé par la ligne d'en-tête)")
    for colonne in ("nom", "detenteur", "provinces", "communes"):
        valeur = enreg[f"{colonne}_plat"]
        if not valeur:
            suspects.append(f"{colonne} vide")
        elif set(valeur) & CARACTERES_SUSPECTS:
            parasites = "".join(sorted(set(valeur) & CARACTERES_SUSPECTS))
            suspects.append(f"{colonne} contient {parasites!r}")
    return suspects


def extraire(chemin: Path, dossier: Path) -> None:
    rejets: list[dict] = []
    enregistrements: list[dict] = []

    with pdfplumber.open(chemin) as pdf:
        verifier_couche_texte(pdf, chemin)
        sections = reperer_sections(pdf)

        for page in pdf.pages:
            section = section_de_page(sections, page.page_number)
            for table in page.extract_tables():
                for ligne in table:
                    cellules = list(ligne)
                    non_vides = [c for c in cellules if c and str(c).strip()]
                    if not non_vides:
                        continue

                    if est_entete(cellules):
                        # L'en-tête de page absorbe parfois une partie du premier
                        # enregistrement : un numéro, un code, un nom, une date.
                        # Cette donnée est PERDUE — on la signale telle quelle,
                        # on ne la réinjecte pas.
                        absorbe = absorption_entete(cellules)
                        if absorbe:
                            rejets.append(
                                {
                                    "page": page.page_number,
                                    "section": section["titre_brut"] if section else "",
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
                                "section": section["titre_brut"] if section else "",
                                "motif": f"{len(cellules)} cellules au lieu de {len(COLONNES)}",
                                "ligne": repr(cellules),
                            }
                        )
                        continue

                    enreg = {
                        "section_ordre": section["ordre"] if section else 0,
                        "section_titre": section["titre_brut"] if section else "",
                        "page": page.page_number,
                    }
                    for colonne, cellule in zip(COLONNES, cellules):
                        enreg[f"{colonne}_brut"] = brut(cellule)
                        enreg[f"{colonne}_plat"] = aplatir(cellule)

                    suspects = champs_suspects(enreg)
                    enreg["suspects"] = " | ".join(suspects)
                    enreg["nb_suspects"] = len(suspects)
                    enregistrements.append(enreg)

    ecrire_sorties(chemin, dossier, sections, enregistrements, rejets)


def colonnes_csv() -> list[str]:
    entetes = ["section_ordre", "section_titre", "page"]
    for colonne in COLONNES:
        entetes += [f"{colonne}_brut", f"{colonne}_plat"]
    return entetes + ["nb_suspects", "suspects"]


def ecrire_sorties(chemin, dossier, sections, enregistrements, rejets) -> None:
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
        section["nb_lignes"] = len(lignes)
        section["fichier"] = fichier.name

    rapport = dossier / "rapport.txt"
    lignes_rapport: list[str] = []

    def dire(ligne: str = "") -> None:
        print(ligne)
        lignes_rapport.append(ligne)

    dire("=" * 78)
    dire(f"EXTRACTION — {chemin.name}")
    dire(f"sections repérées : {len(sections)}")
    dire(f"lignes extraites  : {len(enregistrements)}")
    dire(f"lignes rejetées   : {len(rejets)}")
    dire("=" * 78)

    dire("\n### LIGNES PAR SECTION")
    for section in sections:
        dire(f"\n[{section['ordre']}] {section['titre_brut']}")
        dire(f"    pages {section['page_debut']}–{section['page_fin']}  |  "
             f"{section['nb_lignes']} lignes  |  {section['fichier']}")
        entete = [l for l in section["entete_page"] if l]
        if entete:
            dire(f"    en-tête brut (arrêté compris) : {entete[-3:]}")

    dire("\n### LIGNES REJETÉES")
    if not rejets:
        dire("(aucune)")
    else:
        motifs = Counter(r["motif"] for r in rejets)
        for motif, nombre in motifs.most_common():
            dire(f"  {nombre:>4}  {motif}")
        dire("\n  détail :")
        for rejet in rejets:
            dire(f"  p{rejet['page']:>3} | {rejet['motif']}")
            dire(f"         {rejet['ligne'][:400]}")

    dire("\n### CHAMPS SUSPECTS")
    avec = [e for e in enregistrements if e["nb_suspects"]]
    dire(f"lignes portant au moins un champ suspect : {len(avec)} / {len(enregistrements)}")
    if enregistrements:
        taux = 100.0 * len(avec) / len(enregistrements)
        dire(f"soit {taux:.1f} %  (une ligne suspecte reste extraite, elle est seulement signalée)")
    categories = Counter()
    for enreg in avec:
        for suspect in enreg["suspects"].split(" | "):
            categories[suspect.split(":")[0]] += 1
    dire("\nrépartition par motif :")
    for motif, nombre in categories.most_common():
        dire(f"  {nombre:>4}  {motif}")

    dire("\n### 15 PREMIÈRES LIGNES SUSPECTES, TELLES QUELLES")
    for enreg in avec[:15]:
        dire(f"\n  p{enreg['page']} section {enreg['section_ordre']} — {enreg['suspects']}")
        dire(f"    no={enreg['no_plat']!r} code={enreg['code_plat']!r} nom={enreg['nom_plat']!r}")
        dire(f"    statut={enreg['statut_plat']!r} detenteur={enreg['detenteur_plat']!r}")
        dire(f"    octroi={enreg['date_octroi_plat']!r} expiration={enreg['date_expiration_plat']!r}")

    dire("\n" + "-" * 78)
    dire("Aucune valeur n'a été corrigée. Les champs suspects sont signalés, pas réparés.")
    dire(f"CSV consolidé : {consolide}")
    dire(f"CSV par section : {dossier}")

    rapport.write_text("\n".join(lignes_rapport), encoding="utf-8")
    print(f"\n[rapport écrit dans {rapport}]")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extrait les tableaux d'une édition des listes de titres miniers valides."
    )
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--out", type=Path, default=Path("data/extraction"))
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"Fichier introuvable : {args.pdf}")
    extraire(args.pdf, args.out)


if __name__ == "__main__":
    main()
