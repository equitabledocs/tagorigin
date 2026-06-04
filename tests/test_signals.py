"""Phase 1 tests for tagorigin signals.

These tests use the three sample PDFs provided by the project owner:
- Publisher InDesign auto-export (expected AUTO_TAGGED)
- PDFix-remediated sibling (expected LIGHTLY_REMEDIATED or REMEDIATED)
- Untagged scan (expected UNTAGGED)
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tagorigin.classify import classify
from tagorigin.inspect import PdfInspector
from tagorigin.signals.metadata import (
    m1_xmp_history_single_event,
    m4_producer_authoring_tool,
    m5_producer_remediation_tool,
    m6_pdf_ua_declared,
    m9_mark_info_marked,
    m10_title_non_default,
)
from tagorigin.signals.structure import (
    s1_no_struct_tree,
    s2_heading_hierarchy,
    s6_figure_alt_generic,
    s15_rolemap_present,
    s17_outlines_present,
)

# ------------------------------------------------------------------
# Fixtures: paths to sample PDFs
# ------------------------------------------------------------------
PUBLISHER_PDF = Path(
    r"C:\Users\deepa\Projects\pdfix-remediation\clients\slizvon-reteach\inputs\CH10\CH10\Without_Anno\Ready_for_R1\803241_sdr_se1_closereading_chap10_cert_noanno.pdf"
)
PDFIX_PDF = Path(
    r"C:\Users\deepa\Projects\pdfix-remediation\clients\slizvon-reteach\Sadlier_G1_B3\pac-final\803241_sdr_se1_closereading_chap11_cert_noanno.pdf"
)
UNTAGGED_PDF = (
    Path(__file__).resolve().parent.parent
    / "tagorigin"
    / "corpus"
    / "untagged"
    / "803241_sdr_se1_prbslvprc_less10-1_cert_noanno.pdf"
)


@pytest.fixture
def publisher_inspector():
    with PdfInspector.open(PUBLISHER_PDF) as insp:
        yield insp


@pytest.fixture
def pdfix_inspector():
    with PdfInspector.open(PDFIX_PDF) as insp:
        yield insp


@pytest.fixture
def untagged_inspector():
    with PdfInspector.open(UNTAGGED_PDF) as insp:
        yield insp


# ------------------------------------------------------------------
# Metadata signal tests
# ------------------------------------------------------------------
def test_m1_publisher_no_xmp_history(publisher_inspector):
    result = m1_xmp_history_single_event(publisher_inspector)
    assert not result.fired


def test_m4_publisher_is_authoring_tool(publisher_inspector):
    result = m4_producer_authoring_tool(publisher_inspector)
    assert result.fired
    assert "Adobe PDF Library" in result.evidence


def test_m4_pdfix_is_authoring_tool(pdfix_inspector):
    # PDFix preserves original producer
    result = m4_producer_authoring_tool(pdfix_inspector)
    assert result.fired


def test_m5_publisher_not_remediation_tool(publisher_inspector):
    result = m5_producer_remediation_tool(publisher_inspector)
    assert not result.fired


def test_m5_pdfix_not_remediation_tool(pdfix_inspector):
    # PDFix preserves original producer, so M5 does not fire
    result = m5_producer_remediation_tool(pdfix_inspector)
    assert not result.fired


def test_m6_publisher_no_pdf_ua(publisher_inspector):
    result = m6_pdf_ua_declared(publisher_inspector)
    assert not result.fired


def test_m9_publisher_marked(publisher_inspector):
    result = m9_mark_info_marked(publisher_inspector)
    assert result.fired


def test_m10_publisher_title_non_default(publisher_inspector):
    result = m10_title_non_default(publisher_inspector)
    assert result.fired


# ------------------------------------------------------------------
# Structure signal tests
# ------------------------------------------------------------------
def test_s1_publisher_has_struct_tree(publisher_inspector):
    result = s1_no_struct_tree(publisher_inspector)
    assert not result.fired


def test_s1_untagged_no_struct_tree(untagged_inspector):
    result = s1_no_struct_tree(untagged_inspector)
    assert result.fired


def test_s2_publisher_heading_hierarchy(publisher_inspector):
    result = s2_heading_hierarchy(publisher_inspector)
    assert result.fired


def test_s6_publisher_generic_alt(publisher_inspector):
    result = s6_figure_alt_generic(publisher_inspector)
    assert result.fired


def test_s6_pdfix_not_generic_alt(pdfix_inspector):
    result = s6_figure_alt_generic(pdfix_inspector)
    assert not result.fired


def test_s15_publisher_rolemap_present(publisher_inspector):
    result = s15_rolemap_present(publisher_inspector)
    assert result.fired
    assert "StyleSpan" in result.evidence


def test_s15_pdfix_no_rolemap(pdfix_inspector):
    result = s15_rolemap_present(pdfix_inspector)
    assert not result.fired


def test_s17_publisher_no_outlines(publisher_inspector):
    result = s17_outlines_present(publisher_inspector)
    assert not result.fired


def test_s17_pdfix_has_outlines(pdfix_inspector):
    result = s17_outlines_present(pdfix_inspector)
    assert result.fired


# ------------------------------------------------------------------
# End-to-end classification tests
# ------------------------------------------------------------------
def test_publisher_classified_auto_tagged():
    with PdfInspector.open(PUBLISHER_PDF) as insp:
        result = classify(insp, PUBLISHER_PDF)
    assert result.classification == "AUTO_TAGGED"


def test_pdfix_classified_higher_than_auto():
    with PdfInspector.open(PDFIX_PDF) as insp:
        result = classify(insp, PDFIX_PDF)
    # Must be at least LIGHTLY_REMEDIATED (one bucket above AUTO_TAGGED)
    assert result.classification in ("LIGHTLY_REMEDIATED", "REMEDIATED", "WELL_REMEDIATED")


def test_untagged_classified_untagged():
    with PdfInspector.open(UNTAGGED_PDF) as insp:
        result = classify(insp, UNTAGGED_PDF)
    assert result.classification == "UNTAGGED"
    assert result.confidence == 1.0


def test_publisher_pdfix_different_classifications():
    with PdfInspector.open(PUBLISHER_PDF) as p_insp:
        pub = classify(p_insp, PUBLISHER_PDF)
    with PdfInspector.open(PDFIX_PDF) as px_insp:
        pix = classify(px_insp, PDFIX_PDF)
    # PDFix must score higher (less negative or more positive)
    assert pix.score > pub.score
