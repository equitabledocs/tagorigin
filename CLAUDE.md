# tagorigin: agent-facing project instructions

This file is read by Claude Code (and by Aider, opencode, Cursor) on session start. Read this before writing any code. The full build spec is at `docs/SPEC.md`.

## What this project is

A Python CLI tool plus optional FastAPI wrapper that classifies a PDF's tag-tree provenance into one of five buckets: `UNTAGGED`, `AUTO_TAGGED`, `LIGHTLY_REMEDIATED`, `REMEDIATED`, `WELL_REMEDIATED`. The classification distinguishes authoring-tool auto-tagged PDFs (InDesign, Word, Pages) from PDFs that have been through a deliberate accessibility remediation pass.

Detailed design, signal list, weights, thresholds, output schema, and CLI surface live in `docs/SPEC.md`. Do not re-derive any of that; follow the spec.

## Build phases

Work through the phases in order. Do not skip ahead.

1. **Phase 1 MVP** (6 to 8 focused hours). Folder scaffold (already in place), `pyproject.toml`, metadata signals M1 to M10, structure signals S1, S2, S5, S6, S7, S10, classifier, CLI `check` subcommand, text + JSON output. Three hand-run smoke tests on user-supplied PDFs. Stop and ask the user before starting Phase 2.
2. **Phase 2** full signal set, content-stream signals, markdown report renderer, batch mode, bundled corpus, weight calibration.
3. **Phase 3** vision-assisted signals (V1, V2), provider-agnostic vision client. Do not auto-start this phase; it requires explicit token-budget approval from the user.
4. **Phase 4** FastAPI wrapper, HTML upload form, portal integration.

## Hard constraints (must follow)

These are non-negotiable. Violating any of them is a delivery failure.

1. No em-dashes or en-dashes anywhere. Code comments, docstrings, README, commit messages. Use commas, colons, or full stops.
2. No AI-tell phrasing in any output. Avoid the transitional and meta-commentary patterns common in machine-generated prose. Write plainly.
3. No mention of "Claude", "Anthropic", "GPT", "ChatGPT", "OpenAI", "assistant", "AI" in the tool's output, README, or commit messages. The tool is `tagorigin`; the maintainer is `EquitableDocs`. (Tool/provider names ARE fine inside `docs/SPEC.md` and `pyproject.toml` where they reference real APIs.)
4. No emojis anywhere unless explicitly requested.
5. Python 3.10+. Use modern typing and `match` statements where they help.
6. Plain HTML when the web UI lands in Phase 4. Semantic HTML5, minimum 16px body text, rem units, visible focus indicators. No React, no Tailwind, no SPA framework.
7. Output formats: text (default), JSON (`--format json`), markdown (`--report file.md`). No emoji icons, no ANSI colour by default (use a flag if you want colour).

## Standing process rules

These are project-wide rules from the EquitableDocs handbook. Honour them without restating in chat.

1. Confirm before risky or irreversible actions: force-push, mass renames, dropping any user data, modifying CI in ways that affect publish. Local commits and edits are fine; pushes to main require explicit user approval per session.
2. Dual-write on decisions: when you pick one approach over another, log the decision in `docs/DECISIONS.md` (create the file if it does not exist) the same turn you make the choice.
3. Paper before schema: any new data structure or output format gets a short markdown spec in `docs/` first, user sign-off, then the code.

## File layout

```
tagorigin/
├── README.md
├── CLAUDE.md              (this file)
├── AGENTS.md              (mirror for Aider / opencode / Cursor)
├── pyproject.toml
├── LICENSE
├── .gitignore
├── tagorigin/
│   ├── __init__.py
│   ├── cli.py             (typer entry, `check` subcommand)
│   ├── inspect.py         (pikepdf wrapper for metadata + structure extraction)
│   ├── classify.py        (weighted-sum scoring, threshold mapping)
│   ├── report.py          (JSON + markdown + text renderers)
│   └── signals/
│       ├── __init__.py
│       ├── metadata.py    (M1 to M10)
│       ├── structure.py   (S1 to S14)
│       ├── content.py     (C1 to C4, Phase 2)
│       └── vision.py      (V1 to V2, Phase 3)
├── tests/
│   └── (smoke tests, corpus tests in Phase 2)
└── docs/
    └── SPEC.md            (the full build specification)
```

## First-turn checklist

When you open this project in a fresh session, do this in order:

1. Read this file (you are reading it now).
2. Read `docs/SPEC.md` end to end. Do not skim. The signal definitions and weights are exact.
3. Read `pyproject.toml` to see which deps are pinned. If empty or missing, set it up per the spec.
4. Read `README.md` for the user-facing framing.
5. Check the git log to see what has already been done.
6. Confirm with the user: which phase to work on, which agent / model is driving, any user-provided sample PDFs for smoke testing.
7. Propose your plan in two or three sentences. Wait for user redirect.
8. Begin work.
