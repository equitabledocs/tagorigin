"""tagorigin FastAPI backend.

POST /audit              accepts a PDF upload, returns JSON ProvenanceResult
POST /audit/html         accepts a PDF upload, returns an HTML report
GET  /                   serves the landing page
GET  /static/{file}      serves static assets

Run with: uvicorn tagorigin.api:app --reload
"""
from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response

from tagorigin.classify import classify
from tagorigin.inspect import PdfInspector
from tagorigin.report import render_markdown

app = FastAPI(
    title="tagorigin",
    description=(
        "Classify a PDF's tag-tree provenance. Distinguishes "
        "authoring-tool autotag from deliberate accessibility remediation."
    ),
    version="0.1.0",
)

# Cap upload size at 50 MB; refuse anything larger
MAX_UPLOAD_BYTES = 50 * 1024 * 1024

# Paths to bundled static assets
PACKAGE_ROOT = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_ROOT / "static"


def _classify_uploaded_pdf(file: UploadFile) -> dict:
    """Save the upload to a temp file, classify, return JSON-able dict."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Upload must be a .pdf file")

    contents = file.file.read()
    if len(contents) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Limit is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
        )

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(contents)
        tmp_path = Path(tmp.name)

    try:
        with PdfInspector.open(tmp_path) as inspector:
            result = classify(inspector, tmp_path)
        return result.model_dump()
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


@app.get("/", response_class=HTMLResponse)
def landing_page() -> str:
    """Serve the landing page."""
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<h1>tagorigin</h1><p>Landing page not built yet.</p>"


@app.get("/static/{filename}")
def static_asset(filename: str) -> Response:
    """Serve a static asset (CSS, etc)."""
    safe = Path(filename).name
    asset = STATIC_DIR / safe
    if not asset.exists() or not asset.is_file():
        raise HTTPException(status_code=404, detail="Not found")
    media_type = "text/css" if safe.endswith(".css") else "application/octet-stream"
    return Response(content=asset.read_bytes(), media_type=media_type)


@app.post("/audit")
def audit_json(pdf: UploadFile = File(...)) -> JSONResponse:
    """Classify an uploaded PDF and return the ProvenanceResult as JSON."""
    result = _classify_uploaded_pdf(pdf)
    return JSONResponse(content=result)


@app.post("/audit/html", response_class=HTMLResponse)
def audit_html(pdf: UploadFile = File(...)) -> str:
    """Classify an uploaded PDF and return a rendered HTML report."""
    result_dict = _classify_uploaded_pdf(pdf)
    from tagorigin.models import ProvenanceResult
    result = ProvenanceResult.model_validate(result_dict)
    md = render_markdown(result)
    # Wrap markdown in a minimal HTML shell. Anyone using this in a real
    # deployment can substitute a markdown-to-HTML renderer for richer output.
    css_path = STATIC_DIR / "result.css"
    css = css_path.read_text(encoding="utf-8") if css_path.exists() else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>tagorigin report: {result.classification}</title>
<style>{css}</style>
</head>
<body>
<main>
<h1>tagorigin provenance report</h1>
<p><a href="/">Audit another PDF</a></p>
<pre>{md}</pre>
</main>
</body>
</html>"""
