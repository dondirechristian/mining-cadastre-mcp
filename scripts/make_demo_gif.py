"""Rend le GIF de démonstration à partir d'une exécution réelle du serveur.

Pas une capture d'écran : les images sont dessinées à partir du journal écrit
par `scripts/demo.py --journal`. Le CONTENU vient donc d'une vraie session MCP
— si le serveur ne répond pas, il n'y a pas de journal et donc pas de GIF.
Seul le rendu est synthétique, ce qui a l'avantage d'être reproductible à
l'identique et de ne dépendre d'aucun logiciel de capture.

Pillow suffit : il est déjà là, en dépendance de pdfplumber.

USAGE
    python scripts/demo.py --pause 0 --journal docs/demo.json
    python scripts/make_demo_gif.py docs/demo.json --sortie docs/demo.gif
"""

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

# Palette proche du thème sombre de GitHub, pour que le GIF s'intègre au README.
FOND = (13, 17, 23)
COULEURS = {
    "": (201, 209, 217),
    "gras": (255, 255, 255),
    "gris": (110, 118, 129),
    "vert": (86, 211, 100),
    "rouge": (255, 123, 114),
    "jaune": (227, 179, 65),
    "titre": (121, 192, 255),
    "demande": (255, 215, 120),
}
GRAS = {"gras", "titre", "demande"}

POLICES = (
    r"C:\Windows\Fonts\CascadiaMono.ttf",
    r"C:\Windows\Fonts\consola.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    "/System/Library/Fonts/Menlo.ttc",
)


def charger_police(taille: int) -> ImageFont.FreeTypeFont:
    for chemin in POLICES:
        if Path(chemin).is_file():
            return ImageFont.truetype(chemin, taille)
    raise SystemExit(
        "Aucune police à chasse fixe trouvée.\n"
        "Emplacements essayés :\n  " + "\n  ".join(POLICES) + "\n"
        "Ajouter le chemin d'une police .ttf dans POLICES."
    )


def rendre(
    journal: list[dict], sortie: Path, lignes_visibles: int, taille: int, echelle: float
) -> None:
    police = charger_police(taille)
    # Chasse fixe : une seule mesure suffit pour toute la grille.
    boite = police.getbbox("M")
    largeur_car = boite[2] - boite[0]
    hauteur_ligne = taille + 6

    colonnes = max((len(e["texte"]) for e in journal), default=80) + 4
    largeur = colonnes * largeur_car + 2 * largeur_car
    hauteur = lignes_visibles * hauteur_ligne + 2 * hauteur_ligne

    images: list[Image.Image] = []
    durees: list[int] = []
    fenetre: list[dict] = []

    for evenement in journal:
        fenetre.append(evenement)
        if len(fenetre) > lignes_visibles:
            fenetre = fenetre[-lignes_visibles:]

        image = Image.new("RGB", (largeur, hauteur), FOND)
        dessin = ImageDraw.Draw(image)
        for i, ligne in enumerate(fenetre):
            y = hauteur_ligne + i * hauteur_ligne
            couleur = COULEURS.get(ligne["style"], COULEURS[""])
            dessin.text((largeur_car, y), ligne["texte"], font=police, fill=couleur)
            if ligne["style"] in GRAS:
                # Faux gras : un second tracé décalé d'un pixel. Évite d'exiger
                # une seconde fonte installée sur la machine.
                dessin.text((largeur_car + 1, y), ligne["texte"], font=police, fill=couleur)

        images.append(image.convert("P", palette=Image.ADAPTIVE, colors=64))
        durees.append(max(4, int(evenement["pause"] * echelle * 100)))

    if not images:
        raise SystemExit("Journal vide : rien à rendre.")

    durees[-1] = max(durees[-1], 250)  # tenir la dernière image avant la boucle
    sortie.parent.mkdir(parents=True, exist_ok=True)
    images[0].save(
        sortie,
        save_all=True,
        append_images=images[1:],
        duration=durees,
        loop=0,
        optimize=True,
        disposal=2,
    )

    total = sum(durees) / 100
    poids = sortie.stat().st_size
    print(f"{sortie} — {len(images)} images, {largeur}×{hauteur} px, "
          f"{total:.1f} s, {poids / 1024:.0f} Ko")
    if poids > 3 * 1024 * 1024:
        print(
            "ATTENTION : au-delà de 3 Mo, GitHub peut refuser d'animer le GIF.\n"
            "  Réduire --taille, --lignes, ou abaisser --echelle."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Rend le GIF depuis un journal de démonstration.")
    parser.add_argument("journal", type=Path, help="JSON produit par demo.py --journal")
    parser.add_argument("--sortie", type=Path, default=Path("docs/demo.gif"))
    parser.add_argument("--lignes", type=int, default=24, help="Lignes visibles à l'écran")
    parser.add_argument("--taille", type=int, default=15, help="Corps de la police, en pixels")
    parser.add_argument("--echelle", type=float, default=0.45, help="Facteur sur les pauses")
    args = parser.parse_args()

    if not args.journal.is_file():
        raise SystemExit(
            f"Journal introuvable : {args.journal}\n"
            "Le produire d'abord, depuis une exécution réelle :\n"
            "  python scripts/demo.py --pause 0 --journal docs/demo.json"
        )
    rendre(
        json.loads(args.journal.read_text(encoding="utf-8")),
        args.sortie, args.lignes, args.taille, args.echelle,
    )


if __name__ == "__main__":
    main()
