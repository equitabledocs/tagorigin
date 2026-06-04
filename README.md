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

## How to contribute

This repo is built and maintained under [EquitableDocs](https://equitabledocs.org). Read `docs/SPEC.md` for the full build spec, then `CLAUDE.md` or `AGENTS.md` for the agent-facing project instructions.

## Licence

MIT. See `LICENSE`.
