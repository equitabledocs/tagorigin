"""tagorigin metadata signals (M1 to M10, M5b).

Each function takes a PdfInspector and returns a SignalResult.
"""
from __future__ import annotations

import re
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
# M1: XMP history single event
# ------------------------------------------------------------------
def m1_xmp_history_single_event(inspector: PdfInspector) -> SignalResult:
    events = inspector.xmp_history_events()
    fired = len(events) == 1 and events[0].get("action") == "converted"
    evidence = f"{len(events)} event(s)"
    if events:
        evidence += f", first action: {events[0].get('action', 'unknown')}"
    return _make(
        "M1_xmp_history_single_event",
        "XMP history contains exactly one converted event",
        -1.5,
        fired,
        evidence,
    )


# ------------------------------------------------------------------
# M2: XMP history multiple events
# ------------------------------------------------------------------
def m2_xmp_history_multiple_events(inspector: PdfInspector) -> SignalResult:
    events = inspector.xmp_history_events()
    fired = len(events) >= 2
    return _make(
        "M2_xmp_history_multiple_events",
        "XMP history contains two or more events",
        0.5,
        fired,
        f"{len(events)} event(s)",
    )


# ------------------------------------------------------------------
# M3: XMP history names accessibility-capable tool
# ------------------------------------------------------------------
ACCESSIBILITY_TOOLS = (
    "PDFix",
    "Acrobat Pro",
    "Adobe Acrobat",
    "CommonLook",
    "axesPDF",
    "axes4",
    "NetCentric",
    "Foxit PhantomPDF",
    "Kofax Power PDF",
    "PAC ",
)


def m3_xmp_history_accessibility_tool(inspector: PdfInspector) -> SignalResult:
    events = inspector.xmp_history_events()
    fired = False
    agent_found = ""
    for evt in events:
        agent = evt.get("software_agent", "")
        for tool in ACCESSIBILITY_TOOLS:
            if tool in agent:
                fired = True
                agent_found = agent
                break
        if fired:
            break
    return _make(
        "M3_xmp_history_accessibility_tool",
        "XMP history names an accessibility-capable tool",
        1.0,
        fired,
        f"agent: {agent_found}" if fired else "no accessibility tool in history",
    )


# ------------------------------------------------------------------
# M4: Producer is pure authoring tool
# ------------------------------------------------------------------
AUTHORING_PRODUCER_PATTERNS = (
    r"Adobe PDF Library",
    r"Microsoft.*Word",
    r"Pages \d",
    r"LibreOffice",
    r"Mac OS X.*Quartz PDFContext",
)


def m4_producer_authoring_tool(inspector: PdfInspector) -> SignalResult:
    producer = inspector.producer()
    fired = any(re.search(pat, producer) for pat in AUTHORING_PRODUCER_PATTERNS)
    return _make(
        "M4_producer_authoring_tool",
        "Producer string matches a pure authoring tool",
        -1.0,
        fired,
        f"Producer: {producer}" if fired else f"Producer: {producer} (no match)",
    )


# ------------------------------------------------------------------
# M5: Producer is accessibility-capable tool
# ------------------------------------------------------------------
REMEDIATION_PRODUCER_PATTERNS = (
    r"PDFix SDK",
    r"PDFix",
    r"Acrobat Pro DC",
    r"Adobe Acrobat.*DC",
    r"CommonLook",
    r"axesPDF",
    r"axes4",
    r"NetCentric Technology",
    r"NetCentric",
)


def m5_producer_remediation_tool(inspector: PdfInspector) -> SignalResult:
    producer = inspector.producer()
    fired = any(re.search(pat, producer) for pat in REMEDIATION_PRODUCER_PATTERNS)
    return _make(
        "M5_producer_remediation_tool",
        "Producer string matches an accessibility-capable tool",
        1.5,
        fired,
        f"Producer: {producer}" if fired else f"Producer: {producer} (no match)",
    )


# ------------------------------------------------------------------
# M5b: Producer is known autotag-only output
# ------------------------------------------------------------------
AUTOTAG_PRODUCER_PATTERNS = (
    r"Acrobat Distiller",
)


def m5b_producer_autotag_only(inspector: PdfInspector) -> SignalResult:
    producer = inspector.producer()
    fired = any(re.search(pat, producer) for pat in AUTOTAG_PRODUCER_PATTERNS)
    # Also check XMP for pdfix:Mode=AutoTag
    if not fired and inspector.xmp_xml is not None:
        for elem in inspector.xmp_xml.iter():
            tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
            if tag == "Mode" and elem.text and "AutoTag" in elem.text:
                fired = True
                break
    return _make(
        "M5b_producer_autotag_only",
        "Producer or XMP indicates autotag-only output",
        -0.5,
        fired,
        f"Producer: {producer}" if fired else "no autotag-only fingerprint",
    )


# ------------------------------------------------------------------
# M6: PDF/UA conformance declared
# ------------------------------------------------------------------
def m6_pdf_ua_declared(inspector: PdfInspector) -> SignalResult:
    part = inspector.pdf_ua_part()
    fired = part is not None and part >= 1
    return _make(
        "M6_pdf_ua_declared",
        "PDF/UA conformance declared in XMP",
        2.0,
        fired,
        f"pdfuaid:part={part}" if fired else "no PDF/UA declaration",
    )


# ------------------------------------------------------------------
# M7: Linearised
# ------------------------------------------------------------------
def m7_linearised(inspector: PdfInspector) -> SignalResult:
    fired = inspector.is_linearised()
    return _make(
        "M7_linearised",
        "PDF is linearised (Fast Web View)",
        0.3,
        fired,
        "Linearised dictionary present" if fired else "Not linearised",
    )


# ------------------------------------------------------------------
# M8: Document-level Lang
# ------------------------------------------------------------------
def m8_document_lang(inspector: PdfInspector) -> SignalResult:
    lang = inspector.document_lang()
    fired = bool(lang)
    return _make(
        "M8_document_lang",
        "Document-level /Lang attribute is set",
        0.3,
        fired,
        f"Lang: {lang}" if fired else "No document Lang",
    )


# ------------------------------------------------------------------
# M9: MarkInfo /Marked
# ------------------------------------------------------------------
def m9_mark_info_marked(inspector: PdfInspector) -> SignalResult:
    val = inspector.mark_info_marked()
    fired = val is True
    return _make(
        "M9_mark_info_marked",
        "MarkInfo /Marked is true",
        0.1,
        fired,
        "Marked=true" if fired else f"Marked={val}",
    )


# ------------------------------------------------------------------
# M10: Title is non-default
# ------------------------------------------------------------------
def m10_title_non_default(inspector: PdfInspector) -> SignalResult:
    title = inspector.title()
    path = inspector.path
    fired = False
    evidence = ""
    if title:
        stem = path.stem if path else ""
        if stem and title != stem:
            fired = True
            evidence = f"Title: '{title}' (differs from filename)"
        else:
            evidence = f"Title: '{title}' (matches filename)"
    else:
        evidence = "No /Title in Info dictionary"
    return _make(
        "M10_title_non_default",
        "Title exists and does not match filename stem",
        0.3,
        fired,
        evidence,
    )


# ------------------------------------------------------------------
# Registry
# ------------------------------------------------------------------
METADATA_SIGNALS = [
    m1_xmp_history_single_event,
    m2_xmp_history_multiple_events,
    m3_xmp_history_accessibility_tool,
    m4_producer_authoring_tool,
    m5_producer_remediation_tool,
    m5b_producer_autotag_only,
    m6_pdf_ua_declared,
    m7_linearised,
    m8_document_lang,
    m9_mark_info_marked,
    m10_title_non_default,
]
