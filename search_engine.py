"""Ranking-based search methods for ResearchSphere."""

import math
from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from text_processor import preprocess_text


def get_document_text(paper):
    """Combine important metadata and paper text for retrieval."""
    fields = [
        paper.get("title") or "",
        paper.get("authors") or "",
        paper.get("keywords") or "",
        paper.get("abstract") or "",
        paper.get("full_text") or "",
    ]
    return " ".join(str(field) for field in fields if field).strip()


def search_papers(query, papers):
    """Rank papers using TF-IDF vectors and cosine similarity."""
    if not query or not query.strip() or not papers:
        return []

    documents = [get_document_text(paper) for paper in papers]
    if not any(document.strip() for document in documents):
        return []

    vectorizer = TfidfVectorizer(
        lowercase=True,
        stop_words="english",
        ngram_range=(1, 2),
        sublinear_tf=True,
    )

    try:
        document_vectors = vectorizer.fit_transform(documents)
        query_vector = vectorizer.transform([query])
    except ValueError:
        # For example, the collection may contain only stop words.
        return []

    scores = cosine_similarity(query_vector, document_vectors).ravel()
    results = []

    for paper, score in zip(papers, scores):
        if score > 0:
            result = paper.copy()
            result["score"] = round(float(score), 6)
            results.append(result)

    return sorted(results, key=lambda item: item["score"], reverse=True)


def search_bm25(query, papers, k1=1.5, b=0.75):
    """Rank papers with the Okapi BM25 scoring formula."""
    if not query or not query.strip() or not papers:
        return []
    if k1 <= 0 or not 0 <= b <= 1:
        raise ValueError("BM25 requires k1 > 0 and b between 0 and 1.")

    documents = [
        preprocess_text(get_document_text(paper)) for paper in papers
    ]
    query_terms = set(preprocess_text(query))

    if not query_terms:
        return []

    document_lengths = [len(document) for document in documents]
    total_documents = len(documents)
    average_length = sum(document_lengths) / total_documents

    if average_length == 0:
        return []

    document_frequency = Counter()
    for document in documents:
        document_frequency.update(set(document))

    results = []

    for paper, document, length in zip(papers, documents, document_lengths):
        term_counts = Counter(document)
        score = 0.0

        for term in query_terms:
            term_frequency = term_counts[term]
            if term_frequency == 0:
                continue

            frequency = document_frequency[term]
            inverse_document_frequency = math.log(
                1 + (total_documents - frequency + 0.5) / (frequency + 0.5)
            )
            length_normalizer = k1 * (
                1 - b + b * length / average_length
            )
            denominator = term_frequency + length_normalizer

            score += inverse_document_frequency * (
                term_frequency * (k1 + 1) / denominator
            )

        if score > 0:
            result = paper.copy()
            result["score"] = round(float(score), 6)
            results.append(result)

    return sorted(results, key=lambda item: item["score"], reverse=True)
