"""
Diagnostic pdfplumber sur une édition des listes de titres miniers valides.

Ce script NE FAIT PAS D'EXTRACTION. Il ne produit ni CSV, ni enregistrements,
ni découpage des neuf sections. Il constate, et rien de plus :

  - le nombre de pages réel
  - la présence et la qualité de la couche texte, page par page
  - ce que `extract_tables()` détecte, et avec quelle géométrie
  - un échantillon brut de quelques pages, tel quel, sans nettoyage
  - une estimation du taux de lignes exploitables, selon un critère affiché

Le document est un scan passé à l'OCR : rien de ce qui en sort n'est corrigé ici.

USAGE
    python scripts/diagnose_pdf.py <chemin.pdf>
    python scripts/diagnose_pdf.py <chemin.pdf> --sample 3 8 25
    python scripts/diagnose_pdf.py <chemin.pdf> --rapport diagnostic.txt
"""

import argparse
import re
import sys
from pathlib import Path

import pdfplumber

# Critère d'exploitabilité, affiché dans le rapport pour qu'il soit discutable.
# Une ligne est comptée exploitable si elle porte au moins 9 cellules non vides
# et qu'au moins une cellule ressemble à une date JJ/MM/AAAA. Ce critère ne
# valide RIEN sur le fond : il mesure seulement si la géométrie du tableau
# ressort assez pour qu'un enregistrement soit reconstituable.
MIN_CELLULES = 9
MOTIF_DATE = re.compile(r"\b\d{2}/\d{2}/\d{4}\b")
MOTIF_CODE = re.compile(r"^\d+$")


def qualite_texte(texte: str) -> dict:
    """Mesure grossière de la qualité d'une couche texte OCR."""
    if not texte:
        return {"caracteres": 0, "lignes": 0, "alnum_pct": 0.0, "suspects": 0}
    alnum = sum(1 for c in texte if c.isalnum())
    # Caractères rarement légitimes dans ce document : bon indicateur de bruit OCR.
    suspects = sum(1 for c in texte if c in "|\\~^`{}[]<>_@#$%*+=")
    return {
        "caracteres": len(texte),
        "lignes": len([l for l in texte.splitlines() if l.strip()]),
        "alnum_pct": 100.0 * alnum / len(texte),
        "suspects": suspects,
    }


def analyse_page(page) -> dict:
    texte = page.extract_text() or ""
    q = qualite_texte(texte)
    tables = page.extract_tables()

    lignes_totales = 0
    lignes_exploitables = 0
    codes_numeriques = 0
    for table in tables:
        for row in table:
            cellules = [c for c in row if c and str(c).strip()]
            if not cellules:
                continue
            lignes_totales += 1
            joint = " ".join(str(c) for c in cellules)
            if len(cellules) >= MIN_CELLULES and MOTIF_DATE.search(joint):
                lignes_exploitables += 1
            if row and row[1] and MOTIF_CODE.match(str(row[1]).strip()):
                codes_numeriques += 1

    return {
        "numero": page.page_number,
        "taille": (round(page.width, 1), round(page.height, 1)),
        "chars": len(page.chars),
        "images": len(page.images),
        "lignes_graphiques": len(page.lines),
        "rects": len(page.rects),
        "texte": texte,
        "qualite": q,
        "nb_tables": len(tables),
        "geometrie_tables": [(len(t), max((len(r) for r in t), default=0)) for t in tables],
        "lignes_totales": lignes_totales,
        "lignes_exploitables": lignes_exploitables,
        "codes_numeriques": codes_numeriques,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnostic pdfplumber, sans extraction.")
    parser.add_argument("pdf", type=Path)
    parser.add_argument(
        "--sample", type=int, nargs="*", default=None,
        help="Numéros de pages (1-based) à afficher brutes. Défaut : 3 pages réparties.",
    )
    parser.add_argument("--rapport", type=Path, default=None, help="Écrire aussi dans ce fichier")
    args = parser.parse_args()

    if not args.pdf.exists():
        raise SystemExit(f"Fichier introuvable : {args.pdf}")

    sortie = []

    def dire(ligne: str = "") -> None:
        print(ligne)
        sortie.append(ligne)

    with pdfplumber.open(args.pdf) as pdf:
        pages = pdf.pages
        dire("=" * 78)
        dire(f"FICHIER   : {args.pdf.name}")
        dire(f"TAILLE    : {args.pdf.stat().st_size} octets")
        dire(f"PAGES     : {len(pages)}")
        dire(f"METADATA  : {pdf.metadata}")
        dire("=" * 78)

        analyses = []
        dire("\n### COUCHE TEXTE ET TABLEAUX, PAGE PAR PAGE")
        dire(
            f"{'page':>4} {'chars':>7} {'img':>4} {'lig.':>5} {'rect':>5} "
            f"{'txt':>7} {'lignes':>7} {'alnum%':>7} {'susp':>5} "
            f"{'tabl':>5} {'rows':>6} {'expl.':>6} {'code#':>6}"
        )
        for page in pages:
            a = analyse_page(page)
            analyses.append(a)
            q = a["qualite"]
            dire(
                f"{a['numero']:>4} {a['chars']:>7} {a['images']:>4} "
                f"{a['lignes_graphiques']:>5} {a['rects']:>5} "
                f"{q['caracteres']:>7} {q['lignes']:>7} {q['alnum_pct']:>7.1f} "
                f"{q['suspects']:>5} {a['nb_tables']:>5} {a['lignes_totales']:>6} "
                f"{a['lignes_exploitables']:>6} {a['codes_numeriques']:>6}"
            )

        dire("\nLégende : chars/img/lig./rect = objets pdfplumber sur la page ;")
        dire("  txt = caractères rendus par extract_text() ; lignes = lignes non vides ;")
        dire("  alnum% = part alphanumérique ; susp = caractères improbables (bruit OCR) ;")
        dire("  tabl = tableaux vus par extract_tables() ; rows = lignes non vides trouvées ;")
        dire("  expl. = lignes satisfaisant le critère ; code# = 2e cellule purement numérique.")

        # --- Totaux
        pages_sans_texte = [a["numero"] for a in analyses if a["qualite"]["caracteres"] == 0]
        pages_sans_table = [a["numero"] for a in analyses if a["nb_tables"] == 0]
        total_rows = sum(a["lignes_totales"] for a in analyses)
        total_expl = sum(a["lignes_exploitables"] for a in analyses)
        total_codes = sum(a["codes_numeriques"] for a in analyses)
        total_chars = sum(a["qualite"]["caracteres"] for a in analyses)
        total_images = sum(a["images"] for a in analyses)

        dire("\n### TOTAUX")
        dire(f"pages                                : {len(pages)}")
        dire(f"pages sans aucune couche texte       : {len(pages_sans_texte)} {pages_sans_texte}")
        dire(f"pages où extract_tables() ne voit rien: {len(pages_sans_table)} {pages_sans_table}")
        dire(f"caractères de texte au total         : {total_chars}")
        dire(f"images (pages scannées)              : {total_images}")
        dire(f"lignes de tableau non vides          : {total_rows}")
        dire(f"lignes satisfaisant le critère       : {total_expl}")
        dire(f"2e cellule purement numérique        : {total_codes}")
        if total_rows:
            dire(f"TAUX DE LIGNES EXPLOITABLES          : {100.0 * total_expl / total_rows:.1f} %")
        else:
            dire("TAUX DE LIGNES EXPLOITABLES          : sans objet, aucune ligne détectée")
        dire(f"\nCritère retenu : >= {MIN_CELLULES} cellules non vides ET au moins une date JJ/MM/AAAA.")
        dire("Il mesure la géométrie, pas la justesse du contenu. Un OCR peut satisfaire")
        dire("ce critère en ayant mal lu un nom ou un chiffre.")

        # --- Échantillon brut
        if args.sample is None:
            n = len(pages)
            cibles = sorted({min(3, n), max(1, n // 2), max(1, n - 1)})
        else:
            cibles = args.sample

        for numero in cibles:
            if not (1 <= numero <= len(pages)):
                dire(f"\n(page {numero} hors limites, ignorée)")
                continue
            a = analyses[numero - 1]
            dire("\n" + "=" * 78)
            dire(f"### ÉCHANTILLON BRUT — PAGE {numero} (aucun nettoyage)")
            dire(f"taille page : {a['taille']}  | tableaux : {a['geometrie_tables']}")
            dire("-" * 78)
            dire("--- extract_text() ---")
            dire(a["texte"] if a["texte"] else "(aucun texte)")
            dire("-" * 78)
            dire("--- extract_tables(), 12 premières lignes du 1er tableau ---")
            tables = pages[numero - 1].extract_tables()
            if not tables:
                dire("(aucun tableau détecté)")
            else:
                for row in tables[0][:12]:
                    dire(repr(row))

    if args.rapport:
        args.rapport.write_text("\n".join(sortie), encoding="utf-8")
        print(f"\n[rapport écrit dans {args.rapport}]", file=sys.stderr)


if __name__ == "__main__":
    main()
