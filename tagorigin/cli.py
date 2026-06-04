"""tagorigin CLI entry point (typer)."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import typer

from tagorigin.classify import classify
from tagorigin.inspect import PdfInspector
from tagorigin.report import render_json, render_markdown, render_text

app = typer.Typer(
    name="tagorigin",
    help="Classify the provenance of a PDF's tag tree.",
    no_args_is_help=True,
)


def _find_pdfs(folder: Path, recursive: bool) -> list[Path]:
    if recursive:
        return sorted(folder.rglob("*.pdf"))
    return sorted(folder.glob("*.pdf"))


@app.command()
def check(
    target: Path = typer.Argument(..., exists=True, help="PDF file or folder to inspect."),
    fmt: str = typer.Option("text", "--format", help="Output format: text, json, markdown."),
    report: Path | None = typer.Option(None, "--report", help="Write a report to this file."),
    recursive: bool = typer.Option(False, "--recursive", help="Walk subdirectories."),
    csv_out: Path | None = typer.Option(None, "--csv", help="Write CSV summary to this file."),
    json_dir: Path | None = typer.Option(
        None, "--json-dir", help="Write per-file JSON to this folder."
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Show all signals in output."),
) -> None:
    """Run provenance audit on a PDF or a folder of PDFs."""
    if target.is_dir():
        pdfs = _find_pdfs(target, recursive)
        if not pdfs:
            typer.echo(f"No PDF files found in {target}", err=True)
            raise typer.Exit(code=64)

        results: list[tuple[Path, object]] = []
        for pdf in pdfs:
            try:
                with PdfInspector.open(pdf) as inspector:
                    result = classify(inspector, pdf)
                results.append((pdf, result))
            except Exception as exc:
                typer.echo(f"Failed to process {pdf}: {exc}", err=True)

        if csv_out:
            with csv_out.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow([
                    "file", "size_bytes", "md5", "classification",
                    "confidence", "score", "summary",
                ])
                for pdf, result in results:
                    writer.writerow([
                        str(pdf),
                        result.file_size_bytes,
                        result.file_md5,
                        result.classification,
                        result.confidence,
                        result.score,
                        result.summary,
                    ])
            typer.echo(f"CSV summary written to {csv_out}")

        if json_dir:
            json_dir.mkdir(parents=True, exist_ok=True)
            for pdf, result in results:
                out_path = json_dir / f"{pdf.stem}.json"
                out_path.write_text(render_json(result), encoding="utf-8")
            typer.echo(f"Per-file JSON written to {json_dir}")

        if not csv_out and not json_dir:
            for pdf, result in results:
                typer.echo(
                    f"{pdf.name}: {result.classification} "
                    f"(score={result.score}, confidence={result.confidence})"
                )

        raise typer.Exit(code=0)

    if target.suffix.lower() != ".pdf":
        typer.echo(f"Expected a .pdf file, got: {target}", err=True)
        raise typer.Exit(code=64)

    try:
        with PdfInspector.open(target) as inspector:
            result = classify(inspector, target)
    except Exception as exc:
        typer.echo(f"Failed to process {target}: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if fmt.lower() == "json":
        output = render_json(result)
    elif fmt.lower() == "markdown":
        output = render_markdown(result)
    else:
        output = render_text(result)

    typer.echo(output)

    if report:
        report.write_text(output, encoding="utf-8")
        typer.echo(f"\nReport written to {report}")

    raise typer.Exit(code=0)


@app.command()
def signals() -> None:
    """List the supported provenance signals and their weights."""
    from tagorigin.signals.metadata import METADATA_SIGNALS
    from tagorigin.signals.structure import STRUCTURE_SIGNALS

    typer.echo("Metadata signals:")
    for fn in METADATA_SIGNALS:
        sig = fn.__doc__ or fn.__name__
        typer.echo(f"  {fn.__name__}  --  {sig}")

    typer.echo("\nStructure signals:")
    for fn in STRUCTURE_SIGNALS:
        sig = fn.__doc__ or fn.__name__
        typer.echo(f"  {fn.__name__}  --  {sig}")

    raise typer.Exit(code=0)


@app.command()
def test_corpus() -> None:
    """Run against the bundled corpus and print confusion matrix."""
    corpus_dir = Path("tagorigin/corpus")
    expected_path = corpus_dir / "expected.json"
    if not expected_path.exists():
        typer.echo(f"Corpus expected file not found: {expected_path}", err=True)
        raise typer.Exit(code=2)

    with expected_path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    entries = data.get("entries", [])
    if not entries:
        typer.echo("No entries in expected.json", err=True)
        raise typer.Exit(code=2)

    classes = ["UNTAGGED", "AUTO_TAGGED", "LIGHTLY_REMEDIATED", "REMEDIATED", "WELL_REMEDIATED"]
    confusion: dict[str, dict[str, int]] = {c: dict.fromkeys(classes, 0) for c in classes}
    correct = 0
    total = 0

    for entry in entries:
        pdf_path = Path(entry["path"])
        expected = entry["expected"]
        if not pdf_path.exists():
            typer.echo(f"Skip missing file: {pdf_path}", err=True)
            continue
        try:
            with PdfInspector.open(pdf_path) as inspector:
                result = classify(inspector, pdf_path)
        except Exception as exc:
            typer.echo(f"Failed to process {pdf_path}: {exc}", err=True)
            continue
        actual = result.classification
        confusion[expected][actual] += 1
        total += 1
        if actual == expected:
            correct += 1
        else:
            typer.echo(
                f"MISMATCH: {pdf_path.name}: expected {expected}, "
                f"got {actual} (score={result.score})"
            )

    if total == 0:
        typer.echo("No files evaluated.", err=True)
        raise typer.Exit(code=2)

    accuracy = correct / total
    typer.echo(f"\nAccuracy: {correct}/{total} = {accuracy:.1%}")
    typer.echo("\nConfusion matrix (rows = expected, columns = actual):")
    header = "| Expected | " + " | ".join(f"{c:>20}" for c in classes) + " |"
    typer.echo(header)
    typer.echo("|" + "|".join("-" * 22 for _ in range(len(classes) + 1)) + "|")
    for exp in classes:
        row = f"| {exp:>20} |"
        for act in classes:
            count = confusion[exp][act]
            row += f" {count:>20} |"
        typer.echo(row)

    raise typer.Exit(code=0)


if __name__ == "__main__":
    app()
