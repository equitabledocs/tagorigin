"""tagorigin classify.py: weighted-sum scoring, threshold mapping, and override rules.

Override rules take priority over score-based mapping.
When metadata and structure disagree, structure wins.
"""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from tagorigin.models import ProvenanceResult, SignalResult

if TYPE_CHECKING:
    from tagorigin.inspect import PdfInspector

from tagorigin.signals.content import CONTENT_SIGNALS
from tagorigin.signals.metadata import METADATA_SIGNALS
from tagorigin.signals.structure import STRUCTURE_SIGNALS

# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
# Config
# ------------------------------------------------------------------
CLASSIFICATIONS = [
    "UNTAGGED",
    "AUTO_TAGGED",
    "LIGHTLY_REMEDIATED",
    "REMEDIATED",
    "WELL_REMEDIATED",
]


def recommendations() -> dict[str, str]:
    return {
        "UNTAGGED": (
            "Untagged PDF. Run OCR and full structural tagging before any "
            "accessibility work. Treat as raw input."
        ),
        "AUTO_TAGGED": (
            "Publisher-original PDF with authoring-tool auto-tags. No accessibility "
            "remediation pass detected. Treat as from-scratch remediation input. "
            "Expect typical authoring-tool defects: reading order from text frames, "
            "generic alt text, lists tagged as paragraphs, table headers without scope."
        ),
        "LIGHTLY_REMEDIATED": (
            "Single remediation touch detected, but semantic depth is limited. Run a "
            "full PDF/UA + WCAG 2.1 AA QC pass. Likely needs additional remediation work."
        ),
        "REMEDIATED": (
            "Deliberate remediation pass detected. Recommend a verification QC pass "
            "(PAC 2024, NVDA end-to-end) before sign-off. Treat as reteach input if a "
            "vendor defect log accompanies the file."
        ),
        "WELL_REMEDIATED": (
            "Strong remediation evidence including PDF/UA conformance. Minimal QC "
            "needed beyond automated checks. Spot-check with screen reader before delivery."
        ),
    }


def _classification_index(label: str) -> int:
    try:
        return CLASSIFICATIONS.index(label)
    except ValueError:
        return -1


def _step_down(label: str) -> str:
    idx = _classification_index(label)
    if idx > 0:
        return CLASSIFICATIONS[idx - 1]
    return label


# ------------------------------------------------------------------
# Main entry
# ------------------------------------------------------------------
def classify(inspector: PdfInspector, path: Path) -> ProvenanceResult:
    metadata_signals = [fn(inspector) for fn in METADATA_SIGNALS]
    structure_signals = [fn(inspector) for fn in STRUCTURE_SIGNALS]
    content_signals = [fn(inspector) for fn in CONTENT_SIGNALS]
    signals = metadata_signals + structure_signals + content_signals

    # Build lookup by id for override checks
    signal_map: dict[str, SignalResult] = {s.id: s for s in signals}

    # Gather raw metadata for the report
    meta = {
        "producer": inspector.producer(),
        "creator": inspector.creator(),
        "title": inspector.title(),
        "document_lang": inspector.document_lang(),
        "mark_info_marked": inspector.mark_info_marked(),
        "linearised": inspector.is_linearised(),
        "xmp_event_count": len(inspector.xmp_history_events()),
        "xmp_history_agents": [e.get("software_agent", "") for e in inspector.xmp_history_events()],
        "pdf_ua_part": inspector.pdf_ua_part(),
        "tag_tally": inspector.tag_tally(),
        "rolemap_entries": len(inspector.rolemap_entries()),
        "outlines_depth": inspector.outlines_depth(),
    }

    # ------------------------------------------------------------------
    # Step 1: Hard overrides
    # ------------------------------------------------------------------
    s1 = signal_map.get("S1_no_struct_tree")
    s5 = signal_map.get("S5_figure_alt_meaningful")
    s6 = signal_map.get("S6_figure_alt_generic")
    s7 = signal_map.get("S7_table_th_scope")
    s9 = signal_map.get("S9_artifact_markings")
    m6 = signal_map.get("M6_pdf_ua_declared")

    override_applied = False
    label = "AUTO_TAGGED"
    confidence = 0.5
    raw_score = 0.0
    summary = ""

    m3 = signal_map.get("M3_xmp_history_accessibility_tool")
    m5 = signal_map.get("M5_producer_remediation_tool")

    # S1: no struct tree -> UNTAGGED
    if s1 and s1.fired:
        label = "UNTAGGED"
        confidence = 1.0
        override_applied = True
        summary = "No structure tree present. Classification is UNTAGGED."

    # Autotag-pattern override: if S6 fires AND an accessibility tool fingerprint
    # (M3 or M5) is present, cap at LIGHTLY_REMEDIATED. This catches the case
    # where a tool ran autotag but the structural quality is poor. Pure
    # authoring-tool exports with poor structure flow through to normal scoring.
    elif s6 and s6.fired and ((m3 and m3.fired) or (m5 and m5.fired)):
        label = "LIGHTLY_REMEDIATED"
        confidence = 0.6
        override_applied = True
        summary = (
            "Accessibility tool fingerprint detected but figure alt text is generic. "
            "Likely tool-level autotag without human review. "
            "Classification capped at LIGHTLY_REMEDIATED."
        )

    # High-confidence remediation floor: if S5 AND S7 AND S9 fire -> floor at REMEDIATED
    elif s5 and s5.fired and s7 and s7.fired and s9 and s9.fired:
        label = "REMEDIATED"
        confidence = 0.75
        override_applied = True
        summary = (
            "Meaningful figure alt text, complete table header scope, "
            "and artifact markings detected. Floor classification is REMEDIATED."
        )

    if override_applied:
        # PDF/UA sanity check: only apply when we landed on the remediation floor.
        # The autotag-pattern override already accounts for S6 firing, so applying
        # M6+S6 dampening on top would double-demote.
        is_remediation_floor = label in ("REMEDIATED", "WELL_REMEDIATED")
        if is_remediation_floor and m6 and m6.fired and s6 and s6.fired:
            label = _step_down(label)
            confidence = max(0.0, confidence - 0.2)
            summary += " PDF/UA declaration dampened because structural quality contradicts it."

        raw_score = sum(s.weight for s in signals if s.fired)
        recs = recommendations()
        return ProvenanceResult(
            file=str(path),
            file_size_bytes=inspector.file_size_bytes(),
            file_md5=inspector.file_md5(),
            classification=label,
            confidence=round(confidence, 2),
            score=round(raw_score, 2),
            signals=signals,
            summary=summary.strip(),
            recommendation=recs.get(label, ""),
            metadata=meta,
        )

    # ------------------------------------------------------------------
    # Step 2: Weighted-sum scoring
    # ------------------------------------------------------------------
    raw_score = sum(s.weight for s in signals if s.fired)

    # Dampen M6 if S6 fires (PDF/UA falsely declared on auto-tagged file)
    if m6 and m6.fired and s6 and s6.fired:
        raw_score -= 1.0  # Reduce M6 effective weight from +2.0 to +1.0

    if raw_score < -2:
        label = "AUTO_TAGGED"
        confidence = min(1.0, abs(raw_score) / 5)
    elif -2 <= raw_score < 0:
        label = "AUTO_TAGGED"
        confidence = 0.5 + abs(raw_score) / 4
    elif 0 <= raw_score < 2:
        label = "LIGHTLY_REMEDIATED"
        confidence = 0.5 + raw_score / 4
    elif 2 <= raw_score < 5:
        label = "REMEDIATED"
        confidence = 0.6 + raw_score / 10
    else:  # score >= 5
        label = "WELL_REMEDIATED"
        confidence = min(1.0, 0.7 + raw_score / 15)

    confidence = max(0.0, min(1.0, confidence))

    # ------------------------------------------------------------------
    # Step 3: Tool-fingerprint disambiguation (informational summary)
    # ------------------------------------------------------------------
    m3 = signal_map.get("M3_xmp_history_accessibility_tool")
    m4 = signal_map.get("M4_producer_authoring_tool")
    m5 = signal_map.get("M5_producer_remediation_tool")

    if m4 and m4.fired:
        summary = (
            "Authoring-tool export autotag (likely Adobe InDesign / Microsoft Word / "
            "Apple Pages / LibreOffice based on producer string)."
        )
    elif (m5 and m5.fired) or (m3 and m3.fired):
        if s6 and s6.fired:
            summary = (
                "Tool-level autotag (likely Acrobat Pro's Autotag Document, PDFix "
                "autotag mode, or similar). Tool was used but structural quality "
                "indicates no human review."
            )
        elif s5 and s5.fired and s7 and s7.fired:
            summary = (
                "Deliberate human remediation pass (tool fingerprint and structural "
                "quality are both consistent with human review)."
            )
        else:
            summary = (
                f"Accessibility-capable tool fingerprint detected ({label}). "
                "Structural signals are mixed."
            )
    elif m6 and m6.fired and s6 and s6.fired:
        summary = (
            "PDF/UA declared but structural quality suggests the declaration is "
            "premature. Verify with PAC 2024."
        )
    else:
        summary = f"Classification based on {len([s for s in signals if s.fired])} fired signals."

    recs = recommendations()
    return ProvenanceResult(
        file=str(path),
        file_size_bytes=inspector.file_size_bytes(),
        file_md5=inspector.file_md5(),
        classification=label,
        confidence=round(confidence, 2),
        score=round(raw_score, 2),
        signals=signals,
        summary=summary.strip(),
        recommendation=recs.get(label, ""),
        metadata=meta,
    )
