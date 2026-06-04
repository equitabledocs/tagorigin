"""tagorigin report.py: text and JSON renderers for ProvenanceResult."""
from __future__ import annotations

from pathlib import Path

from tagorigin.models import ProvenanceResult


def render_text(result: ProvenanceResult) -> str:
    lines: list[str] = [
        f"File: {result.file}",
        f"Size: {result.file_size_bytes:,} bytes",
        f"MD5:  {result.file_md5}",
        "",
        f"Classification: {result.classification}",
        f"Confidence:     {result.confidence:.2f}",
        f"Score:          {result.score:.2f}",
        "",
        "Summary:",
        f"  {result.summary}",
        "",
        "Recommendation:",
        f"  {result.recommendation}",
        "",
        "Signals:",
    ]
    for sig in result.signals:
        marker = "[+]" if sig.fired else "[ ]"
        lines.append(
            f"  {marker} {sig.id:<40} weight={sig.weight:+.2f}  {sig.evidence}"
        )
    lines.append("")
    return "\n".join(lines)


def render_json(result: ProvenanceResult) -> str:
    return result.model_dump_json(indent=2)


def write_report(result: ProvenanceResult, path: Path) -> None:
    text = render_text(result)
    path.write_text(text, encoding="utf-8")
