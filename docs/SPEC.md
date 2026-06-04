# PDF Provenance Auditor: build spec for the next EquitableDocs tool

**Working title:** PDF Provenance Auditor (codename `tagorigin`)
**Date:** 2026-06-04
**Author:** qc-claude
**Purpose:** Hand this document to an external coding agent (Kimi K2 via opencode, Aider, Cursor, or similar) to build a single-script Python tool plus optional web UI. The spec is self-contained; the agent does not need any other EquitableDocs context.

---

## 0. Why this tool exists (one paragraph for the agent)

In accessibility work there is a widespread, costly misconception: people see a tagged PDF (one that has a `/StructTreeRoot` and structure elements like `/Document`, `/H1`, `/P`, `/Figure`) and assume it has been "remediated for accessibility". That is wrong. Tags can come from at least two kinds of automatic process with no human accessibility review:

1. **Authoring-tool export autotag.** Adobe InDesign, Microsoft Word, Apple Pages, LibreOffice, and Google Docs export-to-PDF all emit a tag tree from the source document's styles on export. Quality varies with how well the source was styled.
2. **Tool-level autotag run on an already-exported PDF.** Adobe Acrobat Pro's "Autotag Document" menu, Acrobat's "Add Tags to Document" command, PDFix SDK in its autotag mode, Foxit's autotag, Microsoft Word's accessibility-check auto-fix. These open a PDF and infer structure from rendered content. No human is in the loop on these either.

Both kinds of autotag routinely fail PDF/UA and WCAG 2.1 AA: generic alt text, lists tagged as paragraphs, reading order following text-frame or content-stream placement rather than visual layout, missing scope on table headers, headings either missing or all collapsed to `/H1`, no artifact markings on decorative content.

An actively remediated PDF, by contrast, has been opened by a dedicated accessibility tool (Adobe Acrobat Pro's Touchup Reading Order, PDFix SDK's interactive editor, CommonLook, axesPDF, NetCentric) AND edited with human intent: meaningful alt text written, list semantics applied, table scope set, reading order corrected, artifacts marked. The edit-tool fingerprint in the PDF metadata tells you which software opened the file; it does NOT tell you whether a human reviewed the tags. To distinguish autotag-only from real remediation, the tool must look at the **structural quality of the tags themselves**, not just at the metadata fingerprint. This is the central design principle of `tagorigin`.

This tool tells you which one you have. It reads a PDF, runs signals across both metadata and structural quality, and outputs one of five provenance classifications with a confidence score and per-signal evidence. The classification drives a recommendation: treat as raw publisher input (do full remediation), treat as autotagged input (still needs remediation despite the tool fingerprint), treat as a reteach case (correct against a vendor defect log), or accept as already-remediated.

Target users: accessibility-team intake reviewers, university procurement officers vetting vendor output, publisher QA teams self-assessing their InDesign exports, and the EquitableDocs portal upload flow.

---

## 1. Classification taxonomy

Output one of:

| Label | Meaning |
|---|---|
| `UNTAGGED` | No `/StructTreeRoot`, or `/StructTreeRoot` is empty. Likely a scanned PDF or pre-tagging draft. |
| `AUTO_TAGGED` | Tags exist but were produced by an automatic process with no human review. Includes BOTH authoring-tool export autotag (InDesign, Word, Pages, Google Docs, LibreOffice) AND tool-level autotag run on an already-exported PDF (Acrobat Pro's "Autotag Document", PDFix's autotag mode, Foxit's autotag, Word's accessibility-check auto-fix). The metadata fingerprint may show any of these tools; what makes the file `AUTO_TAGGED` is that the structural quality is auto-tool quality, not human-reviewed quality. The Sadlier CH10 PDFs we audited on 2026-06-03 are the reference example for the InDesign-export-only subcase. |
| `LIGHTLY_REMEDIATED` | Tags show partial human touch: some list semantics, some alt text written, some artifacts marked, but the work is incomplete. Common when someone opened the PDF in Acrobat Pro, fixed a few obvious things, and saved without doing the full pass. |
| `REMEDIATED` | Tags reflect a deliberate full remediation pass. Proper `/L`/`/LI`/`/Lbl`/`/LBody` lists, sentence-length alt text on figures, scope on table headers, artifact markings on decorative content. PDF/UA conformance metadata may be present. |
| `WELL_REMEDIATED` | All of the above plus advanced markers: `/Lang` attributes at span level, PDF/UA conformance declared, complete `/StructParents` mapping, linearised (Fast Web View enabled), and (optional) Layer 5 visual reading-order verification passes. |

A `confidence` field (0.0 to 1.0) accompanies the label. A `recommendation` field accompanies the label (see section 5).

---

## 2. Detection signals (the heuristic engine)

Each signal has a fixed weight. The weighted sum determines the classification. Signals are grouped by source.

### 2.1 Metadata signals (from `/Info` dictionary and XMP)

| ID | Signal | How to detect | Weight |
|---|---|---|---|
| M1 | XMP history single event | `xmpMM:History` contains exactly one `<rdf:li>` with `<stEvt:action>converted</stEvt:action>` | -1.5 |
| M2 | XMP history multiple events | Two or more `<rdf:li>` entries in `xmpMM:History` | +0.5 (weak signal: a save event can be autotag OR remediation; structural signals decide) |
| M3 | XMP history names accessibility-capable tool | Any `<stEvt:softwareAgent>` contains: `PDFix`, `Acrobat Pro`, `Adobe Acrobat` (save event), `CommonLook`, `axesPDF`, `NetCentric`, `Foxit PhantomPDF`, `Kofax Power PDF`. Default weight: +1.0. **Important calibration note**: many production remediation tools (especially PDFix in non-interactive mode and Acrobat Pro on in-place save) do NOT append xmpMM:History events. Empirical verification on a PDFix-remediated CH11 file showed XMP history was identical to the InDesign source (1 event, InDesign agent), despite a confirmed remediation pass. Treat absence of M3 as weak evidence, not strong. |
| M4 | `/Producer` is pure authoring tool | `Adobe PDF Library X.X` (paired with InDesign), `Microsoft® Word X` (paired with Word `/Creator`), `Pages X.X`, `LibreOffice X.X`, `Mac OS X X X Quartz PDFContext` | -1.0. **Calibration note**: PDFix and CommonLook commonly preserve the original `/Producer` string to avoid breaking publisher fingerprints. Empirical verification on a PDFix-remediated CH11 file showed `/Producer` was identical to the InDesign source. M4 will misfire (favour AUTO_TAGGED) on these tools. |
| M5 | `/Producer` is accessibility-capable tool | `PDFix SDK`, `Acrobat Pro DC`, `Adobe Acrobat X DC`, `CommonLook`, `axesPDF`, `NetCentric Technology`. Default weight: +1.5. **Note**: Acrobat Pro Touchup on in-place save does NOT change /Producer; only Save-As-Optimized or PDF Optimizer does. M5 fires reliably for PDFix output saved to a new file but unreliably for Acrobat-remediated in-place saves. |
| M5b | `/Producer` is a known autotag-only output | `Acrobat Distiller` (post-Distiller flatten with autotag), Word's "Save as PDF with accessibility check", PDFix CLI invoked in `autotag` mode (detectable when XMP includes `pdfix:Mode=AutoTag` or similar) | -0.5 (tags exist but were generated automatically) |
| M6 | PDF/UA conformance declared | XMP contains `<pdfuaid:part>1</pdfuaid:part>` | +2.0. **Dampening rule**: if M6 fires AND (S4 OR S6 OR S8b) also fires, reduce effective M6 weight to +1.0. Empirical verification: a publisher-original Sadlier InDesign export declared `pdfuaid:part=1` despite being unremediated. PDF/UA declarations are commonly written without actually meeting the standard. |
| M7 | Linearised (Fast Web View enabled) | PDF has a `/Linearized` dictionary in object 1 | +0.3 (weak; InDesign can produce linearised output with the right preset) |
| M8 | `/Lang` set at document level | `pdf.Root.get('/Lang')` is non-empty | +0.3 |
| M9 | `/MarkInfo /Marked` is true | `pdf.Root.get('/MarkInfo').get('/Marked')` is True | +0.1 (near-universal among any tagged file; almost no discriminatory power) |
| M10 | Title is non-default | `/Title` exists, is not empty, and does not match the filename stem | +0.3 |

### 2.2 Structure-tree signals (walk `/StructTreeRoot`)

| ID | Signal | How to detect | Weight |
|---|---|---|---|
| S1 | No `/StructTreeRoot` | Absent or empty | -3.0 (forces `UNTAGGED`) |
| S2 | Heading hierarchy present | `/H1` count >= 1 and `/H2` count >= 1, no skipped levels | +0.3 (lower than originally specced: well-styled InDesign sources export heading hierarchy faithfully without remediation) |
| S3 | Lists use semantic list structure | Count of `/L` + `/LI` + `/Lbl` + `/LBody` divided by count of `/P` containing "1." / "2." / "3." patterns at the start. Ratio > 0.7 → +1.0. **Note**: Word exports lists as `/L` reliably when source uses Word list styles; expect S3 to fire on Word auto-exports without remediation. Combine with S2 and structural signals to break the tie. |
| S4 | Lists are tagged as paragraphs (anti-signal) | Many `/P` elements containing leading "1.", "2.", "3." (digit-period-space) text spans. Ratio > 0.5 → -1.5 |
| S5 | `/Figure` elements have meaningful alt | Per `/Figure`, read `/Alt` attribute. If figure_count > 0 AND average alt-text length across figures is > 30 characters AND no figure has alt in (`image`, `figure`, `logo`, `icon`, `graphic`, file extension only, the file stem) → +1.0. **Gated on figure_count > 0**. |
| S6 | `/Figure` elements have generic or empty alt | figure_count > 0 AND (average alt < 15 chars OR > 30% of figures have alt in (`image`, `logo`, `icon`, `figure`, `graphic`)) → -1.5. **Gated on figure_count > 0**: a PDF with no figures does not fire S6. |
| S7 | Tables have `/Scope` on `/TH` | Every `/TH` element has `/Scope` ∈ {`Row`, `Column`, `Both`} → +1.0 |
| S8 | Tables missing `/Scope` on `/TH` | Any `/TH` lacks `/Scope` → -0.5 |
| S8b | Tables: all `/TH` lack `/Scope` (anti-signal) | All `/TH` elements in the document lack `/Scope` → -1.0. Stronger than S8 because every-TH-without-scope is a near-certain auto-tag tell. |
| S9 | Artifact markings present | `/Artifact` BMC/EMC pairs in content streams, or `/Type /Pagination` / `/Layout` artifact subtypes → +0.5 |
| S10 | ActualText anti-patterns | `/ActualText` values include `blank`, `space`, or empty string on non-empty spans → -0.5 per occurrence, capped at -1.5 |
| S11 | `/Lang` attributes at span level | At least one `/Span` element with `/Lang` attribute → +0.5 |
| S12 | `/StructParents` mapping completeness | Every page with content has a `/StructParents` entry, and the `/ParentTree` is well-formed → +0.5 |
| S13 | Reading order tag-tree-first | The `/StructTreeRoot` walk order matches the page content's visual top-to-bottom, left-to-right order on at least 3 sampled pages (compute via tag-tree pre-order traversal vs `/MCID` coordinate centroids) → +1.0 |
| S14 | Reading order text-frame-first (anti-signal) | Walk order matches text-frame insertion order from InDesign, which often diverges from visual order. Detected by comparing tag-tree order to visual order; if mismatched on 2+ sampled pages → -1.0 |
| S15 | `/RoleMap` present with content (anti-signal, strong) | `/StructTreeRoot /RoleMap` exists and has >= 1 entry. InDesign exports always include a RoleMap that maps standard tags to InDesign internal names. Remediation tools (PDFix, CommonLook, axesPDF) consistently strip or minimise the RoleMap because it serves no purpose after the file leaves the authoring tool. **Empirically verified**: Sadlier CH10 publisher-source had `/StyleSpan -> /Span` entry; PDFix-remediated CH11 sibling file had no RoleMap. -0.8 |
| S16 | Table sectioning AND scope combined | `/THead` present AND every `/TH` has `/Scope` set → +1.5. **Note**: `/THead` alone is NOT a reliable remediation positive: well-styled InDesign sources can produce THead from properly-defined header rows. The combination with scope completeness is what distinguishes deliberate work. Verified empirically: publisher-source CH10 post_test_table had THead + Column scope on 5/5 TH; PDFix-remediated CH11 sibling had no THead and no scope on any of 20 TH (PDFix autotag mode can actually degrade table structure). |
| S17 | Document outlines (bookmarks) tree present | `pdf.Root.get('/Outlines')` non-empty AND depth >= 2 → +0.5. Auto-tagged authoring-tool exports rarely include outlines. Remediation passes commonly add them for screen-reader navigation. **Empirically verified**: Sadlier CH10 publisher-source had no /Outlines; PDFix-remediated CH11 sibling file had a non-empty outline tree. |

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

### 2.5 Classification thresholds and override rules

Apply the following rules in order. **Override rules take priority over the score-based mapping** because the central design principle of this tool is: metadata says which tool touched the file; structural quality says whether a human reviewed the tags. When metadata and structure disagree, structure wins.

**Step 1: Hard floor and ceiling overrides (evaluate before scoring).**

- If S1 fires (no `/StructTreeRoot`) → `UNTAGGED`, confidence 1.0. Stop.
- **Autotag-pattern override**: if (S4 fires OR S6 fires) AND (M3 or M5 fires, indicating an accessibility-capable tool touched the file) → cap classification at `LIGHTLY_REMEDIATED` regardless of how strong the remaining metadata signals are. Both structural autotag tells can fire together; cap holds. This catches the "Acrobat opened the PDF and ran Autotag, leaving an Acrobat fingerprint in XMP but no human-quality tagging" case explicitly. Pure authoring-tool exports with poor structure (e.g., InDesign with generic alt text) flow through to normal scoring because no remediation tool fingerprint is present.
- **High-confidence remediation floor**: if S5 (figures have meaningful alt, average > 30 chars, no generic placeholders) AND S7 (every `/TH` has `/Scope`) AND S9 (artifact markings present) ALL fire → floor classification at `REMEDIATED`.
- **PDF/UA declared sanity check**: if M6 (PDF/UA declared) fires BUT S4 or S6 also fires → drop confidence by 0.2 and reclassify down by one bucket. PDF/UA can be falsely declared; structural quality is the truth.

**Step 2: Weighted-sum scoring (run only when no hard override fired).**

Compute `score = sum of fired-signal weights`. Map score to label:

- `score < -2`: `AUTO_TAGGED`, confidence = min(1.0, abs(score) / 5)
- `-2 <= score < 0`: `AUTO_TAGGED`, confidence = 0.5 + abs(score) / 4
- `0 <= score < 2`: `LIGHTLY_REMEDIATED`, confidence = 0.5 + score / 4
- `2 <= score < 5`: `REMEDIATED`, confidence = 0.6 + score / 10
- `score >= 5`: `WELL_REMEDIATED`, confidence = min(1.0, 0.7 + score / 15)

**Step 3: Tool-fingerprint disambiguation in evidence (informational, no score change).**

Even when classification is decided, the report should name the most likely process responsible for the current tag state, so the user knows what they are looking at. Pick the first matching pattern:

1. M4 (pure authoring producer) + M1 (single XMP event) → "Authoring-tool export autotag (likely Adobe InDesign / Microsoft Word / Apple Pages / LibreOffice based on producer string)"
2. M5 or M3 (accessibility-capable tool fingerprint) + S4 or S6 (autotag tells in structure) → "Tool-level autotag (likely Acrobat Pro's Autotag Document, PDFix autotag mode, or similar). Tool was used but structural quality indicates no human review."
3. M5 or M3 + (S5 AND S7 AND S9 all firing) → "Deliberate human remediation pass (tool fingerprint and structural quality are both consistent with human review)."
4. M6 (PDF/UA declared) + (S4 or S6 firing) → "PDF/UA declared but structural quality suggests the declaration is premature. Verify with PAC 2024."

These thresholds and overrides are calibrated against the test corpus in section 7 and re-tuned during the build. The override rules are the single most important calibration target: false positives on `REMEDIATED` (autotag PDFs misclassified as remediated) are the failure mode this tool exists to prevent.

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
