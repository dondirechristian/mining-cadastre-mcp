"""Démonstration filmable : une vraie session MCP, rythmée pour l'écran.

Tous les appels sont RÉELS. Rien n'est rejoué ni mis en scène : si le serveur
échoue, la démonstration échoue. C'est le point — une capture d'écran doit
pouvoir être refaite.

Le scénario tient en quatre temps, choisis pour montrer autant ce que le
serveur sait faire que ce qu'il refuse de faire :

    1. le serveur démarre et annonce ses trois outils
    2. une question à laquelle il répond, avec sa provenance
    3. une question à laquelle il REFUSE de répondre — les permis d'or
    4. un code abîmé par l'OCR : une piste, pas une conclusion

USAGE
    python scripts/demo.py                 rythme par défaut, pour filmer
    python scripts/demo.py --pause 0       sans pause, pour vérifier
    python scripts/demo.py --largeur 72    adapter à la largeur du terminal
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

RACINE = Path(__file__).resolve().parents[1]


class Scene:
    def __init__(self, pause: float, largeur: int) -> None:
        self.pause = pause
        self.largeur = largeur

    def _attendre(self, facteur: float = 1.0) -> None:
        if self.pause:
            time.sleep(self.pause * facteur)

    def titre(self, texte: str) -> None:
        print(f"\n\033[1;36m{'─' * self.largeur}\033[0m")
        print(f"\033[1;36m {texte}\033[0m")
        print(f"\033[1;36m{'─' * self.largeur}\033[0m")
        self._attendre()

    def demande(self, texte: str) -> None:
        print(f"\n\033[1;33m? {texte}\033[0m")
        self._attendre(1.5)

    def appel(self, outil: str, args: dict) -> None:
        rendu = json.dumps(args, ensure_ascii=False)
        print(f"\033[2m  → {outil}({rendu})\033[0m")
        self._attendre()

    def dire(self, texte: str = "", style: str = "") -> None:
        codes = {"gras": "1", "vert": "32", "rouge": "31", "gris": "2", "jaune": "33"}
        if style:
            print(f"\033[{codes.get(style, '0')}m{texte}\033[0m")
        else:
            print(texte)

    def bloc(self, charge: dict, cles: list[str]) -> None:
        extrait = {k: charge[k] for k in cles if k in charge}
        for ligne in json.dumps(extrait, ensure_ascii=False, indent=2).splitlines():
            print(f"  {ligne}")
            self._attendre(0.04)


async def jouer(scene: Scene) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(RACINE / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    params = StdioServerParameters(
        command=sys.executable, args=["-m", "mining_cadastre_mcp"],
        cwd=str(RACINE), env=env,
    )

    async with stdio_client(params) as (lecture, ecriture):
        async with ClientSession(lecture, ecriture) as session:
            init = await session.initialize()
            outils = (await session.list_tools()).tools

            scene.titre("mining-cadastre-mcp — cadastre minier du Burkina Faso")
            scene.dire(f"  serveur   {init.server_info.name} {init.server_info.version}", "gras")
            scene.dire(f"  protocole {init.protocol_version}", "gris")
            scene.dire()
            for outil in outils:
                scene.dire(f"  ▸ {outil.name}", "vert")
                scene._attendre(0.6)

            # --- 1. ce que le serveur couvre
            scene.demande("Que couvre ce serveur ?")
            scene.appel("cadastre_list_jurisdictions", {})
            r = json.loads(
                (await session.call_tool("cadastre_list_jurisdictions", {})).content[0].text
            )
            j = r["juridictions"][0]
            scene.dire(f"  {j['pays']} — édition du {j['edition_servie']}, "
                       f"{j['titres']} titres, {len(j['categories'])} catégories", "gras")
            scene.dire(f"  publiée le {j['publiee_le']}", "gris")
            scene.dire()
            scene.dire("  ⚠ ce n'est pas l'édition la plus récente :", "jaune")
            for e in j["editions_publiees_depuis"]:
                scene.dire(f"    {e['edition']} publiée le {e['publiee_le']}, non servie", "jaune")
            scene._attendre(2)

            # --- 2. une réponse, avec sa provenance
            scene.demande("Qui détient le titre 4417, et jusqu'à quand ?")
            scene.appel("cadastre_get_licence", {"code": "4417"})
            r = json.loads(
                (await session.call_tool("cadastre_get_licence", {"code": "4417"})).content[0].text
            )
            t = r["titre"]
            scene.dire(f"  {t['nom']} — {t['detenteur']}", "gras")
            scene.dire(f"  {t['statut_normalise']} · octroyé le {t['date_octroi']} · "
                       f"expire le {t['date_expiration']}")
            scene.dire(f"  {t['provinces']} / {t['communes']}", "gris")
            scene.dire()
            s = r["source"]
            scene.dire(f"  source : {s['autorite'][:58]}…", "gris")
            scene.dire(f"           édition {s['edition']}, publiée {s['publiee_le']}, "
                       f"lue {s['lue_le']}", "gris")
            scene.dire(f"           page {t['page_du_document']} du document publié", "gris")
            scene._attendre(2)

            # --- 3. ce que le serveur refuse
            scene.demande("Quelles sociétés détiennent des permis d'or ?")
            scene.appel("cadastre_search_licences", {"categorie": "or"})
            r = json.loads(
                (await session.call_tool(
                    "cadastre_search_licences", {"categorie": "or"}
                )).content[0].text
            )
            scene.dire(f"  {r['total_trouves']} résultat", "rouge")
            scene.dire()
            scene.dire("  La substance exploitée n'est PAS publiée dans ces listes.", "rouge")
            scene.dire("  Mines et carrières se distinguent — pas l'or du manganèse.", "rouge")
            scene.dire("  Le serveur le dit plutôt que de deviner.", "rouge")
            scene._attendre(2.5)

            # --- 4. une piste, pas une conclusion
            scene.demande("Et le titre 4360 ?")
            scene.appel("cadastre_get_licence", {"code": "4360"})
            r = json.loads(
                (await session.call_tool("cadastre_get_licence", {"code": "4360"})).content[0].text
            )
            scene.dire("  Aucune correspondance exacte.", "jaune")
            piste = r["codes_contenant_la_valeur"][0]
            scene.dire(f"  Un enregistrement porte le code {piste['code']!r} — "
                       f"{piste['nom']}, page {piste['page_du_document']}.", "jaune")
            scene.dire()
            scene.dire("  Le code est abîmé par la reconnaissance optique.", "gris")
            scene.dire("  Le serveur donne la piste. Il ne conclut pas à votre place.", "gras")
            scene._attendre(2)

            scene.titre("Trois outils en lecture seule · la source citée à chaque réponse")
            scene.dire("  Le registre officiel reste la seule référence opposable.", "gris")
            scene._attendre(2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Démonstration filmable du serveur.")
    parser.add_argument("--pause", type=float, default=0.9, help="Rythme, en secondes")
    parser.add_argument("--largeur", type=int, default=76, help="Largeur des séparateurs")
    args = parser.parse_args()
    asyncio.run(jouer(Scene(args.pause, args.largeur)))


if __name__ == "__main__":
    main()
