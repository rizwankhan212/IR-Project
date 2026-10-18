"""Utilities for inspecting Information Retrieval behavior."""

from collections import Counter

from search_engine import get_document_text
from text_processor import preprocess_text


def analyze_query(query, papers):
    """Summarize query terms and their distribution across the collection."""
    query_terms = preprocess_text(query)
    document_terms = {
        paper["id"]: preprocess_text(get_document_text(paper))
        for paper in papers
    }

    term_statistics = []
    for term in dict.fromkeys(query_terms):
        document_frequency = sum(
            1 for terms in document_terms.values() if term in set(terms)
        )
        total_occurrences = sum(terms.count(term) for terms in document_terms.values())

        term_statistics.append({
            "Term": term,
            "Document Frequency": document_frequency,
            "Total Occurrences": total_occurrences,
        })

    return {
        "query_terms": query_terms,
        "term_statistics": term_statistics,
        "document_count": len(papers),
    }


def get_term_postings(term, papers):
    """Return documents containing a term and its frequency in each document."""
    normalized_terms = preprocess_text(term)
    if not normalized_terms:
        return []

    normalized_term = normalized_terms[0]
    postings = []

    for paper in papers:
        terms = preprocess_text(get_document_text(paper))
        frequency = Counter(terms)[normalized_term]

        if frequency:
            postings.append({
                "paper_id": paper["id"],
                "title": paper.get("title") or "Untitled paper",
                "term_frequency": frequency,
            })

    return sorted(
        postings,
        key=lambda item: (-item["term_frequency"], item["paper_id"])
    )
