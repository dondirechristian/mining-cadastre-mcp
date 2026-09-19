# mining-cadastre-mcp

**MCP server for West African mining cadastres.**
Give your AI agent read access to public mining licence registries — permit
holders, commodities, status, expiry — across West Africa.

> Status: v0.1 in development. Not yet usable.

<!-- TODO: GIF de démonstration avant la première publication -->

## Why this exists

Mining licence data across West Africa is public, but scattered across a dozen
government portals, each with its own map interface and no shared entry point.
Answering a question as simple as *"which companies hold gold exploration
permits in this country, and when do they expire?"* means visiting several
sites by hand.

No MCP server exposes this data — in any region of the world. This one does it
for West Africa first.

Most of these portals run on the same underlying platform, which means one
integration covers many countries.

## Tools

| Tool | Description |
|---|---|
| `cadastre_list_jurisdictions` | Countries covered, data source, coverage status |
| `cadastre_search_licences` | Search by company, commodity, status or licence code |
| `cadastre_get_licence` | Full detail of a single licence |

All three are read-only. This server never writes anything.

## Data and accuracy

This server reads **official public registries only**. Every response carries
its source and the date it was read.

It is a convenience layer, not a legal reference. The official registry of each
country remains the only authoritative record. Do not rely on this server for
title verification, due diligence, or any decision with legal or financial
consequence without confirming against the source.

The server reports what the registries publish. It does not interpret, score,
rank or cross-reference.

## Coverage

See `docs/SOURCES.md` for the per-country status, including which portals have
had their terms of use reviewed.

## Install

Not published yet.

## Licence

MIT. Built by [SOTECHDI](https://sotechdi.bf), Ouagadougou, Burkina Faso.

---

## Français

Serveur MCP donnant accès en lecture aux cadastres miniers publics d'Afrique de
l'Ouest : titulaires de permis, substances, statuts, échéances. Trois outils en
lecture seule. Sources officielles uniquement, citées et datées dans chaque
réponse. Ce serveur ne fait pas foi : le registre officiel de chaque pays reste
la seule référence opposable. Documentation complète en anglais ci-dessus.
