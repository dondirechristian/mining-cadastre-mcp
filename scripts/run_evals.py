"""Exécute `evals/questions.xml` contre le serveur, en vrai.

Ouvre une session MCP sur stdio, appelle chaque outil avec les arguments écrits
dans le fichier, et évalue chaque assertion sur la réponse obtenue. Aucune
réponse n'est simulée : si le serveur ne démarre pas, les évaluations échouent.

USAGE
    python scripts/run_evals.py
    python scripts/run_evals.py --question Q06
    python scripts/run_evals.py --verbeux
"""

import argparse
import asyncio
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

RACINE = Path(__file__).resolve().parents[1]
QUESTIONS = RACINE / "evals" / "questions.xml"


def resoudre(charge, chemin: str):
    """Suit un chemin pointé avec indices : `titres[0].detenteur`.

    Rend le sentinelle `ABSENT` si le chemin n'existe pas, pour qu'une assertion
    sur une clé manquante échoue proprement au lieu de lever.
    """
    courant = charge
    for morceau in chemin.split("."):
        nom, indices = re.match(r"([^\[]*)((?:\[\d+\])*)", morceau).groups()
        if nom:
            if not isinstance(courant, dict) or nom not in courant:
                return ABSENT
            courant = courant[nom]
        for i in re.findall(r"\[(\d+)\]", indices):
            if not isinstance(courant, list) or int(i) >= len(courant):
                return ABSENT
            courant = courant[int(i)]
    return courant


class _Absent:
    def __repr__(self) -> str:
        return "<absent>"


ABSENT = _Absent()


def verifier(assertion: ET.Element, charge) -> tuple[bool, str]:
    chemin = assertion.get("chemin", "")
    obtenu = resoudre(charge, chemin)

    if (attendu := assertion.get("egal")) is not None:
        if attendu in ("True", "False"):
            ok = obtenu is (attendu == "True")
        else:
            # Comparaison sur les deux formes : un code est une chaîne (« 38 »),
            # un décompte un entier (383). Le fichier d'évaluation, lui, ne peut
            # écrire que du texte — il ne doit pas avoir à connaître le type.
            ok = obtenu == attendu or str(obtenu) == attendu
        return ok, f"{chemin} = {obtenu!r} ({type(obtenu).__name__}), attendu {attendu!r}"

    if (fragment := assertion.get("contient")) is not None:
        ok = isinstance(obtenu, str) and fragment in obtenu
        extrait = obtenu[:70] if isinstance(obtenu, str) else obtenu
        return ok, f"{chemin} contient {fragment!r} ? obtenu {extrait!r}"

    if (n := assertion.get("longueur")) is not None:
        ok = isinstance(obtenu, (list, dict, str)) and len(obtenu) == int(n)
        taille = len(obtenu) if isinstance(obtenu, (list, dict, str)) else None
        return ok, f"len({chemin}) = {taille}, attendu {n}"

    if assertion.get("present") is not None:
        ok = obtenu is not ABSENT and obtenu not in (None, "", [], {})
        return ok, f"{chemin} présent ? {obtenu is not ABSENT}"

    if assertion.get("absent") is not None:
        return obtenu is ABSENT, f"{chemin} absent ? {obtenu is ABSENT}"

    return False, f"assertion sans critère reconnu sur {chemin}"


async def executer(questions: list[ET.Element], verbeux: bool) -> int:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(RACINE / "src") + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mining_cadastre_mcp"],
        cwd=str(RACINE),
        env=env,
    )

    echecs = 0
    async with stdio_client(params) as (lecture, ecriture):
        async with ClientSession(lecture, ecriture) as session:
            init = await session.initialize()
            outils = {t.name for t in (await session.list_tools()).tools}
            print(f"serveur   : {init.server_info.name} {init.server_info.version}")
            print(f"protocole : {init.protocol_version}")
            print(f"outils    : {len(outils)} — {', '.join(sorted(outils))}")
            print("=" * 78)

            for q in questions:
                ident = q.get("id")
                enjeu = q.get("enjeu", "")
                appel = q.find("appel")
                outil = appel.get("outil")
                args = json.loads((appel.text or "{}").strip())

                if outil not in outils:
                    print(f"\n{ident} ÉCHEC — outil inconnu : {outil}")
                    echecs += 1
                    continue

                reponse = await session.call_tool(outil, args)
                charge = json.loads(reponse.content[0].text)

                resultats = [verifier(a, charge) for a in q.findall("attendu/assertion")]
                rates = [m for ok, m in resultats if not ok]
                marque = "OK   " if not rates else "ÉCHEC"
                print(f"\n{marque} {ident} [{enjeu}]")
                print(f"      {(q.findtext('demande') or '').strip()}")
                print(f"      {outil}({json.dumps(args, ensure_ascii=False)})"
                      f" — {len(resultats)} assertions")
                if verbeux:
                    for ok, message in resultats:
                        print(f"        {'.' if ok else 'X'} {message}")
                for message in rates:
                    print(f"        X {message}")
                echecs += bool(rates)

    print("\n" + "=" * 78)
    total = len(questions)
    print(f"{total - echecs} / {total} questions vérifiées contre le serveur")
    if echecs:
        print(
            f"{echecs} en échec. Une valeur attendue a changé : soit le serveur a "
            f"régressé, soit l'instantané servi n'est plus l'édition du fichier "
            f"d'évaluation. Vérifier l'attribut `edition` de questions.xml."
        )
    return echecs


def main() -> None:
    parser = argparse.ArgumentParser(description="Exécute les évaluations contre le serveur.")
    parser.add_argument("--question", action="append", help="N'exécuter que cet identifiant")
    parser.add_argument("--verbeux", action="store_true", help="Afficher chaque assertion")
    args = parser.parse_args()

    if not QUESTIONS.is_file():
        raise SystemExit(f"Fichier d'évaluations introuvable : {QUESTIONS}")

    racine = ET.parse(QUESTIONS).getroot()
    questions = racine.findall("question")
    if args.question:
        voulus = set(args.question)
        questions = [q for q in questions if q.get("id") in voulus]
        if not questions:
            raise SystemExit(
                f"Aucune question ne porte cet identifiant. Disponibles : "
                f"{', '.join(q.get('id') for q in racine.findall('question'))}"
            )

    print(f"édition attendue : {racine.get('edition')}  (vérifiée le {racine.get('verifie_le')})")
    raise SystemExit(asyncio.run(executer(questions, args.verbeux)))


if __name__ == "__main__":
    main()
