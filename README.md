# tagorigin

**Is this PDF really accessible, or just tagged?**

Authoring tools like Adobe InDesign, Microsoft Word, and Apple Pages emit structure tags automatically on export. Those auto-emitted tags routinely fail PDF/UA and WCAG 2.1 AA because of generic alt text, lists tagged as paragraphs, reading order following text-frame placement rather than visual layout, missing scope attributes on table headers, and so on. An actively remediated PDF, by contrast, has been opened by a dedicated accessibility tool (Adobe Acrobat Pro, PDFix SDK, CommonLook, axesPDF, NetCentric) and edited with intent. The two are visually similar in the Tags panel but very different in downstream behaviour.

`tagorigin` tells you which one you have. It reads a PDF, runs a set of provenance signals, and outputs one of five classifications with a confidence score and per-signal evidence:

- `UNTAGGED`
- `AUTO_TAGGED` (authoring-tool export, no remediation pass)
- `LIGHTLY_REMEDIATED`
- `REMEDIATED`
- `WELL_REMEDIATED`

Target users: accessibility-team intake reviewers, university procurement teams vetting vendor output, publisher QA teams self-assessing their InDesign exports.

## Quick start

### Command line

```
pip install -e .
tagorigin check sample.pdf
tagorigin check sample.pdf --format json
tagorigin check sample.pdf --format markdown --report report.md
tagorigin check folder/ --recursive --csv summary.csv
tagorigin test-corpus
```

### Vision-assisted signals (optional)

The V1 (visual reading order) and V2 (alt-text accuracy) signals use an
Anthropic Claude vision model to cross-check structural signals against the
rendered page. Costs apply per page.

```
pip install -e .[vision]
$env:ANTHROPIC_API_KEY = "sk-ant-..."
tagorigin check sample.pdf --vision
tagorigin check sample.pdf --vision --vision-model claude-opus-4-7
```

### Web service

A FastAPI backend with an HTML landing page is included. Run locally:

```
pip install -e .[web]
uvicorn tagorigin.api:app --reload
```

Open `http://127.0.0.1:8000/` for the landing page, or POST a PDF to
`/audit` (JSON response) or `/audit/html` (rendered HTML report).

## Status

Phases 1, 2, 3, and 4 shipped. The tool implements:

- Metadata signals M1 to M10 plus M5b
- Structure signals S1 to S17 (S13, S14 reading-order are placeholders pending visual position analysis)
- Content-stream signals C1, C2 (C3, C4 placeholders for deep content-stream parsing)
- Vision-assisted signals V1, V2 (Anthropic Claude vision, behind `--vision` flag)
- Weighted-sum scoring with three override rules
- Text, JSON, and markdown output formats
- Batch mode with CSV summary and per-file JSON
- Bundled test corpus across UNTAGGED, AUTO_TAGGED, LIGHTLY_REMEDIATED, REMEDIATED buckets
- FastAPI web service with a plain-HTML landing page

Corpus tests pass at 100% across 18 files. WELL_REMEDIATED bucket awaits real
samples from the PDF Association Matterhorn Protocol test suite.

See `docs/SPEC.md` for the full build specification.

## Use cases

### Within EquitableDocs

**Portal intake triage.** When a student or partner uploads a document, run tagorigin before routing. UNTAGGED goes through OCR plus full tagging. AUTO_TAGGED gets flagged so the remediator does not assume the existing tags are trustworthy. REMEDIATED and WELL_REMEDIATED get fast-tracked through validation only. This is real cost saving on volunteer time.

**Before/after evidence for our own pipeline.** Run tagorigin on the publisher original and on the delivered file. The classification jump (AUTO_TAGGED to REMEDIATED) becomes the receipt that human work happened. Useful for the transparency page and for funder reports.

**University procurement vetting.** When a partner university tells you their incumbent vendor charges Rs 150 per page and delivers "accessible PDFs", tagorigin lets them check whether they are paying for remediation or for an autotag pass with a markup. This is the single most expensive misconception in the Indian market and the tool addresses it directly. It also strengthens the cost-only pricing pitch.

**Document Accessibility Check companion.** Document Accessibility Check tells the user what is wrong against WCAG and Matterhorn. tagorigin tells them where the tags came from in the first place. Different question, complementary surface.

### Outside EquitableDocs

- **Publisher self-audit.** InDesign, Word, and Pages export shops can run their own output through it before shipping to libraries. The "your file is AUTO_TAGGED, not REMEDIATED" verdict is a clear next-step trigger.
- **Government and procurement officers.** RPwD compliance reviews, GIGW audits, public-sector RFP scoring. A reviewer can demand a tagorigin classification as part of vendor delivery proof.
- **University library acquisitions.** Before signing publisher e-textbook contracts, libraries can sample-check claims of "accessible PDF" delivery.
- **Training tool.** A teaching aid for the Accessibility Collective. Members learn the difference between tagged and remediated by running the tool on known-good and known-bad files and reading the per-signal evidence.
- **Litigation support and DPO complaints.** Where an institution claims a document was accessible, a tagorigin report with signal evidence is documentary proof of the opposite.

## Known limits

- It is a heuristic classifier, not a proof. The SPEC documents that signals M3, M4, and M5 misfire on PDFix in-place saves where the producer string is preserved. The per-signal evidence output partially mitigates this, but borderline AUTO vs LIGHTLY cases will sometimes be wrong.
- The WELL_REMEDIATED bucket has no real-world calibration samples yet. The Matterhorn Protocol test suite is the next planned source.
- "tagorigin" is an engineery codename. For the public web surface a plain-language name (such as "Tag Origin Check") will replace it.

## How to contribute

This repo is built and maintained under [EquitableDocs](https://equitabledocs.org). Read `docs/SPEC.md` for the full build spec, then `CLAUDE.md` or `AGENTS.md` for the agent-facing project instructions.

## Licence

Apache License 2.0. See `LICENSE`. Attribution notices for redistribution are in `NOTICE`.

The Apache 2.0 grant covers code, not brand. "EquitableDocs" and the public-facing tool name are trademarks of EquitableDocs and are not licensed under Apache 2.0. Forks may use the code; they may not present themselves as EquitableDocs or as tagorigin.
