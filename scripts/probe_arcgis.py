"""
Sonde ArcGIS — à exécuter AVANT d'écrire la moindre ligne du serveur MCP.

Objectif : découvrir la structure réelle d'un service de cadastre minier —
couches disponibles, noms de champs, maxRecordCount, un échantillon de
résultats. Les noms de champs varient d'un pays à l'autre et ne se devinent pas.

COMMENT TROUVER L'URL DU SERVICE
  1. Ouvrir le portail cartographique dans le navigateur
  2. Ouvrir les outils de développement (F12), onglet Réseau
  3. Recharger la page, filtrer sur : rest/services
  4. Relever l'URL qui ressemble à :
     https://<hote>/arcgis/rest/services/<dossier>/<service>/MapServer

USAGE
    pip install httpx
    python scripts/probe_arcgis.py "https://.../MapServer"
    python scripts/probe_arcgis.py "https://.../MapServer" --layer 0

Coller ensuite la sortie dans le contexte de Claude Code avant de lui demander
le premier outil réseau.
"""

import argparse
import asyncio
import json

import httpx

TIMEOUT = 30.0
# Un portail ministériel public n'est pas dimensionné pour un agent en boucle.
# Cette sonde fait quelques requêtes, espacées. Ne pas la mettre en boucle.
PAUSE = 1.0


async def get_json(client: httpx.AsyncClient, url: str, **params) -> dict:
    params.setdefault("f", "json")
    response = await client.get(url, params=params)
    response.raise_for_status()
    return response.json()


async def describe_service(client: httpx.AsyncClient, base: str) -> None:
    print(f"\n=== SERVICE {base}")
    info = await get_json(client, base)

    print(f"description   : {info.get('serviceDescription', '(aucune)')[:200]}")
    print(f"maxRecordCount: {info.get('maxRecordCount', '(non déclaré)')}")
    print(f"copyright     : {info.get('copyrightText', '(aucun)')}")
    print(f"spatialRef    : {info.get('spatialReference', {})}")

    layers = info.get("layers", [])
    print(f"\ncouches ({len(layers)}) :")
    for layer in layers:
        print(f"  [{layer.get('id')}] {layer.get('name')}")

    tables = info.get("tables", [])
    if tables:
        print(f"\ntables ({len(tables)}) :")
        for table in tables:
            print(f"  [{table.get('id')}] {table.get('name')}")


async def describe_layer(client: httpx.AsyncClient, base: str, layer_id: int) -> None:
    url = f"{base.rstrip('/')}/{layer_id}"
    print(f"\n=== COUCHE {layer_id}")
    info = await get_json(client, url)

    print(f"nom           : {info.get('name')}")
    print(f"type          : {info.get('type')}")
    print(f"maxRecordCount: {info.get('maxRecordCount', '(non déclaré)')}")
    print(f"pagination    : {info.get('advancedQueryCapabilities', {}).get('supportsPagination')}")

    print("\nchamps :")
    for field in info.get("fields", []):
        alias = field.get("alias", "")
        suffix = f"  ({alias})" if alias and alias != field.get("name") else ""
        print(f"  {field.get('name'):<32} {field.get('type', ''):<24}{suffix}")

    await asyncio.sleep(PAUSE)

    print("\n--- échantillon (5 enregistrements) ---")
    sample = await get_json(
        client,
        f"{url}/query",
        where="1=1",
        outFields="*",
        returnGeometry="false",
        resultRecordCount=5,
    )
    for feature in sample.get("features", []):
        print(json.dumps(feature.get("attributes", {}), indent=2, ensure_ascii=False))

    await asyncio.sleep(PAUSE)

    count = await get_json(client, f"{url}/query", where="1=1", returnCountOnly="true")
    print(f"\nnombre total d'enregistrements : {count.get('count', '(inconnu)')}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Sonde un service ArcGIS REST de cadastre minier.")
    parser.add_argument("url", help="URL du MapServer ou FeatureServer")
    parser.add_argument("--layer", type=int, default=None, help="Identifiant de couche à détailler")
    args = parser.parse_args()

    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=True) as client:
        try:
            await describe_service(client, args.url)
            if args.layer is not None:
                await asyncio.sleep(PAUSE)
                await describe_layer(client, args.url, args.layer)
        except httpx.HTTPStatusError as exc:
            raise SystemExit(f"HTTP {exc.response.status_code} sur {exc.request.url}")
        except httpx.RequestError as exc:
            raise SystemExit(f"Échec réseau : {exc!r}")

    print("\n" + "-" * 60)
    print("À relever avant de coder :")
    print("  - le champ portant le nom du titulaire")
    print("  - le champ portant le code du titre")
    print("  - le champ portant le statut, et ses valeurs possibles")
    print("  - les champs de dates (octroi, expiration) et leur format")
    print("  - maxRecordCount, qui impose la stratégie de pagination")
    print("  - copyrightText, premier indice sur les conditions d'utilisation")


if __name__ == "__main__":
    asyncio.run(main())
