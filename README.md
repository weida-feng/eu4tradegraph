# EU4 Trade Graph

[![tests](https://github.com/weida-feng/eu4tradegraph/actions/workflows/tests.yml/badge.svg)](https://github.com/weida-feng/eu4tradegraph/actions/workflows/tests.yml)

A Python / Streamlit tool that turns Europa Universalis IV save-game trade data into a directed network graph and downloadable tables.

[中文说明](README.zh-CN.md) · [Design notes](docs/architecture.md) · [Example SVG](docs/images/trade-network.svg)

EU4 stores trade nodes and transfers as nested text. This project extracts those records, validates node references, and makes their relationships visible: node size shows current trade value, color shows local production, and edge width shows transferred value.

![Trade network from the original EU4 1.34.4 reference save](docs/images/trade-network.png)

## Compatibility

| Input | Support |
| --- | --- |
| Vanilla EU4, uncompressed `EU4txt` save | Can be parsed when its trade fields and node IDs are recognized |
| Reference data actually checked | **1.34.4.0**, in-game date 1444.12.1 |
| Other EU4 versions, including other 1.34 patches and 1.35+ | Can be attempted; compatibility and results are not guaranteed |
| Saves declaring enabled mods, or containing unknown trade nodes | Rejected |
| Compressed, binary or Ironman saves | Not supported |

Only **EU4 1.34.4.0** has been verified against the reference save. There is no version allowlist: saves from other versions can be attempted, and the app displays a warning before letting users generate graphs and export data. This does not establish compatibility with those versions; parsing may fail or the results may be incorrect if the save format or trade data has changed. Mod detection uses save metadata and the original node catalog; it cannot prove that a save without mod metadata was never modified. DLC entries are separate from mods and are allowed.

The included example is a **trade-only extract**, not a playable game save. It preserves all 80 nodes, 153 route records, their order and numeric trade fields from the original repository save. Its size is 13,808 bytes, compared with the original 51,124,155-byte file. The original remains in Git history at `91633ee`; no history rewrite is required.

## Run locally

Use Python **3.11 or newer**. The Python dependencies are pinned in `requirements.txt`; Graphviz also needs a separate system installation.

1. Install Graphviz and a Chinese font:

   - **Ubuntu / Debian:** `sudo apt-get install graphviz fonts-noto-cjk`
   - **macOS:** `brew install graphviz` (the app defaults to PingFang SC)
   - **Windows:** install [Graphviz](https://graphviz.org/download/), add its `bin` directory to `PATH`, and use Microsoft YaHei or another installed CJK font.

   Check the system installation with `dot -V`.

2. Clone and install:

   ```bash
   git clone https://github.com/weida-feng/eu4tradegraph.git
   cd eu4tradegraph
   python -m venv .venv
   source .venv/bin/activate
   # Windows PowerShell: .venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```

3. Start the app:

   ```bash
   streamlit run app.py
   ```

4. Use **内置演示** (built-in demo) and click **生成贸易网络图** (generate graph), or select **上传存档** (upload save). To produce a compatible save, disable compression in EU4's save dialog. Uploads are limited to 200 MB.

For Streamlit Community Cloud, select `app.py` as the entry point and Python 3.11+. `packages.txt` supplies the Linux Graphviz executable and CJK fonts. This repository does not claim a currently deployed public demo.

## What the graph and tables show

| Visual / column | Save field / interpretation |
| --- | --- |
| Node size and number | `current`, the current node trade value recorded in the save |
| Node color | `local_value`, locally generated trade value, interpolated in HSV |
| Arrow width | `incoming.value`, transferred trade value |
| Arrow direction | `incoming.from` → the node containing that record |
| Dashed arrow | A route whose recorded value is zero |
| Box / ellipse | Inland / coastal node classification from the original mapping |
| `outgoing` table column | Outgoing trade value recorded in the save |

These are node/route values, **not a country's trade income**. The graph describes relationships, not geographical distance. Each numeric visual uses min–max scaling; a constant data range uses the midpoint to avoid division by zero.

Features include Chinese or English node labels, adjustable sizing and color ranges, PNG/SVG downloads, and UTF-8 CSV exports of node and route data. CSV exports keep canonical node IDs so the tables can be joined in pandas or another analysis tool.

## Implementation

```text
app.py                         Streamlit input, controls and downloads
eu4tradegraph/parser.py         Format checks, version metadata and trade extraction
eu4tradegraph/render.py         Numeric scaling, DOT generation and in-memory rendering
eu4tradegraph/export.py         Node/route tables and CSV serialization
eu4tradegraph/data/             UTF-8 node names and inland/coastal flags
examples/                      Small reference trade snapshot
tests/                         Parser, rendering, export and app checks
```

The parser reads braces, quoted strings and comments instead of relying on fixed indentation. It skips unrelated nested fields and converts numeric values with `float`, without evaluating save content. Route references are one-based in the save and resolved after all nodes have been read. Rendering uses an in-memory Graphviz pipe, so concurrent sessions do not share a `graph.png` output file.

## Validation

```bash
python -m unittest discover -s tests -v
```

The suite checks reference counts and values, acceptance of other version metadata, version warnings that still allow rendering, mods, bad input, omitted zero fields, nested-field isolation, invalid route indices, all-zero rendering, PNG/SVG output, CSV exports and the Streamlit demo flow. Other-version tests use synthetic metadata, not verified saves from those game versions. Graphviz integration tests require `dot`; the GitHub Actions workflow installs it and runs the suite on Python 3.11 and 3.13.

The refactor was also checked against the original full 1.34.4.0 save: the extracted demo and the full save produce equal parsed snapshots. This is one reference campaign, not a cross-version compatibility study.

## Project background

The original tool was developed in 2023 to make EU4 trade flows easier to inspect. The current repository separates the data pipeline from the interface and adds explicit compatibility checks, exports, documentation and automated validation. It is a small data visualization application rather than a general EU4 save parser or a trade-strategy optimizer.

EU4 node identifiers and reference data originate from the game's save format; the Chinese labels and node classification mapping are preserved from the original project.
