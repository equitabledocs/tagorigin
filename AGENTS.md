# AGENTS.md

Project instructions for any AI coding agent (Aider, opencode, Cursor, GitHub Copilot Workspace, or others).

This file mirrors `CLAUDE.md` so any agent that reads only `AGENTS.md` still gets the full briefing. If you have just one of the two file conventions, read the other one too. They are deliberately kept in sync.

See `CLAUDE.md` for the canonical project-instruction set, hard constraints, and first-turn checklist.

See `docs/SPEC.md` for the full build specification (signals, weights, thresholds, schema, phases).

## Quick orientation

- Tool: `tagorigin`. Classifies a PDF's tag-tree provenance.
- Maintainer: EquitableDocs.
- License: Apache 2.0.
- Language: Python 3.10+.
- Primary library: `pikepdf`.
- CLI framework: `typer`.
- Schema: `pydantic`.
- Current phase: pre-MVP, scaffold only.

## Hard constraints (must follow)

1. No em-dashes or en-dashes anywhere. Use commas, colons, or full stops.
2. No AI-tell phrasing. Write plainly.
3. No mention of model providers in user-facing output (the tool, README, commit messages). Provider names are fine in `docs/` and `pyproject.toml`.
4. No emojis.
5. Plain HTML when the web UI lands. No React, no Tailwind, no SPA framework.

## Build flow

Phase 1 first. Stop after Phase 1 and ask the user before starting Phase 2. Do not auto-start vision (Phase 3); that needs explicit token-budget approval. See `CLAUDE.md` section "Build phases" for the exact scope of each phase.
