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
import re
import unicodedata
from pathlib import Path

# Emplacements fouillés par défaut, dans l'ordre.
_RACINES_PAR_DEFAUT = (
    Path(__file__).resolve().parents[2] / "data",   # dépôt en place
    Path(__file__).resolve().parent / "data",       # paquet installé
)

# MINING_CADASTRE_DATA, si défini, est IMPÉRATIF : on ne cherche nulle part
# ailleurs. Une faute de frappe doit faire échouer le serveur, jamais le faire
# retomber en silence sur une autre édition — ce serveur sert de la donnée
# datée, servir la mauvaise sans le dire serait le pire défaut possible.
_VARIABLE = "MINING_CADASTRE_DATA"


class DonneesIntrouvables(RuntimeError):
    """Aucun instantané lisible. Le message dit où l'on a cherché et quoi faire."""


def _racines_a_fouiller() -> tuple[list[Path], bool]:
    """Racines à fouiller, et si elles viennent d'un choix explicite."""
    impose = os.environ.get(_VARIABLE, "").strip()
    if impose:
        return [Path(impose).resolve()], True
    vues, racines = set(), []
    for racine in _RACINES_PAR_DEFAUT:
        chemin = Path(racine).resolve()
        if chemin not in vues:
            vues.add(chemin)
            racines.append(chemin)
    return racines, False


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
    racines, impose = _racines_a_fouiller()
    cherchés = []
    for racine in racines:
        cherchés.append(str(racine))
        editions = _editions(racine)
        if editions:
            return _lire_instantane(editions[0])
    origine = (
        f"{_VARIABLE} impose ce seul emplacement ; aucun repli n'est tenté, pour "
        f"qu'une faute de frappe ne fasse pas servir une autre édition en silence.\n"
        if impose
        else ""
    )
    raise DonneesIntrouvables(
        "Aucun instantané de titres miniers n'a été trouvé.\n"
        + origine
        + "Cherché dans :\n  " + "\n  ".join(cherchés) + "\n\n"
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


def replier(texte: str) -> str:
    """Forme comparable d'un texte : sans accents, sans casse, espaces réduits.

    Sert UNIQUEMENT à comparer. La valeur rendue à l'appelant reste celle du
    document : on rapproche une requête d'un texte, on ne réécrit pas le texte.
    """
    sans_accent = unicodedata.normalize("NFKD", texte or "").encode("ascii", "ignore").decode()
    return " ".join(sans_accent.lower().split())


def contient_mots(texte: str, requete: str) -> bool:
    """Vrai si `requete` apparaît dans `texte` sur des frontières de mot.

    Pas une sous-chaîne brute : « or » ne doit PAS répondre sur
    « AUTORISATIONS ». Sans cette règle, un agent cherchant les permis d'or
    recevait 36 titres sans rapport — une fausse réponse est plus nuisible
    qu'une réponse vide, surtout ici où la substance n'est pas publiée.
    """
    cible, motif = replier(texte), replier(requete)
    if not motif:
        return True
    return re.search(rf"\b{re.escape(motif)}\b", cible) is not None


def titre_public(ligne: dict) -> dict:
    """Vue d'un titre telle qu'elle sort des outils.

    `statut` porte ce qu'imprime le document ; `statut_normalise` la valeur
    canonique du vocabulaire observé. Les deux figurent, pour qu'on sache
    toujours ce que la source disait.
    """
    suspects = [s for s in (ligne.get("suspects") or "").split(" | ") if s]
    return {
        "code": ligne.get("code_plat", ""),
        "nom": ligne.get("nom_plat", ""),
        "detenteur": ligne.get("detenteur_plat", ""),
        "statut": ligne.get("statut_plat", ""),
        "statut_normalise": ligne.get("statut_normalise", ""),
        "date_octroi": ligne.get("date_octroi_plat", ""),
        "date_expiration": ligne.get("date_expiration_plat", ""),
        "provinces": ligne.get("provinces_plat", ""),
        "communes": ligne.get("communes_plat", ""),
        "categorie": ligne.get("section_titre", ""),
        "page_du_document": int(ligne["page"]) if (ligne.get("page") or "").isdigit() else None,
        "strategie_extraction": ligne.get("strategie", ""),
        "anomalies_de_lecture": suspects,
    }


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
