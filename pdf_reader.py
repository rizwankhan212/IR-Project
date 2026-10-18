"""PDF text extraction and page-level matching utilities."""

import fitz

from text_processor import preprocess_text


def extract_text(pdf_path):
    """Extract selectable text from each PDF page."""
    pages = []

    with fitz.open(pdf_path) as pdf:
        for page_number, page in enumerate(pdf, start=1):
            text = page.get_text("text").strip()
            if text:
                pages.append({"page": page_number, "text": text})

    return pages


def get_full_text(pages):
    """Combine extracted page text into one document string."""
    return "\n".join(page.get("text", "") for page in pages)


def find_matching_pages(pages, query, match_all=False):
    """Return page numbers containing query terms.

    By default, a page matches when it contains at least one query term.
    Set match_all=True to require every processed query term on the page.
    """
    query_terms = set(preprocess_text(query))
    if not query_terms:
        return []

    matching_pages = []

    for page in pages or []:
        page_terms = set(preprocess_text(page.get("text", "")))
        if match_all:
            matches = query_terms.issubset(page_terms)
        else:
            matches = bool(query_terms.intersection(page_terms))

        if matches and page.get("page") is not None:
            matching_pages.append(page["page"])

    return matching_pages
