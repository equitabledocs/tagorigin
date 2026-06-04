"""tagorigin structure signals (S1, S2, S5, S6, S7, S8, S8b, S10, S15, S16, S17).

Each function takes a PdfInspector and returns a SignalResult.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tagorigin.inspect import PdfInspector

from tagorigin.models import SignalResult


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _make(id_: str, description: str, weight: float, fired: bool, evidence: str) -> SignalResult:
    return SignalResult(
        id=id_,
        description=description,
        weight=weight,
        fired=fired,
        evidence=evidence,
    )


# ------------------------------------------------------------------
# S1: No StructTreeRoot
# ------------------------------------------------------------------
def s1_no_struct_tree(inspector: PdfInspector) -> SignalResult:
    fired = not inspector.has_struct_tree()
    return _make(
        "S1_no_struct_tree",
        "No /StructTreeRoot or empty structure tree",
        -3.0,
        fired,
        "No structure tree" if fired else "Structure tree present",
    )


# ------------------------------------------------------------------
# S2: Heading hierarchy present
# ------------------------------------------------------------------
def s2_heading_hierarchy(inspector: PdfInspector) -> SignalResult:
    tally = inspector.tag_tally()
    h1 = tally.get("/H1", 0)
    h2 = tally.get("/H2", 0)
    # Check for skipped levels: if we have H3 but no H2, or H4 but no H3, etc.
    levels = []
    for i in range(1, 7):
        if tally.get(f"/H{i}", 0) > 0:
            levels.append(i)
    skipped = False
    if len(levels) >= 2:
        for a, b in zip(levels, levels[1:], strict=False):
            if b - a > 1:
                skipped = True
                break
    fired = h1 >= 1 and h2 >= 1 and not skipped
    evidence = f"H1={h1}, H2={h2}, levels={levels}"
    if skipped:
        evidence += " (skipped levels detected)"
    return _make(
        "S2_heading_hierarchy",
        "Heading hierarchy present with no skipped levels",
        0.3,
        fired,
        evidence,
    )


# ------------------------------------------------------------------
# S5: Figure alt meaningful
# ------------------------------------------------------------------
GENERIC_ALT_TOKENS = {"image", "logo", "icon", "figure", "graphic"}


def s5_figure_alt_meaningful(inspector: PdfInspector) -> SignalResult:
    figures = inspector.figure_alt_data()
    count = len(figures)
    if count == 0:
        return _make(
            "S5_figure_alt_meaningful",
            "Figures have meaningful alt text",
            1.0,
            False,
            "No figures found",
        )
    lengths = [len(f["alt"]) for f in figures]
    avg_len = sum(lengths) / count
    has_generic = any(
        any(tok in f["alt"].lower() for tok in GENERIC_ALT_TOKENS) for f in figures
    )
    fired = avg_len > 30 and not has_generic
    evidence = (
        f"{count} figures, avg alt length={avg_len:.1f}, generic={has_generic}"
    )
    return _make(
        "S5_figure_alt_meaningful",
        "Figures have meaningful alt text (avg > 30 chars, no generic placeholders)",
        1.0,
        fired,
        evidence,
    )


# ------------------------------------------------------------------
# S6: Figure alt generic or empty
# ------------------------------------------------------------------
def s6_figure_alt_generic(inspector: PdfInspector) -> SignalResult:
    figures = inspector.figure_alt_data()
    count = len(figures)
    if count == 0:
        return _make(
            "S6_figure_alt_generic",
            "Figures have generic or empty alt text",
            -1.5,
            False,
            "No figures found",
        )
    lengths = [len(f["alt"]) for f in figures]
    avg_len = sum(lengths) / count
    generic_count = sum(
        1
        for f in figures
        if any(tok in f["alt"].lower() for tok in GENERIC_ALT_TOKENS)
    )
    generic_ratio = generic_count / count
    fired = avg_len < 15 or generic_ratio > 0.30
    evidence = (
        f"{count} figures, avg alt length={avg_len:.1f}, "
        f"generic ratio={generic_ratio:.2f}"
    )
    return _make(
        "S6_figure_alt_generic",
        "Figures have generic or empty alt text",
        -1.5,
        fired,
        evidence,
    )


# ------------------------------------------------------------------
# S7: Tables have Scope on TH
# ------------------------------------------------------------------
def s7_table_th_scope(inspector: PdfInspector) -> SignalResult:
    th_data = inspector.table_th_data()
    count = len(th_data)
    if count == 0:
        return _make(
            "S7_table_th_scope",
            "Every /TH element has /Scope set",
            1.0,
            False,
            "No /TH elements found",
        )
    all_scoped = all(d["scope"] is not None for d in th_data)
    valid_scopes = all(
        d["scope"] in {"Row", "Column", "Both"} for d in th_data if d["scope"]
    )
    fired = all_scoped and valid_scopes
    evidence = f"{count} /TH elements, all_scoped={all_scoped}, valid_scopes={valid_scopes}"
    return _make(
        "S7_table_th_scope",
        "Every /TH element has /Scope set to Row, Column, or Both",
        1.0,
        fired,
        evidence,
    )


# ------------------------------------------------------------------
# S8: Any TH missing Scope
# ------------------------------------------------------------------
def s8_table_th_missing_scope(inspector: PdfInspector) -> SignalResult:
    th_data = inspector.table_th_data()
    count = len(th_data)
    if count == 0:
        return _make(
            "S8_table_th_missing_scope",
            "Any /TH lacks /Scope",
            -0.5,
            False,
            "No /TH elements found",
        )
    missing = any(d["scope"] is None for d in th_data)
    return _make(
        "S8_table_th_missing_scope",
        "At least one /TH element lacks /Scope",
        -0.5,
        missing,
        f"{count} /TH elements, missing scope={missing}",
    )


# ------------------------------------------------------------------
# S8b: All TH lack Scope (strong anti-signal)
# ------------------------------------------------------------------
def s8b_all_th_missing_scope(inspector: PdfInspector) -> SignalResult:
    th_data = inspector.table_th_data()
    count = len(th_data)
    if count == 0:
        return _make(
            "S8b_all_th_missing_scope",
            "All /TH elements lack /Scope",
            -1.0,
            False,
            "No /TH elements found",
        )
    all_missing = all(d["scope"] is None for d in th_data)
    return _make(
        "S8b_all_th_missing_scope",
        "All /TH elements lack /Scope",
        -1.0,
        all_missing,
        f"{count} /TH elements, all missing scope={all_missing}",
    )


# ------------------------------------------------------------------
# S10: ActualText anti-patterns
# ------------------------------------------------------------------
def s10_actual_text_anti_patterns(inspector: PdfInspector) -> SignalResult:
    issues = inspector.actual_text_issues()
    count = len(issues)
    # Capped at -1.5 total, -0.5 per occurrence
    raw_weight = -0.5 * count
    if raw_weight < -1.5:
        raw_weight = -1.5
    fired = count > 0
    return _make(
        "S10_actual_text_anti_patterns",
        "ActualText values contain blank, space, or empty string",
        raw_weight,
        fired,
        f"{count} issue(s) found",
    )


# ------------------------------------------------------------------
# S15: RoleMap present with content
# ------------------------------------------------------------------
def s15_rolemap_present(inspector: PdfInspector) -> SignalResult:
    entries = inspector.rolemap_entries()
    fired = len(entries) > 0
    return _make(
        "S15_rolemap_present",
        "/RoleMap exists and has entries (InDesign export tell)",
        -0.8,
        fired,
        f"{len(entries)} entries: {list(entries.items())[:3]}" if fired else "No /RoleMap",
    )


# ------------------------------------------------------------------
# S16: Table sectioning AND scope combined
# ------------------------------------------------------------------
def s16_table_sectioning_and_scope(inspector: PdfInspector) -> SignalResult:
    has_thead = inspector.has_thead()
    th_data = inspector.table_th_data()
    th_count = len(th_data)
    if th_count == 0:
        return _make(
            "S16_table_sectioning_and_scope",
            "/THead present AND every /TH has /Scope",
            1.5,
            False,
            "No /TH elements found",
        )
    all_scoped = all(d["scope"] is not None for d in th_data)
    fired = has_thead and all_scoped
    return _make(
        "S16_table_sectioning_and_scope",
        "/THead present and every /TH has /Scope",
        1.5,
        fired,
        f"THead={has_thead}, TH count={th_count}, all_scoped={all_scoped}",
    )


# ------------------------------------------------------------------
# S17: Document outlines present
# ------------------------------------------------------------------
def s17_outlines_present(inspector: PdfInspector) -> SignalResult:
    depth = inspector.outlines_depth()
    fired = depth >= 2
    return _make(
        "S17_outlines_present",
        "Document outline (bookmarks) tree present with depth >= 2",
        0.5,
        fired,
        f"Outline depth={depth}" if fired else "No outlines or depth < 2",
    )


# ------------------------------------------------------------------
# Registry
# ------------------------------------------------------------------
STRUCTURE_SIGNALS = [
    s1_no_struct_tree,
    s2_heading_hierarchy,
    s5_figure_alt_meaningful,
    s6_figure_alt_generic,
    s7_table_th_scope,
    s8_table_th_missing_scope,
    s8b_all_th_missing_scope,
    s10_actual_text_anti_patterns,
    s15_rolemap_present,
    s16_table_sectioning_and_scope,
    s17_outlines_present,
]
