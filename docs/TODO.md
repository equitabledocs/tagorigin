# tagorigin: open follow-ups

Project-level follow-ups visible to anyone working in this repo. Cross-cutting items also live in the program tower at `C:\Users\deepa\Projects\equitabledocs-program\TODO.md` under the `tagorigin` section.

Append-only. Tick an item off when complete and date the line.

## Adoption follow-ups (from the 2026-06-04 portal adoption session)

- [ ] **Tool 6 integration: provenance as first section of every audit.** Owned by qc-claude. The brief is at `equitabledocs-qc/PORTAL-CLAUDE-BRIEF-TOOL-6-PROVENANCE-INTEGRATION-2026-06-04.md`. Scope: vendor `tagorigin` (already pinned in `equitabledocs-portal/requirements.txt` at `fcd70c4`), call `tagorigin.classify()` early in the Tool 6 pipeline, render a "Tag quality" section at the top of the Word audit, JSON, and CSV outputs. Honour the naming-discipline rule: the question H1 "Is this PDF really accessible, or just tagged?" must accompany the section header.
- [ ] **Trademark registration for "EquitableDocs".** Apache 2.0 Section 6 explicitly does not cover trademarks. Brand is the actual protection layer for `tagorigin` and the wider toolset. Priority order: India, then US and EU. Register the public-facing tool name "PDF Tag Quality Check" at the same time.
- [ ] **Marketing site catalogue entry for "PDF Tag Quality Check".** Once Tool 6 integration ships, add an entry on equitabledocs.org under the Tools heading, same template as Document Accessibility Check and AltBridge. Carries the question H1 next to the name (naming-discipline rule).

## Library follow-ups (carried over from earlier)

- [ ] **Find real WELL_REMEDIATED samples.** PAC UA Reports score as LIGHTLY_REMEDIATED because their auto-generated screenshots have generic alt text and the autotag-pattern override correctly caps them. Need hand-curated samples from the PDF Association Matterhorn Protocol test suite. Half a day.
- [ ] **Add Word, Pages, LibreOffice auto-export corpus samples.** Currently all AUTO_TAGGED corpus entries are InDesign. Need two or three samples each from Word, Pages, LibreOffice to validate cross-tool discrimination. Half a day.
- [ ] **Document the test corpus location and redistribution rights.** README claims an 18-file corpus. Confirm whether it is committed to this repo, where it lives, and whether the files are redistributable when this repo goes public.
- [ ] **Hand over the Sadlier CH10 vs CH11 calibration PDFs.** Empirical verification proved that M3, M4, M5 misfire on PDFix in-place saves using these two files. Park them where the portal-side Tool 6 integration can cross-validate.
- [ ] **Design a vision spend-cap before any future web-form vision.** V1, V2 hit a vision API per page. The hosted portal route has vision off (`TAGORIGIN_VISION=off` default). If we ever expose `--vision` from the web, design rate-and-budget guardrails first.
- [ ] **University procurement pilot.** First sales touch: offer a ten-PDF free audit to a disability services office at a university. Use it to validate the procurement use case and collect first testimonial.

## How this list relates to the program tower

The tower at `equitabledocs-program/TODO.md` is the master cross-project tracker. Items above that are cross-cutting (the three adoption follow-ups, the trademark item) also live there under `## tagorigin`. The repo-internal handover items (corpus, calibration PDFs, vision spend-cap design) live only here because they are tagorigin-specific.

When in doubt, read the tower first; it shows what the user has flagged at portfolio level.
