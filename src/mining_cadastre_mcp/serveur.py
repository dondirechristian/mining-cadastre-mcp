"""Serveur MCP — cadastre minier du Burkina Faso.

Trois outils en lecture seule. Le serveur ne modifie jamais rien, n'interprète
rien et ne qualifie rien : il restitue ce que l'autorité publie, en disant d'où
la donnée vient et de quand elle date.
"""

import json

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from . import donnees

serveur = MCPServer(
    name="mining_cadastre_mcp",
    title="Cadastre minier — Burkina Faso",
    version="0.1.0",
    instructions=(
        "Accès en lecture aux listes de titres miniers valides publiées par la "
        "Direction générale du cadastre minier du Burkina Faso. Les listes sont "
        "trimestrielles : une réponse reflète l'état à la date d'édition, pas "
        "l'état du jour. Elles sont extraites de PDF scannés puis océrisés et ne "
        "font pas foi — le registre officiel est la seule référence opposable. "
        "Ces listes ne portent pas la substance exploitée : on peut distinguer "
        "les titres de mines de ceux de carrières, pas l'or du manganèse."
    ),
)


def _reponse(charge: dict, source: dict) -> str:
    """Sérialise une réponse, bloc de provenance systématiquement joint."""
    return json.dumps(
        {**charge, "source": donnees.bloc_source(source)},
        ensure_ascii=False,
        indent=2,
    )


@serveur.tool(
    name="cadastre_list_jurisdictions",
    title="Juridictions couvertes",
    description=(
        "Liste les pays couverts par ce serveur, la source de données de chacun "
        "et l'état de la couverture : édition servie, date de publication, "
        "nombre de titres, catégories présentes. Indique aussi les pays hors "
        "périmètre et pourquoi. À appeler en premier pour savoir ce que ce "
        "serveur peut répondre — et ce qu'il ne peut pas. Les données ne font "
        "pas foi ; le registre officiel de chaque pays reste la seule référence "
        "opposable."
    ),
    annotations=ToolAnnotations(
        title="Juridictions couvertes",
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
async def cadastre_list_jurisdictions() -> str:
    try:
        cat = await donnees.catalogue()
    except donnees.DonneesIntrouvables as exc:
        return json.dumps({"erreur": str(exc)}, ensure_ascii=False, indent=2)

    source = cat["source"]
    categories = [
        {
            "ordre": s.get("ordre"),
            "libelle": s.get("titre"),
            "titres": s.get("lignes"),
        }
        for s in source.get("sections", [])
    ]

    charge = {
        "juridictions": [
            {
                "code": source.get("juridiction"),
                "pays": source.get("pays"),
                "autorite": source.get("autorite"),
                "source": "Listes trimestrielles de titres miniers valides (PDF publié)",
                "portail": "https://www.ecadastreminier.bf/",
                "couverture": "active",
                "edition_servie": source.get("edition"),
                "publiee_le": source.get("publie_le"),
                "periodicite": "trimestrielle : 31 mars, 30 juin, 31 octobre, 31 décembre",
                "titres": source.get("enregistrements"),
                "categories": categories,
                "limites": [
                    "La substance exploitée n'est pas publiée dans ces listes : "
                    "mines et carrières se distinguent, pas l'or du manganèse.",
                    "Aucun périmètre géographique : la localisation se limite aux "
                    "provinces et communes citées.",
                    "Texte issu d'une reconnaissance optique, donc porteur "
                    "d'erreurs de lecture signalées mais non corrigées.",
                ],
            }
        ],
        "hors_perimetre": [
            {
                "pays": "Côte d'Ivoire, Guinée, Togo, Sénégal, RDC",
                "motif": "Portails Landfolio : les couches de titres ne sont pas "
                         "accessibles publiquement, elles sont derrière le proxy du "
                         "portail. Écartés.",
            },
            {
                "pays": "Mali",
                "motif": "Référentiel MCAS public, non encore intégré.",
            },
        ],
    }
    return _reponse(charge, source)


def main() -> None:
    serveur.run(transport="stdio")
