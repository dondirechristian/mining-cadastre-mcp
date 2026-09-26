# mining-cadastre-mcp

**MCP server for the Burkina Faso mining cadastre.**
Three read-only tools giving an AI agent access to the official list of valid
mining titles — holder, status, grant and expiry dates, provinces and communes.

> **v0.1, in development.** Covers **Burkina Faso only**, from the quarterly
> list published by the Direction générale du cadastre minier. 383 titles from
> the edition of 31 March 2026.

<!-- TODO: insérer ici une fois enregistré :  ![Demonstration](docs/demo.gif)
     Le script à filmer est scripts/demo.py — tous ses appels sont réels.
     Ancienne note : une transcription d'appels réels tient lieu
     de démonstration ci-dessous en attendant ; elle a l'avantage d'être
     vérifiable en relançant scripts/run_evals.py. -->

## Why this exists

Mining title data in Burkina Faso is public, but it is published as documents,
not as data: a quarterly PDF, scanned from paper, with nine tables inside it.
Answering *"which titles does this company hold, and when do they expire?"*
means finding the right ministry page, downloading the right file, and reading
a scanned table by eye.

No MCP server exposes mining cadastre data — in any region of the world. This
one starts with Burkina Faso.

## What it can and cannot answer

**It can** tell you who holds a title, its status, its grant and expiry dates,
the provinces and communes it covers, and which category of title it is.

**It cannot** tell you the commodity. The published lists do not carry it. You
can separate *mines* from *quarries*, but not gold from manganese. Asking the
server for gold permits returns zero results and says why — it will not guess
from a company name.

**It is not authoritative.** Every response carries the edition date, the
publication date, the date the document was read, and the SHA-256 of the source
PDF. The data reflects the state at the edition date, not today. The official
registry remains the only opposable record. Do not use this for title
verification or due diligence without confirming against the source.

**The text comes from OCR.** The source is a scan. Values that look wrong are
reported as they are, flagged in `anomalies_de_lecture`, and never silently
corrected.

## Tools

| Tool | What it does |
|---|---|
| `cadastre_list_jurisdictions` | Countries covered, source, edition served, categories and counts, explicit limits |
| `cadastre_search_licences` | Search by `societe`, `statut`, `code`, `categorie` — all optional and combinable |
| `cadastre_get_licence` | Full detail of one title by its `code` |

All three are read-only, idempotent, and never reach the network at call time.
This server writes nothing, anywhere.

## Demonstration

Real output, captured over a stdio session. Reproduce it with
`python scripts/run_evals.py`.

**Detail of one title.** Note that every response carries its provenance.

```jsonc
// cadastre_get_licence({"code": "4417"})
{
  "trouve": true,
  "titre": {
    "code": "4417",
    "nom": "BOUBOULOU 2",
    "detenteur": "SOPAMIB",
    "statut": "valide",
    "statut_normalise": "valide",
    "date_octroi": "05/12/2025",
    "date_expiration": "04/12/2028",
    "provinces": "PASSORE",
    "communes": "YAKO",
    "categorie": "LISTE DES PERMIS DE RECHERCHE VALIDES A LA DATE DU 31/03/2026",
    "page_du_document": 1,
    "strategie_extraction": "traits",
    "anomalies_de_lecture": []
  },
  "source": {
    "juridiction": "BF",
    "autorite": "Direction generale du cadastre minier (DGCM), ...",
    "edition": "2026-03-31",
    "publiee_le": "2026-04-11",
    "lue_le": "2026-09-24",
    "document_sha256": "6a18a11bd393a2b4e5e67aeb34db0645dfbbc52270b174c6f09c033b6f1de916",
    "avertissement": "Instantané daté, extrait d'un PDF scanné puis océrisé...
                      Elle ne fait pas foi : le registre officiel est la seule
                      référence opposable."
  }
}
```

**Asking for gold.** The commodity is not published, so the server says so
rather than returning something plausible.

```jsonc
// cadastre_search_licences({"categorie": "or"})
{
  "total_trouves": 0,
  "aucun_resultat": "Aucun titre ne correspond. ... Rappel : la substance n'est
                     pas publiée dans ces listes ...",
  "categories_disponibles": [ /* the nine real category labels */ ]
}
```

**A code damaged by OCR.** The server surfaces the lead and refuses to draw the
conclusion for you.

```jsonc
// cadastre_get_licence({"code": "4360"})
{
  "trouve": false,
  "message": "Aucun titre ne porte exactement le code « 4360 » dans l'édition
              2026-03-31 (383 titres). ...",
  "codes_contenant_la_valeur": [
    { "code": "4360 .", "nom": "IMASGHO", "page_du_document": 36 }
  ],
  "avertissement_rapprochement": "... Le serveur ne décide PAS qu'il s'agit du
                                  titre cherché : à vérifier sur le document,
                                  page indiquée."
}
```

Responses are French-language JSON, matching the vocabulary of the source
documents. Field values are never translated — they are what the ministry
printed.

## Install

Not published to PyPI yet. From a clone:

```bash
pip install -e .
```

Register it with an MCP client over stdio:

```json
{
  "mcpServers": {
    "mining-cadastre": {
      "command": "python",
      "args": ["-m", "mining_cadastre_mcp"]
    }
  }
}
```

`mining-cadastre-mcp` also works as a console command, from any directory.

The server reads a dated snapshot committed in `data/`, so it starts instantly
and works offline. Point it elsewhere with `MINING_CADASTRE_DATA=/path/to/data`
— which is what you need for a non-editable install, since the snapshot lives
in the repository and is not packaged into the wheel. If no snapshot is found,
the server says where it looked and how to produce one.

### Refreshing the data

New editions appear quarterly (31 March, 30 June, 31 October, 31 December).
File names are not consistent between editions, so the URL is discovered rather
than constructed:

```bash
python scripts/fetch_titres.py --list          # list published editions
python scripts/fetch_titres.py                 # download the most recent
python scripts/extract_titres.py <pdf> --out data/YYYY-MM-DD
python scripts/run_evals.py                    # check nothing broke
```

**Optional system prerequisite: Tesseract with the `fra` language.** It is only
needed for editions published without a text layer — two of the five editions
seen so far, including the most recent. It is not a Python package; on Windows
the binary is not on `PATH` by default:

```bash
export TESSERACT_CMD=/path/to/tesseract        # set TESSERACT_CMD=... on Windows
tesseract --list-langs                         # must list "fra"
```

Use `--sans-ocr` to skip it: pages without a text layer are then rejected, never
guessed. Be aware that OCR extraction currently performs poorly — see
`docs/EDITIONS.md`.

## How the data is produced

The source is a scanned PDF. Extraction runs offline and commits a dated
snapshot; the server only reads it. Three strategies are tried per page, and
every record records which one produced it:

| Strategy | When | Quality on real editions |
|---|---|---|
| `traits` | text layer + vector rules | 383 rows, 1.6 % flagged |
| `abscisses` | text layer, no rules | 391 rows, 3.3 % flagged |
| `ocr` | no text layer at all | 116 rows, 98.3 % flagged — not usable yet |

Per-edition results, including three distinct failure modes, are in
`docs/EDITIONS.md`. Source provenance and terms of use are in
`docs/SOURCES.md`.

## Testing

```bash
python scripts/run_evals.py            # 10 questions, 41 assertions, real stdio session
python scripts/run_evals.py --verbeux  # show every assertion
```

The evaluations run against a real server process. Five of the ten questions are
traps: they fail if the server answers when it should decline — asking for gold,
asking for a non-existent code, asking whether a title is valid *today*.

## Licence

MIT — see `LICENSE`. **The licence covers the software only.** The title lists
are administrative acts published by the ministry; no explicit redistribution
grant exists for them. See `docs/SOURCES.md`.

Built by [SOTECHDI](https://sotechdi.bf), Ouagadougou, Burkina Faso.

---

## Français

Serveur MCP donnant accès en lecture au cadastre minier du **Burkina Faso**, à
partir des listes trimestrielles de titres miniers valides publiées par la
Direction générale du cadastre minier. Trois outils en lecture seule : pays
couverts, recherche, détail d'un titre.

La substance exploitée n'étant pas publiée dans ces listes, le serveur ne permet
pas de distinguer l'or du manganèse — seulement les mines des carrières. Il le
dit au lieu de deviner.

Chaque réponse porte sa source, la date d'édition, la date de publication, la
date de lecture et l'empreinte du document. Les listes sont extraites de PDF
scannés puis océrisés : les valeurs douteuses sont signalées, jamais corrigées.
Ce serveur ne fait pas foi — le registre officiel reste la seule référence
opposable. Documentation complète en anglais ci-dessus.
