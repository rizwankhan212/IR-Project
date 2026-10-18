"""Best-effort metadata extraction for research-paper PDFs.

PDF layouts vary, so extracted metadata should be reviewed in the Library tab.
Missing values are left blank rather than guessed.
"""

import re


YEAR_RE = re.compile(r"\b(19\d{2}|20[0-2]\d)\b")


def _clean_line(line):
    return " ".join(line.split()).strip(" \t|")


def _is_noise_line(line):
    return bool(re.search(
        r"@|https?://|www\.|doi\s*:|arxiv\s*:|"
        r"university|department|school of|faculty of|"
        r"copyright|all rights reserved",
        line,
        re.I,
    ))


def _extract_year(text):
    patterns = [
        r"(?:publication\s+year|published(?:\s+online)?|publication\s+date)"
        r"\s*[:\-]?\s*((?:19|20)\d{2})",
        r"copyright\s*(?:©|\(c\))?\s*((?:19|20)\d{2})",
    ]

    for pattern in patterns:
        match = re.search(pattern, text[:15000], re.I)
        if match:
            year_match = YEAR_RE.search(match.group(1))
            if year_match:
                return int(year_match.group(1))

    return None


def _extract_abstract(text):
    match = re.search(
        r"\babstract\b\s*[:.\-]?\s*(.*?)"
        r"(?=\n\s*(?:keywords?|index terms|"
        r"\d+\.?\s+introduction|introduction)\b|\Z)",
        text,
        re.I | re.S,
    )
    if not match:
        return ""

    return " ".join(match.group(1).split())[:4000]


def _extract_keywords(text):
    match = re.search(
        r"\b(?:keywords?|index terms)\b\s*[:\-]\s*(.*?)(?=\n|$)",
        text,
        re.I,
    )
    return _clean_line(match.group(1)) if match else ""


def extract_metadata(full_text):
    """Extract likely title, authors, year, abstract, and keywords."""
    lines = [_clean_line(line) for line in full_text.splitlines()]
    lines = [line for line in lines if line]

    metadata = {
        "title": "Unknown",
        "authors": "Unknown",
        "publication_year": _extract_year(full_text),
        "abstract": _extract_abstract(full_text),
        "keywords": _extract_keywords(full_text),
    }

    if not lines:
        return metadata

    candidates = []
    for line in lines[:15]:
        if (
            15 <= len(line) <= 280
            and not _is_noise_line(line)
            and not re.fullmatch(r"(?:19|20)\d{2}", line)
            and not re.search(r"\babstract\b", line, re.I)
            and len(line.split()) >= 3
        ):
            candidates.append(line)

    if candidates:
        metadata["title"] = max(
            candidates[:6],
            key=lambda line: (
                min(len(line), 180)
                + (12 if line.istitle() else 0)
                - (25 if line.endswith(".") else 0)
            ),
        )

    try:
        title_index = lines.index(metadata["title"])
    except ValueError:
        title_index = -1

    if title_index >= 0:
        for line in lines[title_index + 1:title_index + 5]:
            if (
                3 <= len(line) <= 220
                and re.search(r"[A-Za-z]", line)
                and not _is_noise_line(line)
                and not re.search(
                    r"\b(abstract|keywords?|introduction|received|accepted|"
                    r"published|conference|journal)\b",
                    line,
                    re.I,
                )
                and not YEAR_RE.search(line)
            ):
                metadata["authors"] = line
                break

    return metadata
