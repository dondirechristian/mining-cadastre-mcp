"""
Récupère la dernière liste de titres miniers valides publiée par le Ministère
de l'Énergie, des Mines et des Carrières du Burkina Faso, et décrit ce qui a
été téléchargé.

Ce script NE PARSE RIEN. Le format réel du fichier n'est pas connu à ce jour :
il est fourni par le mainteneur, il ne se devine pas. Voir les TODO ci-dessous.
Tant qu'ils ne sont pas levés, ce script sert à une seule chose : rapatrier le
fichier et dire factuellement ce qu'il est.

USAGE
    python scripts/fetch_titres.py <url>
    python scripts/fetch_titres.py            (une fois SOURCE_URL renseignée)
    python scripts/fetch_titres.py <url> --out data/

Coller ensuite la sortie dans le contexte de Claude Code, avec un extrait du
fichier lui-même, avant de lui demander le premier outil de lecture.
"""

import argparse
import asyncio
import hashlib
from pathlib import Path

import httpx

# TODO(mainteneur) — URL de la page de publication du MEMC, pour mémoire.
PUBLICATION_PAGE = None

# TODO(mainteneur) — URL directe du dernier fichier publié.
# Tant qu'elle vaut None, l'URL doit être passée en argument de ligne de
# commande. Ne rien inventer ici.
SOURCE_URL = None

# TODO(mainteneur) — format réel du fichier : PDF, XLSX, CSV, page HTML ?
# De cette réponse dépend la suite : lire un PDF ou un XLSX demande une
# bibliothèque supplémentaire, donc une décision du mainteneur.
EXPECTED_FORMAT = None

TIMEOUT = 30.0
DEFAULT_OUT = Path("data")

# Signatures de fichiers, à seule fin de CONSTAT. Ce n'est pas une hypothèse de
# format : on rapporte les premiers octets observés, on ne décide rien.
SIGNATURES = [
    (b"%PDF-", "PDF"),
    (b"PK\x03\x04", "conteneur ZIP (XLSX, ODS, DOCX...)"),
    (b"\xd0\xcf\x11\xe0", "OLE2 (XLS, DOC anciens)"),
    (b"\xef\xbb\xbf", "texte UTF-8 avec BOM"),
    (b"<!DOCTYPE", "HTML"),
    (b"<html", "HTML"),
]


def identify(head: bytes) -> str:
    for magic, label in SIGNATURES:
        if head.startswith(magic):
            return label
    return "(signature non reconnue)"


def preview(head: bytes, length: int = 256) -> str:
    chunk = head[:length]
    return "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)


async def fetch(url: str, out_dir: Path) -> Path:
    print(f"=== TÉLÉCHARGEMENT\nurl demandée  : {url}")

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise SystemExit(
                f"HTTP {exc.response.status_code} sur {exc.request.url}\n"
                "Vérifier que l'URL pointe bien vers le fichier publié, et non vers "
                "une page qui exige une session."
            )
        except httpx.RequestError as exc:
            raise SystemExit(
                f"Échec réseau : {exc!r}\n"
                "Le site du ministère est parfois indisponible. Réessayer plus tard."
            )

    body = response.content

    print(f"url finale    : {response.url}")
    print(f"statut        : {response.status_code}")
    print(f"content-type  : {response.headers.get('content-type', '(absent)')}")
    print(f"disposition   : {response.headers.get('content-disposition', '(absent)')}")
    print(f"last-modified : {response.headers.get('last-modified', '(absent)')}")
    print(f"taille        : {len(body)} octets")
    print(f"sha256        : {hashlib.sha256(body).hexdigest()}")

    out_dir.mkdir(parents=True, exist_ok=True)
    name = Path(response.url.path).name or "titres_burkina.bin"
    destination = out_dir / name
    destination.write_bytes(body)
    print(f"enregistré    : {destination}")

    print("\n=== CONSTAT SUR LE CONTENU")
    print(f"signature     : {identify(body[:16])}")
    print(f"256 premiers octets, caractères imprimables :\n{preview(body)}")

    return destination


def describe_structure(path: Path) -> None:
    """Décrit la structure du fichier : colonnes, nombre de lignes, échantillon.

    Non implémenté, volontairement. Il faut d'abord connaître le format réel —
    voir EXPECTED_FORMAT. Une fois le format connu, cette fonction doit relever
    et afficher :

      - les intitulés de colonnes tels qu'écrits dans le document
      - le nombre d'enregistrements
      - trois enregistrements complets, bruts
      - les valeurs distinctes du champ statut
      - le format des dates d'octroi et d'expiration
      - la date de publication de la liste, telle qu'elle figure au document
      - la mention de source ou de droits portée par le document
    """
    raise NotImplementedError(
        f"Format du fichier inconnu — rien n'est parsé.\n"
        f"Fichier téléchargé : {path}\n"
        "Étape suivante : le mainteneur indique le format réel (EXPECTED_FORMAT), "
        "puis cette fonction est écrite à partir du fichier observé, jamais d'une "
        "supposition."
    )


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Télécharge la dernière liste de titres miniers valides du Burkina Faso."
    )
    parser.add_argument(
        "url",
        nargs="?",
        default=SOURCE_URL,
        help="URL directe du fichier publié (obligatoire tant que SOURCE_URL vaut None)",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Répertoire de destination")
    parser.add_argument(
        "--describe",
        action="store_true",
        help="Tenter de décrire la structure du fichier (nécessite un format connu)",
    )
    args = parser.parse_args()

    if not args.url:
        raise SystemExit(
            "Aucune URL.\n"
            "SOURCE_URL n'est pas renseignée dans ce script et aucune URL n'a été "
            "passée en argument.\n"
            "Fournir l'URL du dernier fichier publié par le MEMC :\n"
            "    python scripts/fetch_titres.py <url>"
        )

    destination = await fetch(args.url, args.out)

    print("\n" + "-" * 60)
    if args.describe:
        try:
            describe_structure(destination)
        except NotImplementedError as exc:
            raise SystemExit(str(exc))
    else:
        print("À relever sur le fichier avant de coder :")
        print("  - la date de publication portée par le document")
        print("  - les intitulés de colonnes, tels qu'écrits")
        print("  - le champ du titulaire, celui du code de titre, celui du statut")
        print("  - les valeurs possibles du statut")
        print("  - le format des dates d'octroi et d'expiration")
        print("  - la mention de source ou de droits portée par le document")
        print("\nPuis reporter le format réel dans EXPECTED_FORMAT et dans docs/SOURCES.md.")


if __name__ == "__main__":
    asyncio.run(main())
