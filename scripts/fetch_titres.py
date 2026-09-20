"""
Récupère la dernière liste de titres miniers valides publiée par la Direction
générale du cadastre minier (DGCM), Ministère de l'Énergie, des Mines et des
Carrières du Burkina Faso, et décrit ce qui a été téléchargé.

Ce script NE PARSE PAS les tableaux. Le format est désormais connu — PDF scanné
puis passé à l'OCR — mais l'extraction fait l'objet d'une étape séparée. Voir
`describe_structure()`, qui porte la spécification de ce qui devra en sortir.

LOCALISATION DES ÉDITIONS
Le site est un WordPress. Chaque édition trimestrielle fait l'objet d'un article
dont le contenu porte le lien du PDF. L'API REST les expose :
    /wp-json/wp/v2/posts?search=titres+miniers+valides
Le nom de fichier n'est PAS normalisé d'une édition à l'autre — voir la note
dans docs/SOURCES.md. Une URL ne se construit donc pas à partir d'une date :
elle se découvre.

USAGE
    python scripts/fetch_titres.py                 découvre et prend la plus récente
    python scripts/fetch_titres.py --list          liste les éditions, sans télécharger
    python scripts/fetch_titres.py <url>           force une édition précise
    python scripts/fetch_titres.py --pinned        prend SOURCE_URL, sans découverte
    python scripts/fetch_titres.py --out data/
"""

import argparse
import asyncio
import hashlib
import re
from pathlib import Path
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import httpx

# Page de publication de la DGCM. Les fichiers sont déposés sous
# wp-content/uploads/AAAA/MM/.
PUBLICATION_PAGE = "https://www.ecadastreminier.bf/"

# API REST WordPress : c'est par là que se détectent les nouvelles éditions.
WP_POSTS_ENDPOINT = "https://www.ecadastreminier.bf/wp-json/wp/v2/posts"
DISCOVERY_SEARCH = "titres miniers valides"

# Dernière édition connue au 20 septembre 2026, publiée le 10 juillet 2026.
# Sert de repli avec --pinned. La découverte reste la voie normale : ce lien
# vieillira au prochain trimestre.
SOURCE_URL = (
    "https://www.ecadastreminier.bf/wp-content/uploads/2026/07/"
    "Titres_Miniers_valides_au_30_juin_2026 (1) (1).pdf"
)

# Édition de référence sur laquelle la structure a été vérifiée par le
# mainteneur (30 juin 2025) :
#   https://www.ecadastreminier.bf/wp-content/uploads/2025/07/
#   LISTE%20DES%20TITRES%20MINIERS%20VALIDES%20AU%2030%20JUIN%202025.pdf

# PDF **scanné, passé à l'OCR** — pas un PDF texte natif. Conséquence directe
# pour l'étape d'extraction : le texte est le produit d'une reconnaissance, il
# porte donc des erreurs de lecture. Ce n'est pas une source fiable caractère
# par caractère.
EXPECTED_FORMAT = "PDF (scan + OCR)"

# Publication trimestrielle : 31 mars, 30 juin, 31 octobre, 31 décembre.
# L'article paraît quelques jours à quelques semaines après la date d'arrêt.
PERIODICITE = ("31 mars", "30 juin", "31 octobre", "31 décembre")

TIMEOUT = 30.0
DEFAULT_OUT = Path("data")
USER_AGENT = "mining-cadastre-mcp/0.1 (+https://github.com/sotechdi/mining-cadastre-mcp)"

# Signatures de fichiers, à seule fin de CONSTAT.
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
    return "".join(chr(b) if 32 <= b < 127 else "." for b in head[:length])


def normalise_url(url: str) -> str:
    """Encode les espaces et parenthèses du chemin, sans ré-encoder les %XX."""
    parts = urlsplit(url)
    return urlunsplit(
        (parts.scheme, parts.netloc, quote(parts.path, safe="/%~"), parts.query, parts.fragment)
    )


async def discover_editions(client: httpx.AsyncClient) -> list[dict]:
    """Liste les éditions publiées, la plus récente d'abord.

    Ne devine aucune URL : lit le lien tel qu'il figure dans l'article.
    """
    try:
        response = await client.get(
            WP_POSTS_ENDPOINT,
            params={"search": DISCOVERY_SEARCH, "per_page": 20, "orderby": "date", "order": "desc"},
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise SystemExit(
            f"HTTP {exc.response.status_code} sur l'API REST du site.\n"
            "Contourner la découverte en passant l'URL du PDF en argument, ou avec --pinned."
        )
    except httpx.RequestError as exc:
        raise SystemExit(
            f"Échec réseau sur l'API REST : {exc!r}\n"
            "Le site de la DGCM est parfois indisponible. Réessayer, ou utiliser --pinned."
        )

    editions = []
    for post in response.json():
        html = post.get("content", {}).get("rendered", "")
        pdfs = list(dict.fromkeys(re.findall(r'href="([^"]+\.pdf)"', html, re.I)))
        editions.append(
            {
                "titre": re.sub("<[^>]+>", "", post.get("title", {}).get("rendered", "")).strip(),
                "publie_le": post.get("date", ""),
                "article": post.get("link", ""),
                "pdf": pdfs[0] if pdfs else None,
                "pdf_multiples": pdfs[1:],
            }
        )
    return editions


async def fetch(client: httpx.AsyncClient, url: str, out_dir: Path) -> Path:
    print(f"=== TÉLÉCHARGEMENT\nurl demandée  : {url}")

    try:
        response = await client.get(normalise_url(url))
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise SystemExit(
            f"HTTP {exc.response.status_code} sur {exc.request.url}\n"
            "Vérifier que l'URL pointe bien vers le fichier publié, et non vers "
            "une page qui exige une session. Le nom de fichier change d'une "
            "édition à l'autre : relancer sans argument pour le redécouvrir."
        )
    except httpx.RequestError as exc:
        raise SystemExit(
            f"Échec réseau : {exc!r}\n"
            "Le site de la DGCM est parfois indisponible. Réessayer plus tard."
        )

    body = response.content

    print(f"url finale    : {response.url}")
    print(f"statut        : {response.status_code}")
    print(f"content-type  : {response.headers.get('content-type', '(absent)')}")
    print(f"disposition   : {response.headers.get('content-disposition', '(absent)')}")
    print(f"last-modified : {response.headers.get('last-modified', '(absent)')}")
    print(f"taille        : {len(body)} octets ({len(body) / 1_048_576:.2f} Mo)")
    print(f"sha256        : {hashlib.sha256(body).hexdigest()}")

    out_dir.mkdir(parents=True, exist_ok=True)
    # Le nom publié est percent-encodé et porte parfois des suffixes de
    # ré-upload (« (1) »). On le décode pour le disque, sans le réécrire :
    # c'est le nom du document tel que publié.
    name = unquote(Path(urlsplit(str(response.url)).path).name) or "titres_burkina.pdf"
    destination = out_dir / name
    destination.write_bytes(body)
    print(f"enregistré    : {destination}")

    print("\n=== CONSTAT SUR LE CONTENU")
    print(f"signature     : {identify(body[:16])}")
    print(f"format attendu: {EXPECTED_FORMAT}")
    print(f"256 premiers octets, caractères imprimables :\n{preview(body)}")

    return destination


def describe_structure(path: Path) -> None:
    """Décrit la structure du PDF : les neuf listes, leurs colonnes, un échantillon.

    NON IMPLÉMENTÉ — étape suivante, commit séparé.

    Structure réelle, vérifiée par le mainteneur sur l'édition du 30 juin 2025.
    Ne rien deviner au-delà de ceci ; revérifier sur l'édition traitée.

    Un seul PDF contient NEUF listes, chacune sous son propre numéro d'arrêté :
      1. Autorisations d'exploitation artisanale de substances de carrières
      2. Autorisations d'exploitation artisanale de substances de mines
      3. Autorisations de prospection
      4. Autorisations de recherche de gîte de substances de carrières
      5. Permis d'exploitation industrielle de mines
      6. Permis d'exploitation industrielle permanente de substances de carrières
      7. Permis d'exploitation semi-mécanisée de substances de carrières
      8. Permis d'exploitation semi-mécanisée de substances de mines
      9. Permis de recherche

    Colonnes identiques dans les neuf listes :
      No | CODE | NOM | STATUT | DETENTEUR | DATE D'OCTROI | DATE D'EXPIRATION
         | PROVINCES | COMMUNES

    Règles de lecture :
      - CODE : identifiant numérique stable entre éditions. C'est la clé de
        jointure. Ne JAMAIS le reconstruire ni le normaliser.
      - STATUT : « valide », « En renouvellement », « Suspendu ». Casse telle
        quelle dans le document.
      - Dates au format JJ/MM/AAAA.
      - PROVINCES et COMMUNES peuvent porter plusieurs valeurs séparées par
        « / » ou « , ». Conserver la chaîne brute ET une version découpée.
      - Le texte vient d'un OCR : il porte des erreurs de reconnaissance. Tout
        écart doit remonter tel quel, jamais être corrigé silencieusement.

    Cette fonction devra afficher, par liste : le numéro d'arrêté, le nombre
    d'enregistrements, trois enregistrements bruts, les valeurs distinctes de
    STATUT réellement rencontrées, et la date d'arrêt portée par le document.
    """
    raise NotImplementedError(
        f"Extraction des tableaux non implémentée — étape suivante, commit séparé.\n"
        f"Fichier téléchargé : {path}\n"
        "Le format est connu (PDF scanné + OCR) et la structure est documentée dans "
        "la docstring de describe_structure(). Reste à arbitrer avec le mainteneur "
        "la bibliothèque d'extraction, qui sera une dépendance nouvelle."
    )


def print_editions(editions: list[dict]) -> None:
    print(f"=== ÉDITIONS PUBLIÉES ({len(editions)})")
    print(f"source : {WP_POSTS_ENDPOINT}?search={DISCOVERY_SEARCH.replace(' ', '+')}")
    for edition in editions:
        print(f"\n- {edition['titre']}")
        print(f"  publié le : {edition['publie_le']}")
        print(f"  article   : {edition['article']}")
        print(f"  pdf       : {edition['pdf'] or '(aucun lien .pdf dans cet article)'}")
        if edition["pdf_multiples"]:
            print(f"  ATTENTION : {len(edition['pdf_multiples'])} autres PDF dans le même article")


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Télécharge la dernière liste de titres miniers valides du Burkina Faso."
    )
    parser.add_argument("url", nargs="?", default=None, help="URL d'une édition précise")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Répertoire de destination")
    parser.add_argument("--list", action="store_true", help="Lister les éditions, sans télécharger")
    parser.add_argument("--pinned", action="store_true", help="Utiliser SOURCE_URL, sans découverte")
    parser.add_argument(
        "--describe", action="store_true", help="Décrire la structure (pas encore implémenté)"
    )
    args = parser.parse_args()

    async with httpx.AsyncClient(
        timeout=TIMEOUT, follow_redirects=True, headers={"User-Agent": USER_AGENT}
    ) as client:
        if args.list:
            print_editions(await discover_editions(client))
            return

        if args.url:
            url = args.url
        elif args.pinned:
            url = SOURCE_URL
            print(f"=== ÉDITION ÉPINGLÉE (--pinned)\n{url}\n")
        else:
            editions = await discover_editions(client)
            latest = next((e for e in editions if e["pdf"]), None)
            if latest is None:
                raise SystemExit(
                    "Aucune édition portant un lien .pdf n'a été trouvée via l'API REST.\n"
                    f"Vérifier à la main sur {PUBLICATION_PAGE}, puis passer l'URL en "
                    "argument, ou utiliser --pinned."
                )
            print(f"=== ÉDITION LA PLUS RÉCENTE\ntitre     : {latest['titre']}")
            print(f"publié le : {latest['publie_le']}")
            print(f"article   : {latest['article']}\n")
            url = latest["pdf"]

        await asyncio.sleep(1.0)
        destination = await fetch(client, url, args.out)

    print("\n" + "-" * 60)
    if args.describe:
        try:
            describe_structure(destination)
        except NotImplementedError as exc:
            raise SystemExit(str(exc))
    else:
        print("Structure attendue documentée dans describe_structure().")
        print("Périodicité : " + ", ".join(PERIODICITE) + ".")
        print("Relancer avec --describe une fois l'extraction implémentée.")


if __name__ == "__main__":
    asyncio.run(main())
