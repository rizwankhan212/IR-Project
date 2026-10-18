"""Evaluation metrics for ResearchSphere retrieval methods."""

from search_engine import search_papers, search_bm25


def precision_at_k(results, relevant_ids, k=5):
    """Return relevant results in the first K positions divided by K."""
    if k <= 0:
        return 0.0

    relevant_ids = set(relevant_ids)
    top_results = results[:k]
    hits = sum(1 for paper in top_results if paper.get("id") in relevant_ids)
    return round(hits / k, 4)


def recall_at_k(results, relevant_ids, k=5):
    """Return the fraction of known relevant papers retrieved in top K."""
    relevant_ids = set(relevant_ids)
    if k <= 0 or not relevant_ids:
        return 0.0

    hits = sum(
        1 for paper in results[:k] if paper.get("id") in relevant_ids
    )
    return round(hits / len(relevant_ids), 4)


def f1_at_k(precision, recall):
    """Calculate F1 from Precision@K and Recall@K."""
    if precision + recall == 0:
        return 0.0
    return round(2 * precision * recall / (precision + recall), 4)


def average_precision_at_k(results, relevant_ids, k=5):
    """Calculate AP@K, using the total known relevant set as denominator."""
    relevant_ids = set(relevant_ids)
    if k <= 0 or not relevant_ids:
        return 0.0

    hits = 0
    precision_sum = 0.0

    for rank, paper in enumerate(results[:k], start=1):
        if paper.get("id") in relevant_ids:
            hits += 1
            precision_sum += hits / rank

    return round(precision_sum / len(relevant_ids), 4)


def evaluate_query(query, papers, relevant_ids, k=5):
    """Evaluate TF-IDF and BM25 while preserving the app.py interface."""
    relevant_ids = set(relevant_ids)
    tfidf_results = search_papers(query, papers)
    bm25_results = search_bm25(query, papers)

    tfidf_precision = precision_at_k(tfidf_results, relevant_ids, k)
    bm25_precision = precision_at_k(bm25_results, relevant_ids, k)
    tfidf_recall = recall_at_k(tfidf_results, relevant_ids, k)
    bm25_recall = recall_at_k(bm25_results, relevant_ids, k)

    return {
        "query": query,
        "k": k,
        "relevant_ids": sorted(relevant_ids),
        "tfidf_precision": tfidf_precision,
        "bm25_precision": bm25_precision,
        "tfidf_recall": tfidf_recall,
        "bm25_recall": bm25_recall,
        "tfidf_f1": f1_at_k(tfidf_precision, tfidf_recall),
        "bm25_f1": f1_at_k(bm25_precision, bm25_recall),
        "tfidf_ap": average_precision_at_k(tfidf_results, relevant_ids, k),
        "bm25_ap": average_precision_at_k(bm25_results, relevant_ids, k),
        "tfidf_results": tfidf_results[:k],
        "bm25_results": bm25_results[:k],
    }
