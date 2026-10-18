"""TF-IDF and K-Means based document clustering for ResearchSphere."""

from collections import Counter

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer


def build_paper_text(paper):
    """Combine useful textual fields, preferring full paper text when available."""
    fields = [
        paper.get("title") or "",
        paper.get("abstract") or "",
        paper.get("keywords") or "",
        paper.get("full_text") or "",
    ]
    return " ".join(str(value) for value in fields if str(value).strip())


def cluster_papers(papers, n_clusters=4, max_features=5000, top_terms=8):
    """Cluster papers and return display-ready rows, keywords, and 2D coordinates.

    Raises ValueError with a user-readable message if there is insufficient or
    unusable text. Cluster IDs are displayed from 1 rather than 0.
    """
    usable = []
    texts = []
    for paper in papers:
        text = build_paper_text(paper).strip()
        if text:
            usable.append(paper)
            texts.append(text)

    if len(usable) < 2:
        raise ValueError("At least two papers with extracted text are required.")
    if n_clusters < 2 or n_clusters > len(usable):
        raise ValueError(f"Choose between 2 and {len(usable)} clusters.")

    vectorizer = TfidfVectorizer(
        stop_words="english",
        max_features=max_features,
        min_df=1,
        max_df=1.0,
        sublinear_tf=True,
    )
    try:
        matrix = vectorizer.fit_transform(texts)
    except ValueError as exc:
        raise ValueError(
            "The imported papers do not contain enough usable text to create clusters."
        ) from exc

    if matrix.shape[1] == 0:
        raise ValueError("No useful terms were found in the imported papers.")

    model = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = model.fit_predict(matrix)
    terms = vectorizer.get_feature_names_out()

    cluster_keywords = {}
    for cluster_id in range(n_clusters):
        center = model.cluster_centers_[cluster_id]
        best_indices = np.argsort(center)[::-1]
        cluster_keywords[cluster_id + 1] = [
            str(terms[index])
            for index in best_indices
            if center[index] > 0
        ][:top_terms]

    # PCA is used only for the optional 2D visualisation, not for clustering.
    if matrix.shape[1] >= 2 and len(usable) >= 3:
        coords = PCA(n_components=2, random_state=42).fit_transform(matrix.toarray())
    else:
        coords = np.column_stack((np.arange(len(usable)), np.zeros(len(usable))))

    rows = []
    for index, (paper, label) in enumerate(zip(usable, labels)):
        cluster_id = int(label) + 1
        rows.append({
            "Paper ID": paper.get("id"),
            "Title": paper.get("title") or "Untitled paper",
            "Authors": paper.get("authors") or "",
            "Year": paper.get("publication_year"),
            "Cluster": cluster_id,
            "Cluster keywords": ", ".join(cluster_keywords[cluster_id]) or "No clear keywords",
            "x": float(coords[index, 0]),
            "y": float(coords[index, 1]),
        })

    counts = dict(Counter(row["Cluster"] for row in rows))
    for cluster_id in range(1, n_clusters + 1):
        counts.setdefault(cluster_id, 0)

    return {
        "rows": rows,
        "keywords": cluster_keywords,
        "counts": counts,
        "n_clusters": n_clusters,
        "usable_count": len(usable),
        "skipped_count": len(papers) - len(usable),
    }
