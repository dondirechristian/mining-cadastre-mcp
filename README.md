# mining-cadastre-mcp

**MCP server for public mining cadastres.**
Give your AI agent read access to official mining licence registries — licence
holders, status, grant and expiry dates, locations.

> Status: v0.1 in development. Not yet usable.
> v0.1 covers **Burkina Faso** only.

<!-- TODO: GIF de démonstration avant la première publication -->

## Why this exists

Mining licence data in West Africa is public, but it is published as documents,
not as data. Answering a question as simple as *"which company holds this
permit, and when does it expire?"* means finding the right ministry page,
downloading the right quarterly PDF, and reading a scanned table.

No MCP server exposes this data — in any region of the world. This one starts
with Burkina Faso.

## Coverage

**Burkina Faso.** The Direction générale du cadastre minier (DGCM), part of the
Ministry of Energy, Mines and Quarries, publishes a quarterly list of valid
mining titles at [ecadastreminier.bf](https://www.ecadastreminier.bf/). One PDF
carries nine lists — artisanal authorisations, prospecting and exploration
authorisations, industrial and semi-mechanised exploitation permits, and
exploration permits.

An earlier plan to cover many countries at once through the Landfolio platform
was dropped: its public ArcGIS services expose only context layers, and the
licence data itself sits behind a portal proxy. This server only reads what any
citizen can read. See `docs/SOURCES.md` for the full record of that decision.

Other jurisdictions come after v0.1, each from whatever its ministry actually
publishes. Mali is next in line.

## Tools

| Tool | Description |
|---|---|
| `cadastre_list_jurisdictions` | Countries covered, data source, coverage status |
| `cadastre_search_licences` | Search by company, commodity, status or licence code |
| `cadastre_get_licence` | Full detail of a single licence |

All three are read-only. This server never writes anything.

## Data and accuracy

This server reads **official public registries only**. Every response carries
its source, the publication date of the list it came from, and the date that
list was read.

Two limits matter, and the server states both in its responses:

- **The source lists are quarterly snapshots.** A response reflects the state at
  the list's cut-off date, not today.
- **The Burkina Faso lists are scanned PDFs processed with OCR.** The text is the
  product of character recognition and carries reading errors. The server
  reports what it reads and never silently corrects it.

It is a convenience layer, not a legal reference. The official registry of each
country remains the only authoritative record. Do not rely on this server for
title verification, due diligence, or any decision with legal or financial
consequence without confirming against the source.

The server reports what the registries publish. It does not interpret, score,
rank or cross-reference.

## Install

Not published yet.

## Licence

MIT. Built by [SOTECHDI](https://sotechdi.bf), Ouagadougou, Burkina Faso.

---

## Français

Serveur MCP donnant accès en lecture aux cadastres miniers publics. La v0.1
couvre le **Burkina Faso**, à partir des listes trimestrielles de titres miniers
valides publiées par la Direction générale du cadastre minier. Trois outils en
lecture seule. Sources officielles uniquement, citées et datées dans chaque
réponse — date de publication de la liste et date de lecture. Les listes sont
des PDF scannés passés à l'OCR : le serveur restitue ce qu'il lit, sans le
corriger. Ce serveur ne fait pas foi : le registre officiel reste la seule
référence opposable. Documentation complète en anglais ci-dessus.
