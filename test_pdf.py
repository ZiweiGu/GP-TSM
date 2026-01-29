import argparse
import os
import re
import threading
import time
import webbrowser
from typing import List

import pdfplumber
from flask import Flask, request

import llm
from app import generate_vl0


app = Flask(__name__)

# Simple in-memory cache to avoid rerunning LLM work on refresh
CACHE = {}
SKIP_PAGES = 0
PAGE_NUMBER_PATTERN = re.compile(r"^Page\s+\d+(?:\s+of\s+\d+)?$", re.IGNORECASE)
FOOTNOTE_LINE_MIN_RATIO = 0.1
FOOTNOTE_LINE_MAX_RATIO = 0.4
FOOTNOTE_BOTTOM_RATIO = 0.7
LINE_MERGE_TOLERANCE = 3.0


def _clean_line(line: str) -> str:
    return line.replace("\u00a0", " ").strip()


def _strip_leading_noise(line: str) -> str:
    return re.sub(r"^[^A-Za-z0-9]+", "", line)


def _strip_margin_annotations(line: str) -> str:
    # Remove lines that are purely margin annotations.
    if re.match(r"^\s*Tab\s+\d+\s*,?\s*$", line, flags=re.IGNORECASE):
        return ""
    if re.match(r"^\s*pp?\.?\s*\d*(?:\s*-\s*\d+)?\s*;?\s*$", line, flags=re.IGNORECASE):
        return ""
    if re.match(r"^\s*\d+\s*-\s*\d+\s*$", line):
        return ""

    # Strip inline annotation fragments but preserve body text.
    line = re.sub(r"\bTab\s+\d+\s*,?\s*", "", line, flags=re.IGNORECASE)
    line = re.sub(r"\bpp?\.?\s*\d*(?:\s*-\s*\d+)?\b", "", line, flags=re.IGNORECASE)
    line = re.sub(r"\bpp?\.?\s*;", "", line, flags=re.IGNORECASE)
    line = re.sub(r"\s{2,}", " ", line)
    return line.strip(" ,;")


def _strip_trailing_page_number(line: str) -> str:
    return re.sub(r"[\s.]+\d{1,3}$", "", line).rstrip()


def _strip_trailing_number_after_punct(paragraph: str) -> str:
    return re.sub(r"([.!?])\s+\d{1,3}$", r"\1", paragraph).rstrip()


def _looks_like_name_list(lines: List[str]) -> bool:
    non_empty = [line for line in lines if line.strip()]
    if len(non_empty) < 6:
        return False
    word_counts = [len(line.split()) for line in non_empty]
    short_ratio = sum(1 for count in word_counts if count <= 3) / len(word_counts)
    return short_ratio >= 0.6


def _find_footnote_cutoff(page) -> float:
    if not getattr(page, "lines", None):
        return None
    page_width = page.width
    page_height = page.height
    cutoff_candidates = []
    for line in page.lines:
        x0 = line.get("x0")
        x1 = line.get("x1")
        top = line.get("top")
        bottom = line.get("bottom", top)
        if x0 is None or x1 is None or top is None:
            continue
        if abs((bottom or top) - top) > 2:
            continue
        line_width = abs(x1 - x0)
        width_ratio = line_width / page_width if page_width else 0
        if width_ratio < FOOTNOTE_LINE_MIN_RATIO or width_ratio > FOOTNOTE_LINE_MAX_RATIO:
            continue
        if top < page_height * FOOTNOTE_BOTTOM_RATIO:
            continue
        cutoff_candidates.append(top)
    if cutoff_candidates:
        return min(cutoff_candidates)
    return None


def _extract_lines_from_page(page) -> List[str]:
    words = page.extract_words(use_text_flow=True, keep_blank_chars=False)
    cutoff = _find_footnote_cutoff(page)
    if words:
        filtered = []
        for word in words:
            text = _clean_line(word.get("text", ""))
            if not text:
                continue
            if cutoff is not None and word["top"] >= cutoff:
                continue
            filtered.append(word)

        filtered.sort(key=lambda w: (w["top"], w["x0"]))
        lines = []
        current_line = []
        current_top = None
        for word in filtered:
            if current_top is None or abs(word["top"] - current_top) <= LINE_MERGE_TOLERANCE:
                current_line.append(word)
                if current_top is None:
                    current_top = word["top"]
            else:
                lines.append(current_line)
                current_line = [word]
                current_top = word["top"]
        if current_line:
            lines.append(current_line)

        rendered_lines = []
        for line_words in lines:
            line_words.sort(key=lambda w: w["x0"])
            line_text = " ".join(_clean_line(w["text"]) for w in line_words).strip()
            if not line_text:
                rendered_lines.append(line_text)
                continue
            if PAGE_NUMBER_PATTERN.match(line_text):
                continue
            rendered_lines.append(line_text)
        return rendered_lines

    text = page.extract_text() or ""
    lines = [_clean_line(line) for line in text.splitlines()]
    filtered_lines = []
    for line in lines:
        if not line:
            filtered_lines.append(line)
            continue
        if PAGE_NUMBER_PATTERN.match(line):
            continue
        filtered_lines.append(line)
    return filtered_lines


def _extract_paragraphs_from_pages(pdf_path: str, max_pages: int) -> List[str]:
    paragraphs: List[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        if max_pages <= 0:
            max_pages = len(pdf.pages)
        current: List[str] = []
        started = False
        for page_idx, page in enumerate(pdf.pages):
            if page_idx >= max_pages:
                break
            if page_idx < SKIP_PAGES:
                continue
            lines = _extract_lines_from_page(page)
            if started and _looks_like_name_list(lines):
                break
            for line in lines:
                if not line:
                    if current:
                        paragraph = " ".join(current).strip()
                        paragraphs.append(_strip_trailing_number_after_punct(paragraph))
                        current = []
                    continue
                if PAGE_NUMBER_PATTERN.match(line):
                    continue
                line = _strip_trailing_page_number(_strip_margin_annotations(line))
                if not line:
                    continue
                normalized = _strip_leading_noise(line)
                if not started:
                    numbered_start = re.search(r"\b1\s*(?:[.\)]\s*|\s+|$)", normalized)
                    if numbered_start:
                        line = line[numbered_start.start():].strip()
                        started = True
                        if current:
                            paragraphs.append(" ".join(current).strip())
                        current = [line]
                        continue
                    # Only start once we see a numbered paragraph.
                    continue
                if not started and re.match(r"^1\s*(?:[.\)]\s*|\s+|$)", normalized):
                    started = True
                    if current:
                        paragraph = " ".join(current).strip()
                        paragraphs.append(_strip_trailing_number_after_punct(paragraph))
                    current = [line]
                elif re.match(r"^\d+\s*(?:[.\)]\s*|$)", normalized):
                    started = True
                    if current:
                        paragraphs.append(" ".join(current).strip())
                    current = [line]
                else:
                    if not started:
                        continue
                    current.append(line)
        if current:
            paragraph = " ".join(current).strip()
            paragraphs.append(_strip_trailing_number_after_punct(paragraph))
    paragraphs = [_strip_trailing_number_after_punct(p) for p in paragraphs if len(p.split()) > 2]
    return paragraphs


def _render_paragraph(paragraph: str, api_key: str) -> str:
    vl0 = ""
    for d in llm.get_shortened_paragraph(paragraph, api_key, system_message=llm.UK_LAW_SYSTEM_MESSAGE):
        vl0 += generate_vl0(d["0"], d["1"], d["2"], d["3"], d["4"]) + " "
    return vl0.strip()


def _render_paragraphs(pdf_path: str, max_pages: int, api_key: str) -> List[str]:
    paragraphs = _extract_paragraphs_from_pages(pdf_path, max_pages)
    rendered_paragraphs: List[str] = []
    for paragraph in paragraphs:
        rendered_paragraphs.append(_render_paragraph(paragraph, api_key))
    return rendered_paragraphs


def _build_html(paragraphs: List[str]) -> str:
    blocks = []
    for rendered in paragraphs:
        blocks.append(
            f"""
            <div class="para-block">
              <div class="para-text">{rendered}</div>
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
    .content {{
      max-width: 820px;
      margin: 0 auto;
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
  <div class="content">
    {''.join(blocks)}
  </div>
</body>
</html>
"""


@app.route("/")
def index():
    max_pages = int(request.args.get("pages", app.config["MAX_PAGES"]))
    cache_key = (app.config["PDF_PATH"], max_pages)
    if cache_key not in CACHE:
        start_time = time.perf_counter()
        CACHE[cache_key] = _render_paragraphs(
            app.config["PDF_PATH"],
            max_pages,
            app.config["API_KEY"],
        )
        elapsed = time.perf_counter() - start_time
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        print(f"{minutes} minute, {seconds} second")
    return _build_html(CACHE[cache_key])


def main() -> None:
    global SKIP_PAGES
    default_pdf = os.path.join(
        os.path.dirname(__file__),
        "legal documents",
        "uk_legal_doc_1.pdf",
    )
    parser = argparse.ArgumentParser(description="Render first X PDF pages in a local web app.")
    parser.add_argument("--pdf", default=default_pdf, help="Path to the input PDF.")
    parser.add_argument(
        "--pages",
        type=int,
        default=0,
        help="Number of pages to render (0 = all pages).",
    )
    parser.add_argument(
        "--skip-pages",
        type=int,
        default=SKIP_PAGES,
        help="Number of pages to skip from the start.",
    )
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
    SKIP_PAGES = args.skip_pages

    url = f"http://127.0.0.1:{args.port}/?pages={args.pages}"
    threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(debug=True, use_reloader=False, port=args.port, host="127.0.0.1")


if __name__ == "__main__":
    main()
