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

```
pip install -e .
tagorigin check sample.pdf
tagorigin check sample.pdf --format json
tagorigin check sample.pdf --verbose
```

## Status

Phase 1 complete. The tool implements metadata signals M1 to M10, structure signals S1, S2, S5, S6, S7, S8, S8b, S10, S15, S16, S17, weighted-sum scoring with override rules, and text plus JSON output. See `docs/SPEC.md` for the full build specification and remaining Phase 2 to Phase 4 work.

## How to contribute

This repo is built and maintained under [EquitableDocs](https://equitabledocs.org). Read `docs/SPEC.md` for the full build spec, then `CLAUDE.md` or `AGENTS.md` for the agent-facing project instructions.

## Licence

MIT. See `LICENSE`.
