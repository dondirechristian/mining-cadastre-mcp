"""Chargement des instantanés versionnés.

Le serveur ne télécharge rien et n'extrait rien. Il lit un instantané daté,
produit hors ligne par `scripts/extract_titres.py` et versionné dans le dépôt.
C'est ce qui rend la donnée servie auditable : chaque ligne renvoyée vient d'un
fichier dont on connaît la provenance, la date et l'empreinte.
"""

import asyncio
import csv
import json
import os
from pathlib import Path

# Emplacements fouillés, dans l'ordre. Le premier qui contient un instantané
# gagne. MINING_CADASTRE_DATA permet de pointer ailleurs sans toucher au code.
_RACINES = (
    os.environ.get("MINING_CADASTRE_DATA", ""),
    Path(__file__).resolve().parents[2] / "data",   # dépôt en place
    Path(__file__).resolve().parent / "data",       # paquet installé
)


class DonneesIntrouvables(RuntimeError):
    """Aucun instantané lisible. Le message dit où l'on a cherché et quoi faire."""


def _racines_existantes() -> list[Path]:
    vues, racines = set(), []
    for racine in _RACINES:
        if not racine:
            continue
        chemin = Path(racine).resolve()
        if chemin not in vues:
            vues.add(chemin)
            racines.append(chemin)
    return racines


def _editions(racine: Path) -> list[Path]:
    """Répertoires d'instantané, du plus récent au plus ancien.

    Un instantané est un répertoire daté AAAA-MM-JJ portant `source.json` et
    `titres.csv`. Le tri lexical sur ce nom est aussi le tri chronologique.
    """
    if not racine.is_dir():
        return []
    return sorted(
        (
            d for d in racine.iterdir()
            if d.is_dir() and (d / "source.json").is_file() and (d / "titres.csv").is_file()
        ),
        key=lambda d: d.name,
        reverse=True,
    )


def _lire_instantane(dossier: Path) -> dict:
    source = json.loads((dossier / "source.json").read_text(encoding="utf-8"))
    with (dossier / "titres.csv").open(encoding="utf-8-sig", newline="") as f:
        lignes = list(csv.DictReader(f))
    return {"dossier": dossier, "source": source, "lignes": lignes}


def _charger() -> dict:
    cherchés = []
    for racine in _racines_existantes():
        cherchés.append(str(racine))
        editions = _editions(racine)
        if editions:
            return _lire_instantane(editions[0])
    raise DonneesIntrouvables(
        "Aucun instantané de titres miniers n'a été trouvé.\n"
        "Cherché dans :\n  " + "\n  ".join(cherchés) + "\n\n"
        "Un instantané est un répertoire daté AAAA-MM-JJ contenant source.json\n"
        "et titres.csv. Pour en produire un :\n"
        "  python scripts/fetch_titres.py --list\n"
        "  python scripts/fetch_titres.py <url du PDF>\n"
        "  python scripts/extract_titres.py <pdf> --out data/AAAA-MM-JJ\n\n"
        "Ou pointer un instantané existant :\n"
        "  MINING_CADASTRE_DATA=/chemin/vers/data"
    )


_cache: dict | None = None


async def catalogue() -> dict:
    """Instantané le plus récent, chargé une seule fois puis mémorisé."""
    global _cache
    if _cache is None:
        _cache = await asyncio.to_thread(_charger)
    return _cache


def bloc_source(source: dict) -> dict:
    """Bloc de provenance, joint à CHAQUE réponse d'outil.

    Un titre minier a des conséquences juridiques et financières : toute
    réponse doit dire d'où vient la donnée, de quand elle date, et qu'elle ne
    fait pas foi.
    """
    return {
        "juridiction": source.get("juridiction"),
        "pays": source.get("pays"),
        "autorite": source.get("autorite"),
        "edition": source.get("edition"),
        "edition_libelle": source.get("edition_libelle"),
        "publiee_le": source.get("publie_le"),
        "lue_le": source.get("lu_le"),
        "article": source.get("article"),
        "document": source.get("fichier_url"),
        "document_sha256": source.get("fichier_sha256"),
        "extraction": {
            "outil": source.get("extrait_par"),
            "strategie": source.get("strategie"),
            "enregistrements": source.get("enregistrements"),
            "lignes_suspectes": source.get("lignes_suspectes"),
        },
        "avertissement": (
            "Instantané daté, extrait d'un PDF scanné puis océrisé, publié par "
            "l'autorité citée. La donnée reflète l'état à la date d'édition, non "
            "l'état du jour. Elle ne fait pas foi : le registre officiel est la "
            "seule référence opposable."
        ),
    }
