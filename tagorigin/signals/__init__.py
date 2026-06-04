"""Provenance signal modules.

Each submodule implements a layer of the detection scheme defined in
``docs/SPEC.md`` section 2:

- ``metadata`` for M1 to M10 (Info dictionary, XMP, Producer, Lang, MarkInfo, Title)
- ``structure`` for S1 to S14 (StructTreeRoot walk, list semantics, figure alt, table scope)
- ``content`` for C1 to C4 (content-stream patterns; Phase 2)
- ``vision`` for V1 to V2 (vision-assisted reading-order and alt-accuracy; Phase 3)

Phase 1 implements: metadata.M1 to M10 and structure.S1, S2, S5, S6, S7, S10.
"""
