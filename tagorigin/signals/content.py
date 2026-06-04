"""tagorigin content-stream signals (C1 to C4).

These inspect page content streams for known autotag tells.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pikepdf

if TYPE_CHECKING:
    from tagorigin.inspect import PdfInspector

from tagorigin.models import SignalResult


def _make(id_: str, description: str, weight: float, fired: bool, evidence: str) -> SignalResult:
    return SignalResult(
        id=id_,
        description=description,
        weight=weight,
        fired=fired,
        evidence=evidence,
    )


# ------------------------------------------------------------------
# C1: Reversed-glyph footers
# ------------------------------------------------------------------
def c1_reversed_glyph_footers(inspector: PdfInspector) -> SignalResult:
    """Look for reversed text like .scitamehtaM in content streams."""
    found = 0
    # Check a sample of page content streams
    pages = inspector._get(inspector.root, "/Pages")
    if pages is None:
        return _make(
            "C1_reversed_glyph_footers",
            "Reversed-glyph footer text in content streams",
            -0.5,
            False,
            "No pages",
        )
    texts = _collect_stream_texts(inspector, pages)
    BAD = (".scitamehtaM", ".reildaS")
    for txt in texts:
        for pat in BAD:
            if pat in txt:
                found += 1
                break
    fired = found > 0
    return _make(
        "C1_reversed_glyph_footers",
        "Reversed-glyph footer text in content streams (InDesign anti-pattern)",
        -0.5,
        fired,
        f"{found} occurrence(s)" if fired else "None found",
    )


# ------------------------------------------------------------------
# C2: Doubled-glyph artifacts
# ------------------------------------------------------------------
def c2_doubled_glyph_artifacts(inspector: PdfInspector) -> SignalResult:
    """Look for repeated adjacent identical glyph runs in content streams."""
    found = 0
    pages = inspector._get(inspector.root, "/Pages")
    if pages is None:
        return _make(
            "C2_doubled_glyph_artifacts",
            "Doubled-glyph artifacts in content streams",
            -0.3,
            False,
            "No pages",
        )
    texts = _collect_stream_texts(inspector, pages)
    for txt in texts:
        # Look for repeated identical characters at word boundaries
        for word in txt.split():
            if len(word) >= 4:
                for i in range(len(word) - 1):
                    if word[i] == word[i + 1] and word[i].isalpha():
                        found += 1
                        break
    fired = found > 0
    return _make(
        "C2_doubled_glyph_artifacts",
        "Doubled-glyph artifacts in content streams",
        -0.3,
        fired,
        f"{found} occurrence(s)" if fired else "None found",
    )


# ------------------------------------------------------------------
# C3: XObject reuse with proper /Pg inheritance
# ------------------------------------------------------------------
def c3_xobject_pg_inheritance(inspector: PdfInspector) -> SignalResult:
    """Check that reused XObjects have proper /Pg set per struct element."""
    # Content-stream-level check: requires deep inspection of how
    # structure elements reference content via /Pg. Placeholder.
    return _make(
        "C3_xobject_pg_inheritance",
        "XObject reuse with proper /Pg inheritance",
        0.5,
        False,
        "Deep content-stream inspection not implemented in Phase 2",
    )


# ------------------------------------------------------------------
# C4: BDC/EMC for figures
# ------------------------------------------------------------------
def c4_figure_bdc_emc(inspector: PdfInspector) -> SignalResult:
    """Check that Figure elements use BDC/EMC with proper property dicts."""
    # Content-stream-level check: requires parsing content stream operators.
    # Placeholder.
    return _make(
        "C4_figure_bdc_emc",
        "Figure elements use /Figure BDC ... EMC with /MCID and /Alt",
        0.5,
        False,
        "Content-stream operator parsing not implemented in Phase 2",
    )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _collect_stream_texts(inspector: PdfInspector, node) -> list[str]:
    """Recursively extract text strings from content streams."""
    texts: list[str] = []
    if not isinstance(node, pikepdf.Dictionary):
        return texts
    if node.get("/Type") == "/Page":
        contents = inspector._get(node, "/Contents")
        if contents is not None:
            txt = _extract_text_from_contents(inspector, contents)
            if txt:
                texts.append(txt)
    elif node.get("/Type") == "/Pages":
        kids = inspector._get(node, "/Kids")
        if kids is not None:
            if isinstance(kids, pikepdf.Array):
                for kid in kids:
                    if isinstance(kid, pikepdf.Object):
                        try:
                            kid = inspector.pdf.get_object(kid.objgen)
                        except Exception:
                            continue
                    if isinstance(kid, pikepdf.Dictionary):
                        texts.extend(_collect_stream_texts(inspector, kid))
    return texts


def _extract_text_from_contents(inspector: PdfInspector, contents) -> str:
    """Extract raw text strings from a content stream object."""
    try:
        if isinstance(contents, pikepdf.Array):
            parts = []
            for item in contents:
                if isinstance(item, pikepdf.Object):
                    obj = inspector.pdf.get_object(item.objgen)
                    if hasattr(obj, "read_bytes"):
                        parts.append(obj.read_bytes().decode("latin-1", errors="replace"))
                    elif hasattr(obj, "get"):
                        raw = obj.get("/Filter")
                        if raw is None:
                            raw_str = str(obj).encode("latin-1", errors="replace")
                            parts.append(raw_str.decode("latin-1", errors="replace"))
            return "".join(parts)
        elif isinstance(contents, pikepdf.Object):
            obj = inspector.pdf.get_object(contents.objgen)
            if hasattr(obj, "read_bytes"):
                return obj.read_bytes().decode("latin-1", errors="replace")
        elif isinstance(contents, bytes):
            return contents.decode("latin-1", errors="replace")
    except Exception:
        pass
    return ""


# ------------------------------------------------------------------
# Registry
# ------------------------------------------------------------------
CONTENT_SIGNALS = [
    c1_reversed_glyph_footers,
    c2_doubled_glyph_artifacts,
    c3_xobject_pg_inheritance,
    c4_figure_bdc_emc,
]
