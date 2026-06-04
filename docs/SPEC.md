# PDF Provenance Auditor: build spec for the next EquitableDocs tool

**Working title:** PDF Provenance Auditor (codename `tagorigin`)
**Date:** 2026-06-04
**Author:** qc-claude
**Purpose:** Hand this document to an external coding agent (Kimi K2 via opencode, Aider, Cursor, or similar) to build a single-script Python tool plus optional web UI. The spec is self-contained; the agent does not need any other EquitableDocs context.

---

## 0. Why this tool exists (one paragraph for the agent)

In accessibility work there is a widespread, costly misconception: people see a tagged PDF (one that has a `/StructTreeRoot` and structure elements like `/Document`, `/H1`, `/P`, `/Figure`) and assume it has been "remediated for accessibility". That is wrong. Authoring tools like Adobe InDesign, Microsoft Word, and Apple Pages emit structure tags automatically on export, with no human accessibility review. Those auto-emitted tags routinely fail PDF/UA and WCAG 2.1 AA because of generic alt text, lists tagged as paragraphs, reading order following text-frame placement rather than visual layout, missing scope attributes on table headers, and so on. An actively remediated PDF, by contrast, has been opened by a dedicated accessibility tool (Adobe Acrobat Pro Touchup, PDFix SDK, CommonLook, axesPDF, NetCentric) and edited with intent. The two are visually similar in the Tags panel but very different in downstream behaviour.

This tool tells you which one you have. It reads a PDF, runs a set of signals, and outputs one of five provenance classifications with a confidence score and per-signal evidence. The classification drives a recommendation: treat as raw publisher input (do full remediation), treat as a reteach case (correct against a vendor defect log), or accept as already-remediated.

Target users: accessibility-team intake reviewers, university procurement officers vetting vendor output, publisher QA teams self-assessing their InDesign exports, and the EquitableDocs portal upload flow.

---

## 1. Classification taxonomy

Output one of:

| Label | Meaning |
|---|---|
| `UNTAGGED` | No `/StructTreeRoot`, or `/StructTreeRoot` is empty. Likely a scanned PDF or pre-tagging draft. |
| `AUTO_TAGGED` | Tags exist but were produced by the authoring tool's automatic export. No subsequent remediation pass. The Sadlier CH10 PDFs we audited on 2026-06-03 are the reference example. |
| `LIGHTLY_REMEDIATED` | Tags show a single remediation touch (Acrobat Pro autotag re-run, basic touchup) but with limited semantic depth. Some lists, some alt text, but generic and incomplete. |
| `REMEDIATED` | Tags reflect a deliberate remediation pass. Proper `/L`/`/LI`/`/Lbl`/`/LBody` lists, sentence-length alt text on figures, scope on table headers, artifact markings on decorative content. PDF/UA conformance metadata may be present. |
| `WELL_REMEDIATED` | All of the above plus advanced markers: `/Lang` attributes at span level, PDF/UA conformance declared, complete `/StructParents` mapping, linearised (Fast Web View enabled), and (optional) Layer 5 visual reading-order verification passes. |

A `confidence` field (0.0 to 1.0) accompanies the label. A `recommendation` field accompanies the label (see section 5).

---

## 2. Detection signals (the heuristic engine)

Each signal has a fixed weight. The weighted sum determines the classification. Signals are grouped by source.

### 2.1 Metadata signals (from `/Info` dictionary and XMP)

| ID | Signal | How to detect | Weight |
|---|---|---|---|
| M1 | XMP history single event | `xmpMM:History` contains exactly one `<rdf:li>` with `<stEvt:action>converted</stEvt:action>` | -1.5 |
| M2 | XMP history multiple events | Two or more `<rdf:li>` entries in `xmpMM:History` | +1.0 |
| M3 | XMP history names known remediator agent | Any `<stEvt:softwareAgent>` contains: `PDFix`, `Acrobat Pro` (post-conversion save), `CommonLook`, `axesPDF`, `NetCentric`, `Foxit PhantomPDF`, `Kofax Power PDF`, `Adobe Acrobat` (a save event, not the original convert) | +2.0 |
| M4 | `/Producer` is pure authoring tool | `Adobe PDF Library X.X` (paired with InDesign), `Microsoft® Word X` (paired with Word `/Creator`), `Pages X.X`, `LibreOffice X.X`, `Mac OS X X X Quartz PDFContext` | -1.5 |
| M5 | `/Producer` is remediation tool | `PDFix SDK`, `Acrobat Pro DC`, `Acrobat Distiller` (post-edit), `CommonLook`, `axesPDF`, `NetCentric Technology` | +1.5 |
| M6 | PDF/UA conformance declared | XMP contains `<pdfuaid:part>1</pdfuaid:part>` | +2.0 |
| M7 | Linearised (Fast Web View enabled) | PDF has a `/Linearized` dictionary in object 1 | +0.5 |
| M8 | `/Lang` set at document level | `pdf.Root.get('/Lang')` is non-empty | +0.3 |
| M9 | `/MarkInfo /Marked` is true | `pdf.Root.get('/MarkInfo').get('/Marked')` is True | +0.5 (necessary but not sufficient: InDesign sets this too) |
| M10 | Title is non-default | `/Title` exists, is not empty, and does not match the filename stem | +0.3 |

### 2.2 Structure-tree signals (walk `/StructTreeRoot`)

| ID | Signal | How to detect | Weight |
|---|---|---|---|
| S1 | No `/StructTreeRoot` | Absent or empty | -3.0 (forces `UNTAGGED`) |
| S2 | Heading hierarchy present | `/H1` count >= 1 and `/H2` count >= 1, no skipped levels | +0.5 |
| S3 | Lists use semantic list structure | Count of `/L` + `/LI` + `/Lbl` + `/LBody` divided by count of `/P` containing "1." / "2." / "3." patterns at the start. Ratio > 0.7 → +1.0 |
| S4 | Lists are tagged as paragraphs (anti-signal) | Many `/P` elements containing leading "1.", "2.", "3." (digit-period-space) text spans. Ratio > 0.5 → -1.5 |
| S5 | `/Figure` elements have meaningful alt | Per `/Figure`, read `/Alt` attribute. If average alt-text length across figures is > 30 characters AND no figure has alt in (`image`, `figure`, `logo`, `icon`, `graphic`, file extension only, the file stem) → +1.0 |
| S6 | `/Figure` elements have generic or empty alt | Average alt < 15 chars, OR > 30% of figures have alt in (`image`, `logo`, `icon`, `figure`, `graphic`) → -1.5 |
| S7 | Tables have `/Scope` on `/TH` | Every `/TH` element has `/Scope` ∈ {`Row`, `Column`, `Both`} → +1.0 |
| S8 | Tables missing `/Scope` on `/TH` | Any `/TH` lacks `/Scope` → -0.5 |
| S9 | Artifact markings present | `/Artifact` BMC/EMC pairs in content streams, or `/Type /Pagination` / `/Layout` artifact subtypes → +0.5 |
| S10 | ActualText anti-patterns | `/ActualText` values include `blank`, `space`, or empty string on non-empty spans → -0.5 per occurrence, capped at -1.5 |
| S11 | `/Lang` attributes at span level | At least one `/Span` element with `/Lang` attribute → +0.5 |
| S12 | `/StructParents` mapping completeness | Every page with content has a `/StructParents` entry, and the `/ParentTree` is well-formed → +0.5 |
| S13 | Reading order tag-tree-first | The `/StructTreeRoot` walk order matches the page content's visual top-to-bottom, left-to-right order on at least 3 sampled pages (compute via tag-tree pre-order traversal vs `/MCID` coordinate centroids) → +1.0 |
| S14 | Reading order text-frame-first (anti-signal) | Walk order matches text-frame insertion order from InDesign, which often diverges from visual order. Detected by comparing tag-tree order to visual order; if mismatched on 2+ sampled pages → -1.0 |

### 2.3 Content-stream signals (optional, deeper inspection)

| ID | Signal | How to detect | Weight |
|---|---|---|---|
| C1 | Reversed-glyph footers | Content stream contains text strings like `.scitamehtaM` or `.reildaS` (Sadlier-specific anti-pattern from InDesign's optical-kerning leaking into ActualText) → -0.5 |
| C2 | Doubled-glyph artifacts | Content stream contains repeated adjacent identical glyph runs (`aa`, `bb` patterns at character boundaries) → -0.3 |
| C3 | XObject reuse with proper /Pg inheritance | Same XObject referenced from multiple struct elements, each with proper `/Pg` set → +0.5 |
| C4 | Stream uses `BDC` / `EMC` for figures | Every Figure element references content marked with `/Figure BDC ... EMC`, with `/MCID` and `/Alt` in the property dict → +0.5 |

### 2.4 Layer 5 (optional, vision-assisted)

If a vision model is available (Claude, GPT-4V, Kimi vision):

| ID | Signal | How to detect | Weight |
|---|---|---|---|
| V1 | Visual reading order matches tag-tree order | Render page to image, ask vision model "in what order should a screen reader read this?", compare to tag-tree pre-order traversal → +1.5 if matches, -1.0 if mismatches |
| V2 | Figure alt text accuracy | For each figure, render the page, crop the figure region, ask vision model to describe, compare to `/Alt`. Match → +0.5 per figure, capped at +2.0 |

Vision signals are gated behind a `--vision` CLI flag and a model-provider env var. Without them, the tool still produces a classification from M and S signals alone.

### 2.5 Classification thresholds

Sum the weights of all fired signals. Apply rules in order:

1. If S1 fires → `UNTAGGED`, confidence 1.0
2. Otherwise compute `score = sum of fired-signal weights`
3. Map score to label:
   - `score < -2`: `AUTO_TAGGED`, confidence = min(1.0, abs(score) / 5)
   - `-2 <= score < 0`: `AUTO_TAGGED`, confidence = 0.5 + abs(score) / 4
   - `0 <= score < 2`: `LIGHTLY_REMEDIATED`, confidence = 0.5 + score / 4
   - `2 <= score < 5`: `REMEDIATED`, confidence = 0.6 + score / 10
   - `score >= 5`: `WELL_REMEDIATED`, confidence = min(1.0, 0.7 + score / 15)
4. Hard override: if M6 (PDF/UA declared) AND M3 (remediator agent in XMP) both fire → at minimum `REMEDIATED`

These thresholds are calibrated against the test corpus in section 7 and re-tuned during the build.

---

## 3. Architecture

Single Python package, three layers:

```
tagorigin/
├── __init__.py
├── cli.py                  # argparse entry point, batch + single-file modes
├── inspect.py              # pikepdf-based metadata + structure extraction
├── signals/
│   ├── __init__.py
│   ├── metadata.py         # M1-M10
│   ├── structure.py        # S1-S14
│   ├── content.py          # C1-C4
│   └── vision.py           # V1-V2 (optional, behind --vision flag)
├── classify.py             # weighted-sum scoring + threshold mapping
├── report.py               # render JSON / markdown / HTML reports
├── corpus/                 # bundled test PDFs + expected classifications
│   ├── auto_tagged/        # 5 known InDesign exports
│   ├── word_exports/       # 5 known Word exports
│   ├── remediated/         # 5 known remediated PDFs
│   ├── well_remediated/    # 5 known PDF/UA-certified PDFs
│   ├── untagged/           # 5 scanned PDFs
│   └── expected.json       # ground-truth labels per file
└── tests/
    ├── test_signals.py
    ├── test_classify.py
    └── test_corpus.py      # run against corpus, assert correct labels
```

External dependencies (pin all in `pyproject.toml`):

- `pikepdf` for primary PDF parsing
- `Pillow` for image rendering (used by content + vision signals)
- `pypdfium2` as a render-engine option (lighter than PyMuPDF, no licence issues)
- `click` or `typer` for the CLI (typer is friendlier)
- `pydantic` for the result schema
- `rich` for terminal output (optional)
- `anthropic` or `openai` SDK for vision (only loaded if `--vision` is used)

Python version: 3.10+ (uses `match` statements and modern typing).

---

## 4. CLI design

```
# Single file, default text output to stdout
tagorigin check sample.pdf

# Single file, JSON output to stdout
tagorigin check sample.pdf --format json

# Single file, write a markdown report
tagorigin check sample.pdf --report sample_report.md

# Batch mode: walk a folder, write CSV summary plus per-file JSON
tagorigin check folder/ --recursive --csv summary.csv --json-dir per_file_json/

# Enable vision-assisted signals
tagorigin check sample.pdf --vision --model claude-opus-4-7

# Show evidence with weights (verbose)
tagorigin check sample.pdf --verbose

# List the supported signals and their weights (for transparency)
tagorigin signals --list

# Run against the bundled corpus and print confusion matrix
tagorigin test --corpus
```

Exit codes: 0 if classification produced, 1 if PDF is unreadable, 2 if a required signal failed to compute, 64+ for CLI usage errors.

---

## 5. Output schema (Pydantic-validated)

```python
class SignalResult(BaseModel):
    id: str               # e.g. "M1_xmp_history_single_event"
    description: str      # human-readable
    weight: float
    fired: bool
    evidence: str         # short context, e.g. "1 event, agent: Adobe InDesign 19.4"

class ProvenanceResult(BaseModel):
    file: str
    file_size_bytes: int
    file_md5: str
    classification: Literal["UNTAGGED", "AUTO_TAGGED", "LIGHTLY_REMEDIATED",
                            "REMEDIATED", "WELL_REMEDIATED"]
    confidence: float     # 0.0 to 1.0
    score: float          # raw weighted sum
    signals: list[SignalResult]
    summary: str          # 1-2 sentence human summary
    recommendation: str   # what to do with this file
    metadata: dict        # producer, creator, xmp history count, etc.
```

### Recommendation lines (deterministic, based on classification):

- `UNTAGGED`: "Untagged PDF. Run OCR and full structural tagging before any accessibility work. Treat as raw input."
- `AUTO_TAGGED`: "Publisher-original PDF with authoring-tool auto-tags. No accessibility remediation pass detected. Treat as from-scratch remediation input. Expect typical authoring-tool defects: reading order from text frames, generic alt text, lists tagged as paragraphs, table headers without scope."
- `LIGHTLY_REMEDIATED`: "Single remediation touch detected, but semantic depth is limited. Run a full PDF/UA + WCAG 2.1 AA QC pass. Likely needs additional remediation work."
- `REMEDIATED`: "Deliberate remediation pass detected. Recommend a verification QC pass (PAC 2024, NVDA end-to-end) before sign-off. Treat as reteach input if a vendor defect log accompanies the file."
- `WELL_REMEDIATED`: "Strong remediation evidence including PDF/UA conformance. Minimal QC needed beyond automated checks. Spot-check with screen reader before delivery."

---

## 6. Build phases

### Phase 1: MVP (target: one focused day, 6 to 8 hours)

- Project scaffold + `pyproject.toml`
- `inspect.py`: open PDF with pikepdf, extract `/Info`, `/Root`, XMP, `/StructTreeRoot` walk to tag-name tally
- Signals M1, M2, M3, M4, M5, M6, M7, M8, M9, M10 (all metadata)
- Signals S1, S2, S5, S6, S7, S10 (the highest-signal structure signals)
- `classify.py` with the threshold table
- `cli.py` with `check` subcommand, text + JSON output
- README with the "tagged vs remediated" framing + usage examples
- Hand-test on 3 PDFs: one Sadlier publisher-original, one PDFix-remediated, one untagged scan. Adjust weights to land each in the right bucket.

### Phase 2: Full signal set (target: half a day)

- Remaining signals S3, S4, S8, S9, S11, S12, S13, S14
- Content-stream signals C1, C2, C3, C4
- Markdown report renderer (`report.py`)
- Batch mode (folder walk, CSV summary, per-file JSON)
- Bundled corpus + ground-truth labels + `tagorigin test --corpus` evaluator
- Re-tune weights against the corpus until classification accuracy is >= 90%

### Phase 3: Vision signals (target: one day)

- V1 (reading-order check) and V2 (alt-text accuracy)
- Provider-agnostic vision client (Anthropic + OpenAI + Kimi)
- `--vision` flag, model env var convention
- Cost reporting (per-file token cost on vision runs)

### Phase 4: Web UI and EquitableDocs portal integration (target: one or two days)

- FastAPI wrapper: POST `/audit` with multipart PDF, returns the ProvenanceResult JSON + HTML report
- Static HTML upload form (no React)
- Integration with the existing EquitableDocs portal's upload flow
- Add to portal sidebar as a new tool. Tool number to be assigned by Deepa.

### Phase 5 (later): Continuous corpus + telemetry

- Allow real-world PDFs uploaded to the portal to opt in to corpus growth (with explicit consent)
- Weekly weight re-calibration via the growing corpus
- Public methodology page on the EquitableDocs site explaining what each signal means and why it weights as it does

---

## 7. Test corpus (build during Phase 2)

Collect at minimum 25 PDFs spanning the five classes. Suggested sources:

### `auto_tagged/` (Adobe InDesign auto-export)

- The Sadlier G1 B3 CH10 Without_Anno PDFs at
  `C:\Users\deepa\Projects\pdfix-remediation\clients\slizvon-reteach\inputs\CH10\CH10\Without_Anno\Ready_for_R1\`
  (pick five: closereading, connection, intervention_suggest, post_test_table, reteach_less10-1).
- Any publicly-available textbook PDF exported by the publisher direct from InDesign without remediation. The CH10 set is a known-good calibration baseline.

### `word_exports/` (Microsoft Word auto-export)

- Open a few Word documents and Save As PDF with default settings. Include at least one with a properly-styled Heading 1, one with a numbered list, one with an inline image with no alt.

### `remediated/` (deliberate remediation pass, Acrobat or PDFix)

- The EquitableDocs CH11 shipped remediation output (post-PDFix, post-vision-alt) lives somewhere under `C:\Users\deepa\Projects\pdfix-remediation\clients\slizvon-reteach\` in the Round 1 ship.
- PDFix sample PDFs from `https://pdfix.net/products/pdfix-sdk/samples/` (they publish reference accessibility-tagged outputs).

### `well_remediated/` (PDF/UA certified)

- PDF/UA reference suite from PDFix or the PDF Association: <https://www.pdfa.org/resource/the-matterhorn-protocol/> (Matterhorn protocol test files).
- W3C accessibility example PDFs.

### `untagged/` (scans, no struct tree)

- Any scanned PDF without OCR + tagging. Sample from the EquitableDocs portal's earlier intakes if available, or synthesise one by removing /StructTreeRoot from a tagged file.

`expected.json` lists each file's path and the correct classification + 1-sentence reason. The test runner asserts the tool's output matches.

---

## 8. Risks and known weaknesses

- **Some remediators preserve the original `/Producer`** to avoid breaking publisher fingerprints. M3 (XMP history) catches them, but if the remediator strips XMP history too, the tool may classify as `AUTO_TAGGED`. Document this as a known limitation; recommend looking at structure depth as backup.
- **Some authoring tools produce above-average auto-tagged output** (e.g., InDesign with a custom accessibility export preset). These may score into `LIGHTLY_REMEDIATED` even though no human touched them. Acceptable trade-off; the recommendation line for `LIGHTLY_REMEDIATED` still says "run a full QC pass", which is the right action.
- **PDF/UA conformance can be falsely declared.** Some publishers add the conformance metadata without actually meeting the standard. The tool flags this with a confidence reduction if `M6` fires but `S6` (generic alt) or `S8` (missing scope) also fires.
- **Vision signals add cost and latency.** Keep them behind the `--vision` flag and warn the operator about per-page token cost.
- **Edge case: re-distilled PDFs.** When a PDF goes through Acrobat Distiller after remediation (for some workflows), the producer string changes to Distiller. M5 covers this but with lower weight than direct PDFix/Acrobat-Pro detection.

---

## 9. Integration with EquitableDocs portal

The portal already has Tool 6 (defect detection / accessibility audit report) and Tool 7 (page accessibility coach). This becomes Tool 8 (proposed; number to be confirmed by Deepa post-build).

Portal entry: `/tools/provenance-audit` with the upload form. Backend route: POST `/api/audit/provenance` taking a multipart file, returning the `ProvenanceResult` JSON and a one-page HTML report. Same auth and same retention rules as Tool 6.

Marketing copy on the public-facing tool page (Deepa to refine): "Is this PDF really accessible, or just tagged? Upload a PDF and find out whether its accessibility tags came from a deliberate remediation pass or just from the authoring tool's automatic export. Critical for procurement teams, publisher QA, and universities vetting vendor output."

---

## 10. Instructions for the coding agent (paste this into Kimi or opencode)

> You are building the PDF Provenance Auditor (codename `tagorigin`). Read this spec end to end. Then:
>
> 1. Create the project scaffold under `tagorigin/` matching section 3.
> 2. Implement Phase 1 (MVP) signals: M1, M2, M3, M4, M5, M6, M7, M8, M9, M10 from section 2.1, and S1, S2, S5, S6, S7, S10 from section 2.2. Use `pikepdf` for all PDF access.
> 3. Implement `classify.py` with the threshold table from section 2.5.
> 4. Implement the CLI per section 4, with only the `check` subcommand and text + JSON output formats for now.
> 5. Implement the output schema from section 5 using Pydantic. Include the deterministic recommendation lines.
> 6. Add `pyproject.toml` with pinned dependencies.
> 7. Write a README that explains the "tagged vs remediated" framing (the one paragraph at the top of section 0) and includes the three example invocations from section 4 (default text, JSON, verbose).
> 8. Add three smoke tests that run `tagorigin check` on three sample PDFs the user will provide (one InDesign auto-export, one PDFix-remediated, one untagged scan) and assert the classification.
>
> Constraints, important:
>
> - No em-dashes or en-dashes anywhere in code comments, docstrings, README, or commit messages. Use commas, colons, or full stops. This is a hard rule from the project owner.
> - No AI-tell phrasing in any output: avoid the transitional and meta-commentary patterns common in machine-generated prose. Write plainly.
> - Do not name yourself or the model in any output. The tool is `tagorigin`; the maintainer is `EquitableDocs`.
> - No emojis anywhere unless explicitly requested.
> - Plain HTML in the future web UI: semantic HTML5, minimum 16px body text, rem units, visible focus indicators. No React, no Tailwind, no SPA framework.
>
> When Phase 1 is complete and tests pass, stop and ask the project owner before starting Phase 2. Do not auto-start vision (Phase 3) under any circumstances; that requires explicit token-budget approval.

---

## 11. Tool choice recommendation

For this build, ranked by fit:

1. **Aider with Kimi K2** (recommended). Aider is mature, terminal-based, multi-file diff-aware, and supports Kimi via the OpenAI-compatible Moonshot endpoint. Best fit for a tight Python tool build. Cheap and fast.
2. **opencode with Kimi K2**. opencode is newer but its TUI is pleasant and the model-routing model is similar to Claude Code. Reasonable choice if you prefer its workflow.
3. **Cursor IDE with Kimi K2**. If you want IDE-level integration (jump-to-symbol, live diff preview) over terminal. More overhead than Aider for a single-script project.
4. **Claude Code with Sonnet 4.6**. If Kimi's quality on this specific build turns out to be too uneven, fall back here. Sonnet handles the heuristic-engine work cleanly. Cost is the trade-off.

You probably do not need a Workflow or multi-agent setup for this. One agent, one model, one focused session of 6 to 8 hours for Phase 1.

For the corpus (Phase 2), Claude Code is a better choice than Kimi because corpus collection benefits from web-fetching and ground-truth labelling which Claude handles more reliably.

---

## 12. Estimated effort

- Phase 1 MVP: 6 to 8 hours
- Phase 2 full signal set plus corpus calibration: 6 to 8 hours
- Phase 3 vision signals: 6 to 8 hours
- Phase 4 portal integration: 8 to 16 hours

Total to ship a public Tool 8: roughly two to three working days of focused build time, plus calibration iterations.
