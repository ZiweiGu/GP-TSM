import argparse
import os
import re
import threading
import webbrowser
from typing import List

import pdfplumber
from flask import Flask, request

import llm
from app import generate_vl0


app = Flask(__name__)

# Simple in-memory cache to avoid rerunning LLM work on refresh
CACHE = {}


def _extract_paragraphs_from_pages(pdf_path: str, max_pages: int) -> List[List[str]]:
    pages: List[List[str]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_idx, page in enumerate(pdf.pages):
            if page_idx >= max_pages:
                break
            text = page.extract_text() or ""
            lines = [line.strip() for line in text.splitlines()]
            current: List[str] = []
            page_paragraphs: List[str] = []
            for line in lines:
                if not line:
                    if current:
                        page_paragraphs.append(" ".join(current).strip())
                        current = []
                    continue
                # New paragraph when numbering is present (e.g., "1.", "23.")
                if re.match(r"^\d+\.\s+", line):
                    if current:
                        page_paragraphs.append(" ".join(current).strip())
                    current = [line]
                else:
                    current.append(line)
            if current:
                page_paragraphs.append(" ".join(current).strip())
            page_paragraphs = [p for p in page_paragraphs if len(p.split()) > 2]
            pages.append(page_paragraphs)
    return pages


def _render_paragraph(paragraph: str, api_key: str) -> str:
    vl0 = ""
    for d in llm.get_shortened_paragraph(paragraph, api_key, system_message=llm.UK_LAW_SYSTEM_MESSAGE):
        vl0 += generate_vl0(d["0"], d["1"], d["2"], d["3"], d["4"]) + " "
    return vl0.strip()


def _render_pages(pdf_path: str, max_pages: int, api_key: str) -> List[List[str]]:
    pages = _extract_paragraphs_from_pages(pdf_path, max_pages)
    rendered_pages: List[List[str]] = []
    for page_paragraphs in pages:
        rendered_page: List[str] = []
        for paragraph in page_paragraphs:
            rendered_page.append(_render_paragraph(paragraph, api_key))
        rendered_pages.append(rendered_page)
    return rendered_pages


def _build_html(pages: List[List[str]]) -> str:
    blocks = []
    for page_idx, page_paragraphs in enumerate(pages, start=1):
        page_blocks = []
        for rendered in page_paragraphs:
            page_blocks.append(
                f"""
                <div class="para-block">
                  <div class="para-text">{rendered}</div>
                </div>
                """
            )
        blocks.append(
            f"""
            <div class="page-block">
              <div class="page-header">Page {page_idx}</div>
              {''.join(page_blocks)}
            </div>
            """
        )

    return f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8" />
  <title>GP-TSM PDF Render</title>
  <style>
    body {{
      font-family: Arial, sans-serif;
      margin: 24px;
      color: #111;
    }}
    .page-block {{
      margin-bottom: 40px;
      padding-bottom: 16px;
      border-bottom: 1px solid #ddd;
    }}
    .page-header {{
      font-weight: 700;
      margin-bottom: 12px;
      font-size: 18px;
    }}
    .para-block {{
      margin-bottom: 20px;
    }}
    .para-text {{
      font-size: 16px;
      line-height: 1.6;
      white-space: normal;
      word-wrap: break-word;
    }}
  </style>
</head>
<body>
  {''.join(blocks)}
</body>
</html>
"""


@app.route("/")
def index():
    max_pages = int(request.args.get("pages", app.config["MAX_PAGES"]))
    cache_key = (app.config["PDF_PATH"], max_pages)
    if cache_key not in CACHE:
        CACHE[cache_key] = _render_pages(
            app.config["PDF_PATH"],
            max_pages,
            app.config["API_KEY"],
        )
    return _build_html(CACHE[cache_key])


def main() -> None:
    default_pdf = os.path.join(
        os.path.dirname(__file__),
        "legal documents",
        "uk_legal_doc_1.pdf",
    )
    parser = argparse.ArgumentParser(description="Render first X PDF pages in a local web app.")
    parser.add_argument("--pdf", default=default_pdf, help="Path to the input PDF.")
    parser.add_argument("--pages", type=int, default=29, help="Number of pages to render.")
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENAI_API_KEY", ""),
        help="OpenAI API key (or set OPENAI_API_KEY).",
    )
    parser.add_argument("--port", type=int, default=5050, help="Local port for the server.")
    args = parser.parse_args()

    if not args.api_key:
        raise ValueError("OpenAI API key is required (use --api-key or OPENAI_API_KEY).")

    app.config["PDF_PATH"] = args.pdf
    app.config["MAX_PAGES"] = args.pages
    app.config["API_KEY"] = args.api_key

    url = f"http://127.0.0.1:{args.port}/?pages={args.pages}"
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(debug=True, port=args.port, host="127.0.0.1")


if __name__ == "__main__":
    main()
