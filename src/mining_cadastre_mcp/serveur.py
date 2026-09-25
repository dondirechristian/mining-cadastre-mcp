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


@serveur.tool(
    name="cadastre_search_licences",
    title="Rechercher des titres miniers",
    description=(
        "Recherche des titres miniers dans la liste publiée par l'autorité. "
        "Tous les critères sont facultatifs et se combinent ; sans critère, rend "
        "le début de la liste. La comparaison ignore la casse et les accents.\n\n"
        "ATTENTION sur deux points. Premièrement, la substance exploitée n'est "
        "PAS publiée dans ces listes : `categorie` porte sur la catégorie de "
        "titre — permis de recherche, exploitation artisanale, mines contre "
        "carrières — et ne permet pas de distinguer l'or du manganèse. "
        "Deuxièmement, le texte provient d'un PDF scanné puis océrisé : une "
        "valeur mal reconnue peut empêcher un rapprochement. Le champ "
        "`anomalies_de_lecture` signale les enregistrements concernés. Rien "
        "n'est corrigé.\n\n"
        "La donnée ne fait pas foi et reflète la date d'édition, pas le jour. Le "
        "registre officiel est la seule référence opposable."
    ),
    annotations=ToolAnnotations(
        title="Rechercher des titres miniers",
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
async def cadastre_search_licences(
    societe: str = "",
    statut: str = "",
    code: str = "",
    categorie: str = "",
    limite: int = 50,
) -> str:
    """Recherche par société, catégorie de titre, statut ou code."""
    try:
        cat = await donnees.catalogue()
    except donnees.DonneesIntrouvables as exc:
        return json.dumps({"erreur": str(exc)}, ensure_ascii=False, indent=2)

    if limite < 1 or limite > 500:
        return json.dumps(
            {
                "erreur": f"limite={limite} hors bornes. Attendu un entier de 1 à 500. "
                          f"La liste servie compte {len(cat['lignes'])} titres."
            },
            ensure_ascii=False,
            indent=2,
        )

    q_societe = donnees.replier(societe)
    q_statut = donnees.replier(statut)
    q_code = donnees.replier(code)
    q_categorie = donnees.replier(categorie)

    trouves = []
    for ligne in cat["lignes"]:
        if q_societe and q_societe not in donnees.replier(ligne.get("detenteur_plat", "")):
            continue
        if q_code and q_code not in donnees.replier(ligne.get("code_plat", "")):
            continue
        # `categorie` se compare sur des frontières de mot : « or » ne doit pas
        # répondre sur « AUTORISATIONS ». Voir donnees.contient_mots.
        if categorie and not donnees.contient_mots(ligne.get("section_titre", ""), categorie):
            continue
        if q_statut:
            # Le statut se compare à la valeur canonique ET à la forme imprimée :
            # un statut mal océrisé reste trouvable par ce que le document montre.
            cibles = (
                donnees.replier(ligne.get("statut_normalise", "")),
                donnees.replier(ligne.get("statut_plat", "")),
            )
            if not any(q_statut in c for c in cibles if c):
                continue
        trouves.append(ligne)

    charge = {
        "criteres": {
            "societe": societe or None,
            "statut": statut or None,
            "code": code or None,
            "categorie": categorie or None,
            "limite": limite,
        },
        "total_trouves": len(trouves),
        "rendus": min(len(trouves), limite),
        "titres": [donnees.titre_public(l) for l in trouves[:limite]],
    }
    if len(trouves) > limite:
        charge["troncature"] = (
            f"{len(trouves)} titres correspondent, {limite} sont rendus. "
            f"Préciser les critères, ou relever `limite` jusqu'à 500."
        )
    if not trouves:
        charge["aucun_resultat"] = (
            "Aucun titre ne correspond. Vérifier l'orthographe du détenteur, ou "
            "élargir en retirant un critère. Rappel : la substance n'est pas "
            "publiée dans ces listes, et une valeur mal océrisée peut empêcher "
            "un rapprochement. `cadastre_list_jurisdictions` donne les catégories "
            "disponibles et leur libellé exact."
        )
        if categorie:
            charge["categories_disponibles"] = [
                s.get("titre") for s in cat["source"].get("sections", [])
            ]
    return _reponse(charge, cat["source"])


@serveur.tool(
    name="cadastre_get_licence",
    title="Détail d'un titre minier",
    description=(
        "Rend le détail d'un titre minier par son code, l'identifiant numérique "
        "que porte la liste publiée. Ce code est stable d'une édition à l'autre : "
        "c'est la clé pour suivre un titre dans le temps.\n\n"
        "Le code doit correspondre exactement. Pour le trouver, passer par "
        "`cadastre_search_licences`. Si plusieurs enregistrements portent le même "
        "code — ce qui signale une anomalie de lecture dans la source — ils sont "
        "tous rendus, sans qu'aucun soit choisi à la place de l'appelant.\n\n"
        "Le texte vient d'un PDF scanné puis océrisé ; `anomalies_de_lecture` "
        "signale ce qui est douteux, rien n'est corrigé. La donnée reflète la "
        "date d'édition et ne fait pas foi : le registre officiel est la seule "
        "référence opposable. Ne pas s'en servir pour vérifier un titre sans "
        "confirmer auprès de l'autorité citée."
    ),
    annotations=ToolAnnotations(
        title="Détail d'un titre minier",
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=False,
    ),
)
async def cadastre_get_licence(code: str) -> str:
    """Détail d'un titre par son code."""
    try:
        cat = await donnees.catalogue()
    except donnees.DonneesIntrouvables as exc:
        return json.dumps({"erreur": str(exc)}, ensure_ascii=False, indent=2)

    recherche = donnees.replier(code)
    if not recherche:
        return json.dumps(
            {
                "erreur": "Le paramètre `code` est obligatoire et ne peut être vide. "
                          "C'est l'identifiant numérique du titre, par exemple « 4417 ». "
                          "Utiliser `cadastre_search_licences` pour le trouver."
            },
            ensure_ascii=False,
            indent=2,
        )

    exacts = [l for l in cat["lignes"] if donnees.replier(l.get("code_plat", "")) == recherche]

    if not exacts:
        # Le code cherché figure peut-être dans une cellule que l'OCR a salie
        # (« 4360 . », « 3751 SIB »). On le signale comme piste, sans décider
        # qu'il s'agit du même titre.
        approchants = [
            donnees.titre_public(l)
            for l in cat["lignes"]
            if recherche in donnees.replier(l.get("code_plat", ""))
        ]
        charge = {
            "code_demande": code,
            "trouve": False,
            "message": (
                f"Aucun titre ne porte exactement le code « {code} » dans l'édition "
                f"{cat['source'].get('edition')} ({cat['source'].get('enregistrements')} "
                f"titres). Un titre absent de cette liste peut être expiré, non encore "
                f"publié, ou son code mal reconnu par l'OCR."
            ),
        }
        if approchants:
            charge["codes_contenant_la_valeur"] = approchants
            charge["avertissement_rapprochement"] = (
                "Ces enregistrements contiennent la valeur demandée dans un code "
                "abîmé par la reconnaissance optique. Le serveur ne décide PAS "
                "qu'il s'agit du titre cherché : à vérifier sur le document, page "
                "indiquée."
            )
        return _reponse(charge, cat["source"])

    charge = {
        "code_demande": code,
        "trouve": True,
        "titre": donnees.titre_public(exacts[0]),
    }
    if len(exacts) > 1:
        charge["titre"] = None
        charge["titres_homonymes"] = [donnees.titre_public(l) for l in exacts]
        charge["avertissement_homonymie"] = (
            f"{len(exacts)} enregistrements portent le code « {code} » dans la même "
            f"édition. Un code est censé être unique : c'est une anomalie de la "
            f"source ou de sa lecture. Tous sont rendus, aucun n'est choisi."
        )
    return _reponse(charge, cat["source"])


def main() -> None:
    serveur.run(transport="stdio")
