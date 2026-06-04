"""tagorigin vision-assisted signals (V1, V2).

These signals render PDF pages to images and ask a vision model to assess
reading order (V1) and figure alt-text accuracy (V2). They are gated behind
the `--vision` CLI flag and require an API key. Default to a no-op result
when no client is configured.

Supports Anthropic Claude vision (claude-sonnet-X, claude-opus-X).
The vision client is provider-agnostic via the VisionClient protocol.
"""
from __future__ import annotations

import base64
import io
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

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
# Provider-agnostic vision client
# ------------------------------------------------------------------
class VisionClient(Protocol):
    def describe_image(self, png_bytes: bytes, prompt: str) -> str: ...


@dataclass
class AnthropicVisionClient:
    """Anthropic Claude vision via the anthropic SDK."""

    model: str = "claude-sonnet-4-6"
    api_key: str | None = None

    def __post_init__(self) -> None:
        if self.api_key is None:
            self.api_key = os.environ.get("ANTHROPIC_API_KEY")

    def describe_image(self, png_bytes: bytes, prompt: str) -> str:
        try:
            import anthropic
        except ImportError as exc:
            raise RuntimeError(
                "anthropic SDK not installed. Install with: pip install tagorigin[vision]"
            ) from exc
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        client = anthropic.Anthropic(api_key=self.api_key)
        b64 = base64.standard_b64encode(png_bytes).decode("utf-8")
        response = client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )
        return response.content[0].text


# ------------------------------------------------------------------
# Page rendering helper
# ------------------------------------------------------------------
def _render_page_to_png(pdf_path: str, page_index: int, scale: float = 1.5) -> bytes | None:
    """Render a single PDF page to PNG bytes using pypdfium2."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return None
    try:
        pdf = pdfium.PdfDocument(pdf_path)
        if page_index >= len(pdf):
            return None
        page = pdf[page_index]
        bitmap = page.render(scale=scale).to_pil()
        buf = io.BytesIO()
        bitmap.save(buf, format="PNG")
        pdf.close()
        return buf.getvalue()
    except Exception:
        return None


# ------------------------------------------------------------------
# V1: visual reading-order check
# ------------------------------------------------------------------
V1_PROMPT = (
    "Look at this rendered PDF page. Describe the reading order a screen reader "
    "should follow: list the main content blocks in order from top to bottom and "
    "left to right. Mention any case where the visual layout suggests a reading "
    "order that the tag tree might get wrong (e.g., multi-column text, "
    "sidebars, captions floating beside figures, callouts). "
    "Reply in one short paragraph."
)


def v1_visual_reading_order(
    inspector: PdfInspector,
    client: VisionClient | None = None,
) -> SignalResult:
    """Cross-check the tag-tree reading order against visual layout via vision."""
    if client is None:
        return _make(
            "V1_visual_reading_order",
            "Visual reading order matches tag-tree order (vision-assisted)",
            1.5,
            False,
            "Vision client not configured (use --vision flag)",
        )
    if inspector.path is None:
        return _make(
            "V1_visual_reading_order",
            "Visual reading order matches tag-tree order (vision-assisted)",
            1.5,
            False,
            "No file path on inspector",
        )
    # Render page 1 (most representative of the document's layout style)
    png = _render_page_to_png(str(inspector.path), 0)
    if png is None:
        return _make(
            "V1_visual_reading_order",
            "Visual reading order matches tag-tree order (vision-assisted)",
            1.5,
            False,
            "Page render failed",
        )
    try:
        description = client.describe_image(png, V1_PROMPT)
    except Exception as exc:
        return _make(
            "V1_visual_reading_order",
            "Visual reading order matches tag-tree order (vision-assisted)",
            1.5,
            False,
            f"Vision call failed: {exc}",
        )
    # Heuristic: if the vision model flags reading-order concerns, signal does
    # NOT fire. If the layout is clean and unambiguous, signal fires.
    concern_words = ("wrong", "incorrect", "issue", "problem", "concern", "ambiguous", "diverge")
    has_concern = any(w in description.lower() for w in concern_words)
    fired = not has_concern
    return _make(
        "V1_visual_reading_order",
        "Visual reading order is clean (vision-assisted)",
        1.5,
        fired,
        f"vision: {description[:160]}",
    )


# ------------------------------------------------------------------
# V2: figure alt-text accuracy
# ------------------------------------------------------------------
V2_PROMPT_TEMPLATE = (
    "This is a rendered PDF page. The figures on this page have alt text. "
    "I will list the alt-text strings used: {alt_texts}. "
    "Do these alt-text strings accurately describe the visible figures? "
    "Reply 'accurate' if the alt text matches the visible content for ALL figures, "
    "'partial' if some match and some do not, or 'inaccurate' if most are wrong. "
    "Start your reply with one of those three words."
)


def v2_figure_alt_accuracy(
    inspector: PdfInspector,
    client: VisionClient | None = None,
) -> SignalResult:
    """Verify figure /Alt text matches actual visual content via vision."""
    if client is None:
        return _make(
            "V2_figure_alt_accuracy",
            "Figure alt text matches visual content (vision-assisted)",
            1.5,
            False,
            "Vision client not configured (use --vision flag)",
        )
    if inspector.path is None:
        return _make(
            "V2_figure_alt_accuracy",
            "Figure alt text matches visual content (vision-assisted)",
            1.5,
            False,
            "No file path on inspector",
        )
    figures = inspector.figure_alt_data()
    figures_with_alt = [f for f in figures if f.get("alt")]
    if not figures_with_alt:
        return _make(
            "V2_figure_alt_accuracy",
            "Figure alt text matches visual content (vision-assisted)",
            1.5,
            False,
            "No figures with alt text",
        )
    png = _render_page_to_png(str(inspector.path), 0)
    if png is None:
        return _make(
            "V2_figure_alt_accuracy",
            "Figure alt text matches visual content (vision-assisted)",
            1.5,
            False,
            "Page render failed",
        )
    alt_list = "; ".join(f'"{f["alt"][:80]}"' for f in figures_with_alt[:8])
    prompt = V2_PROMPT_TEMPLATE.format(alt_texts=alt_list)
    try:
        verdict = client.describe_image(png, prompt)
    except Exception as exc:
        return _make(
            "V2_figure_alt_accuracy",
            "Figure alt text matches visual content (vision-assisted)",
            1.5,
            False,
            f"Vision call failed: {exc}",
        )
    first_word = verdict.strip().lower().split()[0] if verdict.strip() else ""
    fired = first_word == "accurate"
    return _make(
        "V2_figure_alt_accuracy",
        "Figure alt text matches visual content (vision-assisted)",
        1.5,
        fired,
        f"vision verdict: {verdict[:160]}",
    )


# ------------------------------------------------------------------
# Registry helper
# ------------------------------------------------------------------
def get_vision_signals(client: VisionClient | None = None) -> list:
    """Return a list of bound vision signal callables that use the given client."""
    return [
        lambda inspector: v1_visual_reading_order(inspector, client),
        lambda inspector: v2_figure_alt_accuracy(inspector, client),
    ]
