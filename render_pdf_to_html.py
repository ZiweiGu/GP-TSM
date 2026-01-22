import argparse
import os
import re
from typing import List, Tuple

import pdfplumber

import llm
from app import generate_vl0


def _extract_paragraphs_from_pdf(pdf_path: str) -> List[List[str]]:
    pages: List[List[str]] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
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
                if re.match(r"^\d+\.\s+", line):
                    if current:
                        page_paragraphs.append(" ".join(current).strip())
                    current = [line]
                else:
                    current.append(line)
            if current:
                page_paragraphs.append(" ".join(current).strip())
            # Filter out tiny fragments
            page_paragraphs = [p for p in page_paragraphs if len(p.split()) > 2]
            pages.append(page_paragraphs)
    return pages


def _render_paragraph(paragraph: str, api_key: str, system_message: str) -> Tuple[str, str]:
    l0 = ""
    vl0 = ""
    for d in llm.get_shortened_paragraph(paragraph, api_key, system_message=system_message):
        l0 += d["0"] + " "
        vl0 += generate_vl0(d["0"], d["1"], d["2"], d["3"], d["4"]) + " "
    return l0.strip(), vl0.strip()


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
    .para-block {{
      margin-bottom: 24px;
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a PDF to HTML using GP-TSM saliency.")
    parser.add_argument("--pdf", required=True, help="Path to the input PDF.")
    parser.add_argument("--out", required=True, help="Path to the output HTML file.")
    parser.add_argument(
        "--api-key",
        default=os.getenv("OPENAI_API_KEY", ""),
        help="OpenAI API key (or set OPENAI_API_KEY).",
    )
    parser.add_argument(
        "--system-message",
        default=llm.UK_LAW_SYSTEM_MESSAGE,
        help="System message to use for the shortener.",
    )
    args = parser.parse_args()

    if not args.api_key:
        raise ValueError("OpenAI API key is required (use --api-key or OPENAI_API_KEY).")

    pages = _extract_paragraphs_from_pdf(args.pdf)
    rendered_pages: List[List[str]] = []
    for page_paragraphs in pages:
        rendered_page: List[str] = []
        for paragraph in page_paragraphs:
            _, rendered = _render_paragraph(paragraph, args.api_key, args.system_message)
            rendered_page.append(rendered)
        rendered_pages.append(rendered_page)

    html = _build_html(rendered_pages)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(html)


if __name__ == "__main__":
    main()
