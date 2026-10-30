import html
import json
import re
from pathlib import Path

import streamlit as st

from database import (
    create_table,
    get_all_papers,
    save_paper,
    update_paper_metadata,
)
from evaluation import evaluate_query
from inverted_index import (
    build_inverted_index,
    search_and,
    search_or,
    search_boolean_query,
    build_positional_index,
    search_phrase,
)
from ir_analysis import analyze_query, get_term_postings
from metadata_extractor import extract_metadata
from pdf_reader import extract_text, find_matching_pages, get_full_text
from search_engine import search_bm25, search_papers
from search_history import initialize_history, save_search, get_search_history, clear_search_history
from document_clustering import cluster_papers
from cloud_manager import (
    get_cloud_status,
    delete_all_running_instances,
    destroy_all_resources,
    scale_up_instances,
    DEFAULT_REGION,
    DEFAULT_PROJECT,
    DEFAULT_ASG,
)



st.set_page_config(page_title="ResearchSphere | Research Discovery", layout="wide")
PAPERS_DIR = Path("papers")
PAPERS_DIR.mkdir(parents=True, exist_ok=True)
create_table()
initialize_history()

st.markdown("""
<style>
    .block-container {max-width: 1180px; padding-top: 2rem; padding-bottom: 3rem;}
    h1, h2, h3 {letter-spacing: -0.035em;}
    div[data-testid="stMetric"] {background: #f6f8fb; border: 1px solid #e7ebf0;
        border-radius: 12px; padding: 14px 18px;}
    div[data-testid="stVerticalBlockBorderWrapper"] {border-radius: 12px;}
    [data-testid="stSidebar"] {border-right: 1px solid #e7ebf0;}
    .muted {color: #657387; font-size: 0.9rem;}
</style>
""", unsafe_allow_html=True)


def paper_pages(paper):
    try:
        pages = json.loads(paper.get("pages_json") or "[]")
        return pages if isinstance(pages, list) else []
    except (TypeError, ValueError):
        return []


def search_collection(query, method, papers):
    if method == "TF-IDF":
        return search_papers(query, papers)
    if method == "BM25":
        return search_bm25(query, papers)

    documents = {
        paper["id"]: " ".join([
            paper.get("title") or "",
            paper.get("abstract") or "",
            paper.get("keywords") or "",
            paper.get("full_text") or "",
        ])
        for paper in papers
    }
    index = build_inverted_index(documents)
    if method == "Boolean AND":
        ids = search_and(index, query)
    elif method == "Boolean OR":
        ids = search_or(index, query)
    elif method == "Boolean Query":
        ids = search_boolean_query(index, query, documents.keys())
    else:
        positional_index = build_positional_index(documents)
        ids = search_phrase(positional_index, query)
    lookup = {paper["id"]: paper for paper in papers}
    return [lookup[paper_id] for paper_id in ids if paper_id in lookup]


def snippet_for(paper, query, limit=330):
    """Build a short excerpt around a query term."""
    text = paper.get("abstract") or paper.get("full_text") or ""
    if not text:
        return "No text preview available."

    terms = [
        term for term in re.findall(r"[a-zA-Z0-9]+", query)
        if len(term) > 1
    ]
    positions = [
        match.start()
        for term in terms
        for match in re.finditer(r"\b" + re.escape(term) + r"\b", text, re.I)
    ]
    start = max(0, min(positions) - 70) if positions else 0
    excerpt = text[start:start + limit].replace("\n", " ").strip()
    return ("..." if start else "") + excerpt + (
        "..." if start + limit < len(text) else ""
    )


def highlighted_snippet(paper, query, limit=330):
    """Highlight query terms in a safely escaped search-result excerpt."""
    excerpt = html.escape(snippet_for(paper, query, limit))
    terms = sorted(
        {
            term for term in re.findall(r"[a-zA-Z0-9]+", query)
            if len(term) > 1
        },
        key=len,
        reverse=True,
    )

    for term in terms:
        pattern = re.compile(r"\b(" + re.escape(term) + r")\b", re.I)
        excerpt = pattern.sub(
            r'<mark style="background:#fff0b3;padding:0 2px;">\1</mark>',
            excerpt,
        )

    return excerpt

def paper_label(paper):
    return f"{paper['id']} | {paper.get('title') or 'Untitled paper'}"


papers = get_all_papers()
by_id = {paper["id"]: paper for paper in papers}

with st.sidebar:
    st.title("ResearchSphere")
    st.caption("Research discovery workspace")
    st.divider()
    section = st.radio(
        "Workspace",
        ["Discover", "Library", "Search History", "Index Explorer", "Ranking Comparison", "Document Clustering", "Evaluation", "IR Analysis", "Cloud Management"],
        label_visibility="collapsed",
        key="workspace",
    )
    st.divider()
    st.subheader("Add research papers")
    uploaded_files = st.file_uploader(
        "Upload PDF documents", type=["pdf"], accept_multiple_files=True
    )
    if st.button("Import papers", use_container_width=True):
        if not uploaded_files:
            st.warning("Choose one or more PDF files first.")
        else:
            existing_names = {paper["file_name"] for paper in papers}
            imported = 0
            for uploaded in uploaded_files:
                name = Path(uploaded.name).name
                if name in existing_names:
                    st.info(f"Already imported: {name}")
                    continue
                path = PAPERS_DIR / name
                try:
                    # Extract before writing, so invalid files are not stored.
                    pdf_bytes = uploaded.getvalue()
                    if not pdf_bytes.startswith(b"%PDF-"):
                        st.warning(f"Not a valid PDF: {name}")
                        continue
                    path.write_bytes(pdf_bytes)
                    pages = extract_text(path)
                    full_text = get_full_text(pages)
                    if not full_text.strip():
                        path.unlink(missing_ok=True)
                        st.warning(f"No selectable text in {name}.")
                        continue
                    metadata = extract_metadata(full_text)
                    if save_paper(metadata, name, path, full_text, pages=pages):
                        imported += 1
                        existing_names.add(name)
                    else:
                        st.info(f"Skipped duplicate: {name}")
                except Exception as exc:
                    path.unlink(missing_ok=True)
                    st.error(f"Failed to import {name}: {exc}")
            if imported:
                st.success(f"Imported {imported} paper(s).")
                st.rerun()
    st.divider()
    st.caption("Local SQLite storage · PDF text extraction")

if section == "Discover":
    st.title("Discover research")
    if st.session_state.get("repeat_search_notice"):
        st.info(st.session_state.pop("repeat_search_notice"))
    st.write("Search your research library using classical information retrieval methods.")
    st.caption("Boolean Query supports AND, OR, NOT, parentheses, and implicit AND between adjacent terms.")
    m1, m2, m3 = st.columns(3)
    m1.metric("Indexed papers", len(papers))
    m2.metric("Search methods", 5)
    m3.metric("PDFs with page data", sum(bool(paper_pages(p)) for p in papers))
    st.divider()

    with st.form("search_form"):
        query = st.text_input("Search papers", placeholder="Enter a research topic or keywords")
        c1, c2, c3 = st.columns([2, 1, 1])
        method = c1.selectbox("Retrieval method", ["BM25", "TF-IDF", "Boolean Query", "Boolean AND", "Boolean OR", "Exact Phrase"])
        year_options = sorted({p["publication_year"] for p in papers if p.get("publication_year")})
        year = c2.selectbox("Publication year", ["All years"] + year_options)
        limit = c3.selectbox("Show top", [5, 10, 20, 50])
        submitted = st.form_submit_button("Search library", type="primary")

    if submitted:
        if not query.strip():
            st.warning("Enter a search query.")
        elif not papers:
            st.info("Import PDFs from the sidebar to start searching.")
        else:
            st.session_state["last_search"] = (query, method, year, limit)
            eligible_count = sum(
                1 for paper in papers
                if year == "All years" or paper.get("publication_year") == year
            )
            save_search(query, method, year, limit, eligible_count)

    if "last_search" in st.session_state:
        saved_query, saved_method, saved_year, saved_limit = st.session_state["last_search"]
        eligible = [p for p in papers if saved_year == "All years" or p.get("publication_year") == saved_year]
        results = search_collection(saved_query, saved_method, eligible)
        st.subheader(f"Results ({len(results)})")
        st.caption(f"Method: {saved_method} | Query: {saved_query}")
        if not results:
            st.info("No matching papers found. Try a broader query or a different retrieval method.")
        for rank, paper in enumerate(results[:saved_limit], start=1):
            with st.container(border=True):
                st.markdown(f"#### {rank}. {paper.get('title') or 'Untitled paper'}")
                st.caption(f"{paper.get('authors') or 'Unknown authors'}  |  "
                           f"{paper.get('publication_year') or 'Year unavailable'}  |  ID {paper['id']}")
                st.markdown(highlighted_snippet(paper, saved_query), unsafe_allow_html=True)
                if paper.get("keywords"):
                    st.caption(f"Keywords: {paper['keywords']}")
                matching = find_matching_pages(paper_pages(paper), saved_query)
                details = []
                if "score" in paper:
                    details.append(f"Relevance score: {paper['score']:.4f}")
                if matching:
                    preview = ", ".join(str(n) for n in matching[:8])
                    details.append(f"Matching pages: {preview}" + (" ..." if len(matching) > 8 else ""))
                if details:
                    st.caption(" | ".join(details))
    elif not papers:
        st.info("Your library is empty. Upload a PDF to get started.")

elif section == "Library":
    st.title("Research library")
    st.caption("Review and correct automatically extracted metadata.")
    if not papers:
        st.info("No papers have been imported yet.")
    else:
        st.write(f"{len(papers)} papers in your collection")
        for paper in papers:
            with st.expander(paper_label(paper)):
                st.caption(f"File: {paper.get('file_name', '')}")
                with st.form(f"metadata_{paper['id']}"):
                    title = st.text_input("Title", value=paper.get("title") or "")
                    authors = st.text_input("Authors", value=paper.get("authors") or "")
                    current_year = paper.get("publication_year")
                    year_text = st.text_input("Publication year", value=str(current_year or ""))
                    keywords = st.text_input("Keywords", value=paper.get("keywords") or "")
                    abstract = st.text_area("Abstract", value=paper.get("abstract") or "", height=150)
                    if st.form_submit_button("Save metadata"):
                        if year_text.strip() and not (year_text.strip().isdigit() and len(year_text.strip()) == 4):
                            st.error("Enter a four-digit year or leave it blank.")
                        else:
                            metadata = {
                                "title": title.strip() or "Unknown",
                                "authors": authors.strip() or "Unknown",
                                "publication_year": int(year_text) if year_text.strip() else None,
                                "keywords": keywords.strip(),
                                "abstract": abstract.strip(),
                            }
                            update_paper_metadata(paper["id"], metadata)
                            st.success("Metadata updated.")
                            st.rerun()

elif section == "Search History":
    st.title("Search history")
    st.caption("Your recent searches are stored locally in SQLite.")

    history = get_search_history(limit=100)

    if not history:
        st.info("No searches saved yet. Run a search from Discover first.")
    else:
        top_left, top_right = st.columns([3, 1])
        top_left.write(f"{len(history)} recent searches")

        with top_right:
            if st.button("Clear search history", use_container_width=True):
                clear_search_history()
                st.rerun()

        history_rows = [
            {
                "Date": item["created_at"],
                "Query": item["query"],
                "Method": item["method"],
                "Year filter": item["year_filter"],
                "Top results": item["top_k"],
                "Documents considered": item["document_count"],
            }
            for item in history
        ]
        st.dataframe(
            history_rows,
            hide_index=True,
            use_container_width=True,
        )

        st.subheader("Repeat a previous search")
        options = {
            (
                f"{item['created_at']} | {item['method']} | "
                f"{item['query']}"
            ): item
            for item in history
        }
        chosen_label = st.selectbox(
            "Choose a saved search",
            list(options.keys()),
        )

        if st.button("Repeat search", type="primary"):
            item = options[chosen_label]
            stored_year = item["year_filter"]
            if stored_year != "All years" and stored_year.isdigit():
                stored_year = int(stored_year)

            st.session_state["last_search"] = (
                item["query"],
                item["method"],
                stored_year,
                item["top_k"],
            )
            st.session_state["workspace"] = "Discover"
            st.session_state["repeat_search_notice"] = (
                "Previous search restored from history."
            )
            st.rerun()



elif section == "Index Explorer":
    st.title("Index Construction and Postings Viewer")
    st.write("Explore how the paper collection is represented as an inverted index.")

    if not papers:
        st.info("Import research papers to build and inspect the index.")
    else:
        documents = {
            paper["id"]: " ".join([
                paper.get("title") or "", paper.get("authors") or "",
                paper.get("keywords") or "", paper.get("abstract") or "",
                paper.get("full_text") or "",
            ])
            for paper in papers
        }
        index = build_inverted_index(documents)
        total_postings = sum(len(postings) for postings in index.values())
        c1, c2, c3 = st.columns(3)
        c1.metric("Documents", len(documents))
        c2.metric("Unique indexed terms", len(index))
        c3.metric("Total postings", total_postings)
        st.caption("Stop words are removed during index construction. Each term has one posting per document in this Boolean index.")

        st.subheader("Term dictionary")
        term_filter = st.text_input("Filter dictionary terms", placeholder="Type a term to filter the dictionary")
        dictionary_rows = [
            {"Term": term, "Document frequency": len(postings), "Posting list (paper IDs)": ", ".join(map(str, postings))}
            for term, postings in sorted(index.items())
            if not term_filter.strip() or term_filter.lower().strip() in term
        ]
        if dictionary_rows:
            st.dataframe(dictionary_rows, hide_index=True, use_container_width=True)
        else:
            st.info("No dictionary terms match that filter.")

        st.subheader("Inspect a term's postings")
        selected_term = st.selectbox("Choose an indexed term", sorted(index.keys()))
        selected_ids = index[selected_term]
        paper_lookup = {paper["id"]: paper for paper in papers}
        posting_rows = []
        for paper_id in selected_ids:
            paper = paper_lookup.get(paper_id, {})
            combined = documents.get(paper_id, "")
            from text_processor import preprocess_text
            frequency = preprocess_text(combined).count(selected_term)
            posting_rows.append({
                "Paper ID": paper_id,
                "Title": paper.get("title") or "Untitled paper",
                "Term frequency": frequency,
            })
        st.dataframe(posting_rows, hide_index=True, use_container_width=True)

        st.subheader("Positional postings")
        st.caption("Positional postings preserve token positions and are used for exact-phrase matching.")
        from inverted_index import build_positional_index
        positional_index = build_positional_index(documents)
        positional_terms = sorted(positional_index.keys())
        positional_term = st.selectbox("Choose a term for its token positions", positional_terms, key="position_term")
        positional_rows = []
        for paper_id, positions in sorted(positional_index[positional_term].items()):
            paper = paper_lookup.get(paper_id, {})
            positional_rows.append({
                "Paper ID": paper_id,
                "Title": paper.get("title") or "Untitled paper",
                "Token positions (zero-based)": ", ".join(map(str, positions)),
                "Occurrences": len(positions),
            })
        st.dataframe(positional_rows, hide_index=True, use_container_width=True)

elif section == "Ranking Comparison":
    st.title("Ranking Algorithm Comparison")
    st.write("Run one query through TF-IDF with cosine similarity and BM25, then compare the returned paper order.")
    if not papers:
        st.info("Import research papers before comparing ranking algorithms.")
    else:
        with st.form("ranking_comparison_form"):
            compare_query = st.text_input("Comparison query", placeholder="e.g. neural information retrieval")
            compare_limit = st.selectbox("Number of ranked papers", [5, 10, 20, 50], index=1)
            compare_submit = st.form_submit_button("Compare rankings", type="primary")
        if compare_submit:
            if not compare_query.strip():
                st.warning("Enter a query to compare ranking algorithms.")
            else:
                st.session_state["ranking_comparison_query"] = compare_query
                st.session_state["ranking_comparison_limit"] = compare_limit

        saved_compare_query = st.session_state.get("ranking_comparison_query", "")
        if saved_compare_query:
            limit_value = st.session_state.get("ranking_comparison_limit", 10)
            tfidf_results = search_papers(saved_compare_query, papers)
            bm25_results = search_bm25(saved_compare_query, papers)
            tfidf_rank = {paper["id"]: (rank, paper) for rank, paper in enumerate(tfidf_results, 1)}
            bm25_rank = {paper["id"]: (rank, paper) for rank, paper in enumerate(bm25_results, 1)}
            all_ids = list(dict.fromkeys(
                [paper["id"] for paper in tfidf_results] + [paper["id"] for paper in bm25_results]
            ))
            all_ids.sort(key=lambda paper_id: min(
                tfidf_rank.get(paper_id, (10**9,))[0],
                bm25_rank.get(paper_id, (10**9,))[0],
            ))
            rows = []
            for paper_id in all_ids:
                paper = (tfidf_rank.get(paper_id) or bm25_rank.get(paper_id))[1]
                t_rank, t_paper = tfidf_rank.get(paper_id, (None, {}))
                b_rank, b_paper = bm25_rank.get(paper_id, (None, {}))
                rows.append({
                    "Paper ID": paper_id,
                    "Title": paper.get("title") or "Untitled paper",
                    "TF-IDF rank": t_rank,
                    "TF-IDF cosine score": t_paper.get("score"),
                    "BM25 rank": b_rank,
                    "BM25 score": b_paper.get("score"),
                    "Rank difference": abs(t_rank - b_rank) if t_rank is not None and b_rank is not None else None,
                })
            st.caption(f"Query: {saved_compare_query}")
            st.write("Scores are not directly comparable because TF-IDF cosine similarity and BM25 use different scales. Compare ranks and ordering.")
            if rows:
                st.dataframe(rows[:limit_value], hide_index=True, use_container_width=True, column_config={
                    "Paper ID": st.column_config.NumberColumn("Paper ID", format="%d"),
                    "TF-IDF rank": st.column_config.NumberColumn("TF-IDF rank", format="%d"),
                    "TF-IDF cosine score": st.column_config.NumberColumn("TF-IDF cosine score", format="%.4f"),
                    "BM25 rank": st.column_config.NumberColumn("BM25 rank", format="%d"),
                    "BM25 score": st.column_config.NumberColumn("BM25 score", format="%.4f"),
                    "Rank difference": st.column_config.NumberColumn("Rank difference", format="%d"),
                })
            else:
                st.info("Neither algorithm found matching papers for this query.")
            left, right = st.columns(2)
            with left:
                st.subheader("TF-IDF + Cosine Similarity")
                for rank, paper in enumerate(tfidf_results[:limit_value], 1):
                    st.write(f"{rank}. {paper.get('title') or 'Untitled paper'} — {paper['score']:.4f}")
            with right:
                st.subheader("BM25")
                for rank, paper in enumerate(bm25_results[:limit_value], 1):
                    st.write(f"{rank}. {paper.get('title') or 'Untitled paper'} — {paper['score']:.4f}")


elif section == "Document Clustering":
    st.title("Topic Discovery & Document Clustering")
    st.write(
        "Discover groups of related research papers automatically using TF-IDF and K-Means. "
        "Cluster keywords help you interpret each group; clusters are not predefined labels."
    )

    if len(papers) < 2:
        st.info("Import at least two research papers with extracted text to discover topics.")
    else:
        max_clusters = min(10, len(papers))
        default_clusters = min(4, max_clusters)
        with st.form("document_clustering_form"):
            selected_clusters = st.slider(
                "Number of clusters (K)", min_value=2, max_value=max_clusters,
                value=max(2, default_clusters),
                help="Choose how many groups K-Means should create. Try 3–5 for a small collection.",
            )
            run_clustering = st.form_submit_button("Discover topics", type="primary")

        if run_clustering:
            try:
                st.session_state["document_clustering_result"] = cluster_papers(
                    papers, n_clusters=selected_clusters
                )
                st.session_state["document_clustering_k"] = selected_clusters
                st.session_state.pop("document_clustering_error", None)
            except ValueError as exc:
                st.session_state["document_clustering_error"] = str(exc)
                st.session_state.pop("document_clustering_result", None)

        if st.session_state.get("document_clustering_error"):
            st.warning(st.session_state["document_clustering_error"])

        clustering_result = st.session_state.get("document_clustering_result")
        if clustering_result:
            if clustering_result["skipped_count"]:
                st.warning(
                    f"{clustering_result['skipped_count']} paper(s) were skipped because no usable text was available."
                )

            metric_columns = st.columns(3)
            metric_columns[0].metric("Papers clustered", clustering_result["usable_count"])
            metric_columns[1].metric("Topics discovered", clustering_result["n_clusters"])
            nonempty_clusters = sum(1 for count in clustering_result["counts"].values() if count > 0)
            metric_columns[2].metric("Non-empty clusters", nonempty_clusters)

            st.subheader("Discovered topics")
            keyword_rows = []
            for cluster_id in range(1, clustering_result["n_clusters"] + 1):
                keyword_rows.append({
                    "Cluster": f"Cluster {cluster_id}",
                    "Papers": clustering_result["counts"].get(cluster_id, 0),
                    "Representative keywords": ", ".join(clustering_result["keywords"].get(cluster_id, [])) or "No clear keywords",
                })
            st.dataframe(keyword_rows, hide_index=True, use_container_width=True)

            st.subheader("Cluster map")
            st.caption("Each point is a paper. The 2D PCA map is a projection for exploration; distances in this plot are only an approximation of the original TF-IDF space.")
            try:
                import plotly.express as px
                import pandas as pd
                plot_frame = pd.DataFrame(clustering_result["rows"])
                plot_frame["Cluster"] = plot_frame["Cluster"].map(lambda value: f"Cluster {value}")
                figure = px.scatter(
                    plot_frame, x="x", y="y", color="Cluster", hover_name="Title",
                    hover_data={"Paper ID": True, "Cluster keywords": True, "x": False, "y": False},
                    title="Research paper clusters (PCA projection)",
                )
                figure.update_layout(legend_title_text="Topic group", height=480)
                st.plotly_chart(figure, use_container_width=True)
            except ImportError:
                st.info("Install plotly to enable the optional cluster map: pip install plotly")

            st.subheader("Explore papers in a cluster")
            cluster_options = list(range(1, clustering_result["n_clusters"] + 1))
            selected_cluster = st.selectbox(
                "Select a cluster",
                cluster_options,
                format_func=lambda value: f"Cluster {value} ({clustering_result['counts'].get(value, 0)} papers)",
            )
            cluster_rows = [
                {key: row[key] for key in ["Paper ID", "Title", "Authors", "Year", "Cluster keywords"]}
                for row in clustering_result["rows"] if row["Cluster"] == selected_cluster
            ]
            if cluster_rows:
                st.dataframe(cluster_rows, hide_index=True, use_container_width=True)
                import csv
                import io
                csv_buffer = io.StringIO()
                writer = csv.DictWriter(csv_buffer, fieldnames=list(cluster_rows[0].keys()))
                writer.writeheader()
                writer.writerows(cluster_rows)
                st.download_button(
                    "Export selected cluster as CSV",
                    data=csv_buffer.getvalue().encode("utf-8-sig"),
                    file_name=f"researchsphere_cluster_{selected_cluster}.csv",
                    mime="text/csv",
                )
            else:
                st.info("This cluster has no papers. Try a smaller number of clusters.")

            st.subheader("All clustered papers")
            all_rows = [
                {key: row[key] for key in ["Paper ID", "Title", "Authors", "Year", "Cluster", "Cluster keywords"]}
                for row in clustering_result["rows"]
            ]
            st.dataframe(all_rows, hide_index=True, use_container_width=True)
            import csv
            import io
            all_csv = io.StringIO()
            writer = csv.DictWriter(all_csv, fieldnames=list(all_rows[0].keys()))
            writer.writeheader()
            writer.writerows(all_rows)
            st.download_button(
                "Export all clusters as CSV",
                data=all_csv.getvalue().encode("utf-8-sig"),
                file_name="researchsphere_document_clusters.csv",
                mime="text/csv",
            )



elif section == "Evaluation":
    st.title("Retrieval evaluation")
    st.write(
        "Compare TF-IDF and BM25 using manually judged relevant documents. "
        "The scores depend on the relevance labels you provide."
    )

    if not papers:
        st.info("Import papers before running an evaluation.")
    else:
        with st.expander("View paper IDs"):
            for paper in papers:
                st.write(paper_label(paper))

        with st.form("evaluation_form"):
            eval_query = st.text_input(
                "Evaluation query",
                placeholder="e.g. neural information retrieval"
            )
            relevant_text = st.text_input(
                "Relevant paper IDs",
                placeholder="e.g. 1, 3, 5"
            )
            k = st.selectbox("Cutoff K", [3, 5, 10], index=1)
            bm25_k1 = st.slider(
                "BM25 term-frequency parameter (k1)",
                min_value=0.5,
                max_value=2.5,
                value=1.5,
                step=0.1,
                help="Controls how quickly repeated query terms stop adding value."
            )
            bm25_b = st.slider(
                "BM25 document-length normalization (b)",
                min_value=0.0,
                max_value=1.0,
                value=0.75,
                step=0.05,
                help="Controls how strongly document length affects ranking."
            )
            run = st.form_submit_button(
                "Compare algorithms",
                type="primary"
            )

        if run:
            try:
                relevant_ids = {
                    int(value.strip())
                    for value in relevant_text.split(",")
                    if value.strip()
                }

                if not eval_query.strip():
                    st.warning("Enter an evaluation query.")
                elif not relevant_ids:
                    st.warning(
                        "Provide manually judged relevant paper IDs."
                    )
                elif not relevant_ids.issubset(by_id):
                    st.warning("One or more paper IDs do not exist.")
                else:
                    report = evaluate_query(
                        eval_query,
                        papers,
                        relevant_ids,
                        k,
                        bm25_k1=bm25_k1,
                        bm25_b=bm25_b
                    )

                    st.subheader("Ranking quality comparison")
                    st.caption(
                        f"Query: {eval_query} | Cutoff: {k} | "
                        f"Relevant documents judged: {len(relevant_ids)} | "
                        f"BM25 k1={bm25_k1:.1f}, b={bm25_b:.2f}"
                    )

                    metric_rows = [
                        {
                            "Ranking method": "TF-IDF",
                            f"Precision@{k}": report["tfidf_precision"],
                            f"Recall@{k}": report["tfidf_recall"],
                            f"F1@{k}": report["tfidf_f1"],
                            f"AP@{k}": report["tfidf_ap"],
                            f"nDCG@{k}": report["tfidf_ndcg"],
                        },
                        {
                            "Ranking method": "BM25",
                            f"Precision@{k}": report["bm25_precision"],
                            f"Recall@{k}": report["bm25_recall"],
                            f"F1@{k}": report["bm25_f1"],
                            f"AP@{k}": report["bm25_ap"],
                            f"nDCG@{k}": report["bm25_ndcg"],
                        },
                    ]

                    st.dataframe(
                        metric_rows,
                        hide_index=True,
                        use_container_width=True,
                        column_config={
                            "Ranking method": st.column_config.TextColumn(
                                "Ranking method"
                            ),
                            f"Precision@{k}": st.column_config.NumberColumn(
                                f"Precision@{k}", format="%.3f"
                            ),
                            f"Recall@{k}": st.column_config.NumberColumn(
                                f"Recall@{k}", format="%.3f"
                            ),
                            f"F1@{k}": st.column_config.NumberColumn(
                                f"F1@{k}", format="%.3f"
                            ),
                            f"AP@{k}": st.column_config.NumberColumn(
                                f"AP@{k}", format="%.3f"
                            ),
                            f"nDCG@{k}": st.column_config.NumberColumn(
                                f"nDCG@{k}", format="%.3f"
                            ),
                        },
                    )

                    st.caption(
                        "Precision@K measures the fraction of the first K "
                        "results that are relevant. Recall@K measures the "
                        "fraction of known relevant papers retrieved. F1@K "
                        "balances precision and recall. AP@K rewards relevant "
                        "papers appearing earlier. nDCG@K evaluates ranking "
                        "quality using discounted gains. Relevance labels are "
                        "binary and supplied manually."
                    )

                    st.subheader("Retrieved documents")
                    for method_label, result_key in [
                        ("TF-IDF", "tfidf_results"),
                        ("BM25", "bm25_results"),
                    ]:
                        with st.expander(
                            f"{method_label} results",
                            expanded=True
                        ):
                            retrieved = report[result_key]

                            if not retrieved:
                                st.write("No results were returned.")
                                continue

                            result_rows = []
                            for position, paper in enumerate(
                                retrieved,
                                start=1
                            ):
                                result_rows.append({
                                    "Rank": position,
                                    "Paper ID": paper["id"],
                                    "Title": (
                                        paper.get("title") or "Untitled paper"
                                    ),
                                    "Score": paper.get("score", None),
                                    "Judgment": (
                                        "Relevant"
                                        if paper["id"] in relevant_ids
                                        else "Not marked relevant"
                                    ),
                                })

                            st.dataframe(
                                result_rows,
                                hide_index=True,
                                use_container_width=True,
                                column_config={
                                    "Rank": st.column_config.NumberColumn(
                                        "Rank", format="%d"
                                    ),
                                    "Paper ID": st.column_config.NumberColumn(
                                        "Paper ID", format="%d"
                                    ),
                                    "Score": st.column_config.NumberColumn(
                                        "Score", format="%.4f"
                                    ),
                                },
                            )

                    st.info(
                        "For a meaningful comparison, repeat the evaluation "
                        "with several queries and carefully judged relevant "
                        "papers. These results are not a benchmark unless "
                        "the relevance labels are consistently reviewed."
                    )

            except ValueError:
                st.error(
                    "Paper IDs must be whole numbers separated by commas."
                )
elif section == "IR Analysis":
    st.title("Information Retrieval Analysis")
    st.write(
        "Inspect query processing, the inverted index, document-term "
        "statistics, and ranking differences between TF-IDF and BM25."
    )

    if not papers:
        st.info("Import research papers to analyze retrieval.")
    else:
        with st.form("ir_analysis_form"):
            analysis_query = st.text_input(
                "Analysis query",
                placeholder="e.g. neural information retrieval"
            )
            analyze_button = st.form_submit_button(
                "Analyze query",
                type="primary"
            )

        if analyze_button:
            if not analysis_query.strip():
                st.warning("Enter a query to analyze.")
            else:
                st.session_state["ir_analysis_query"] = analysis_query

        saved_analysis_query = st.session_state.get("ir_analysis_query", "")

        if saved_analysis_query:
            report = analyze_query(saved_analysis_query, papers)
            st.divider()
            st.subheader("1. Query processing")

            st.write("**Original query**")
            st.code(saved_analysis_query)

            st.write("**Processed terms**")
            if report["query_terms"]:
                st.code("  ".join(report["query_terms"]))
            else:
                st.info(
                    "No terms remain after normalization and stop-word removal."
                )

            metric_cols = st.columns(3)
            metric_cols[0].metric(
                "Query terms",
                len(report["query_terms"])
            )
            metric_cols[1].metric(
                "Unique terms",
                len(set(report["query_terms"]))
            )
            metric_cols[2].metric(
                "Documents indexed",
                len(papers)
            )

            st.subheader("2. Term statistics")
            if report["term_statistics"]:
                st.dataframe(
                    report["term_statistics"],
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Term": st.column_config.TextColumn("Term"),
                        "Document Frequency": st.column_config.NumberColumn(
                            "Document Frequency", format="%d"
                        ),
                        "Total Occurrences": st.column_config.NumberColumn(
                            "Total Occurrences", format="%d"
                        ),
                    },
                )
            else:
                st.info("No searchable query terms were found.")

            st.subheader("3. Inverted index")
            if report["query_terms"]:
                selected_term = st.selectbox(
                    "Inspect a query term",
                    list(dict.fromkeys(report["query_terms"])),
                    key="ir_index_term"
                )
                postings = get_term_postings(
                    selected_term,
                    papers
                )

                st.write(f"**Term:** `{selected_term}`")
                st.write(f"**Posting list length:** {len(postings)}")

                if postings:
                    posting_rows = [
                        {
                            "Paper ID": item["paper_id"],
                            "Title": item["title"],
                            "Term Frequency": item["term_frequency"],
                        }
                        for item in postings
                    ]
                    st.dataframe(
                        posting_rows,
                        hide_index=True,
                        use_container_width=True
                    )
                else:
                    st.info("This term does not occur in the indexed papers.")

            st.subheader("4. Ranking comparison")
            tfidf_results = search_papers(saved_analysis_query, papers)
            bm25_results = search_bm25(saved_analysis_query, papers)

            ranking_rows = []
            for method_name, ranked_results in [
                ("TF-IDF + Cosine Similarity", tfidf_results),
                ("BM25", bm25_results),
            ]:
                for rank, paper in enumerate(ranked_results[:10], start=1):
                    ranking_rows.append({
                        "Method": method_name,
                        "Rank": rank,
                        "Paper ID": paper["id"],
                        "Title": paper.get("title") or "Untitled paper",
                        "Score": paper.get("score", 0.0),
                    })

            if ranking_rows:
                st.dataframe(
                    ranking_rows,
                    hide_index=True,
                    use_container_width=True,
                    column_config={
                        "Rank": st.column_config.NumberColumn(
                            "Rank", format="%d"
                        ),
                        "Paper ID": st.column_config.NumberColumn(
                            "Paper ID", format="%d"
                        ),
                        "Score": st.column_config.NumberColumn(
                            "Score", format="%.4f"
                        ),
                    },
                )
            else:
                st.info("Neither ranking method returned matching papers.")

            st.caption(
                "TF-IDF cosine scores and BM25 scores use different scales; "
                "compare their ranking order, not the raw score values."
            )

elif section == "Cloud Management":
    st.title("Cloud Infrastructure & Instance Control")
    st.write("Real-time monitoring and 1-click controls for ResearchSphere cloud instances.")
    st.caption("Instantly scale down Auto Scaling Groups and terminate all running EC2 instances to stop AWS billing.")
    st.divider()

    # Live Application URL (dynamically fetched from ALB)
    with st.container(border=True):
        st.subheader("🌐 Live Application URL")
        st.markdown(
            "The application URL changes every time the infrastructure is re-created (new deployment). "
            "The URL below is fetched live from AWS each time this page loads."
        )
        try:
            import boto3 as _boto3_url
            _region_for_url = st.session_state.get("aws_region") or DEFAULT_REGION
            _key_for_url = st.session_state.get("aws_access_key") or None
            _secret_for_url = st.session_state.get("aws_secret_key") or None
            _sess_kwargs: dict = {"region_name": _region_for_url}
            if _key_for_url and _secret_for_url:
                _sess_kwargs["aws_access_key_id"] = _key_for_url
                _sess_kwargs["aws_secret_access_key"] = _secret_for_url
            _elbv2 = _boto3_url.Session(**_sess_kwargs).client("elbv2")
            _albs = _elbv2.describe_load_balancers(Names=["researchsphere-alb"]).get("LoadBalancers", [])
            if _albs:
                _dns = _albs[0]["DNSName"]
                _live_url = f"http://{_dns}"
                st.success(f"✅ **Application is deployed!**")
                st.markdown(f"### 👉 [{_live_url}]({_live_url})")
                st.caption(f"DNS: `{_dns}`")
                st.markdown(
                    "> 💡 Always use **`http://`** (not `https://`). "
                    "If you see a DNS error in the browser, wait 2-3 minutes after deployment — the instance is still booting."
                )
            else:
                st.warning("⚠️ No active Load Balancer found. Deploy the application first via GitHub Actions.")
        except Exception as _e:
            st.info(
                "ℹ️ Could not auto-fetch the URL from AWS. Set credentials in the **⚙️ AWS Configuration** panel below, "
                "or check the **GitHub Actions deploy job summary** for the latest URL.\n\n"
                f"Reason: `{_e}`"
            )

    # Credential & Configuration Expander
    with st.expander("⚙️ AWS Configuration & Credentials (Optional)", expanded=False):
        c_k1, c_k2, c_k3 = st.columns([1, 1, 1])
        cfg_region = c_k1.text_input("AWS Region", value=st.session_state.get("aws_region", DEFAULT_REGION))
        cfg_key = c_k2.text_input("AWS Access Key ID", value=st.session_state.get("aws_access_key", ""), type="password")
        cfg_secret = c_k3.text_input("AWS Secret Key", value=st.session_state.get("aws_secret_key", ""), type="password")

        c_p1, c_p2 = st.columns(2)
        cfg_project = c_p1.text_input("Project Name Tag", value=DEFAULT_PROJECT)
        cfg_asg = c_p2.text_input("Auto Scaling Group Name", value=DEFAULT_ASG)

        if st.button("Save Credentials for Session"):
            st.session_state["aws_region"] = cfg_region
            st.session_state["aws_access_key"] = cfg_key
            st.session_state["aws_secret_key"] = cfg_secret
            st.success("Credentials saved to session state.")
            st.rerun()

    # Active session or environment credentials
    active_key = st.session_state.get("aws_access_key") or None
    active_secret = st.session_state.get("aws_secret_key") or None
    active_region = st.session_state.get("aws_region") or DEFAULT_REGION
    active_project = DEFAULT_PROJECT
    active_asg = DEFAULT_ASG

    # 1-Click Action Hub Container
    with st.container(border=True):
        st.subheader("⚡ 1-Click Cloud Controls")

        col_stop, col_start, col_refresh = st.columns([2, 1, 1])

        with col_stop:
            stop_clicked = st.button(
                "🛑 Stop Instances (Scale to 0)",
                type="primary",
                use_container_width=True,
                help="Sets ASG to 0 and terminates all active project EC2 instances. ALB & VPC stay alive for quick restart.",
                key="btn_stop"
            )

        with col_start:
            start_clicked = st.button(
                "🟢 Scale Up (1 Instance)",
                use_container_width=True,
                help="Restores 1 EC2 instance in the Auto Scaling Group.",
                key="btn_start"
            )

        with col_refresh:
            if st.button("🔄 Refresh", use_container_width=True, key="btn_refresh"):
                st.rerun()

    # Terminate All Resources section (separate danger zone)
    with st.container(border=True):
        st.subheader("💥 Terminate ALL Resources (Danger Zone)")
        st.markdown(
            "This will **permanently delete** all AWS resources: Auto Scaling Group, Load Balancer, Target Group, and EC2 instances. "
            "VPC/Security Groups/Route Tables can only be fully removed via the **GitHub Actions** `full_destroy` workflow."
        )

        confirm_col, destroy_col = st.columns([3, 1])
        with confirm_col:
            confirm_text = st.text_input(
                "Type **TERMINATE** to confirm full resource destruction",
                placeholder="TERMINATE",
                key="terminate_confirm",
                label_visibility="visible"
            )
        with destroy_col:
            st.markdown("<br>", unsafe_allow_html=True)
            destroy_clicked = st.button(
                "💥 Terminate ALL",
                type="primary",
                use_container_width=True,
                help="Permanently destroys ALB, ASG, EC2 instances.",
                key="btn_destroy"
            )

        if destroy_clicked:
            if confirm_text.strip() != "TERMINATE":
                st.error("❌ Type **TERMINATE** in the box above to confirm. This action cannot be undone.")
            else:
                with st.spinner("☠️ Terminating all AWS resources (ASG, ALB, EC2 instances)..."):
                    destroy_result = destroy_all_resources(
                        access_key=active_key,
                        secret_key=active_secret,
                        region=active_region,
                        project_name=active_project,
                        asg_name=active_asg,
                    )

                if destroy_result.get("success"):
                    st.success("✅ All resources terminated successfully!")
                else:
                    st.warning("⚠️ Partial completion — some resources may need manual cleanup.")

                with st.expander("Execution Details", expanded=True):
                    for act in destroy_result.get("actions", []):
                        st.write(act)
                    for err in destroy_result.get("errors", []):
                        st.error(f"Error: {err}")
                    if destroy_result.get("note"):
                        st.info(f"💡 {destroy_result['note']}")
                    if destroy_result.get("error"):
                        st.error(destroy_result["error"])

                st.info(
                    "For **complete cleanup** including VPC, Subnets and Security Groups, "
                    "go to GitHub Actions → **🛑 Terminate AWS Resources (1-Click)** → Run workflow → select **full_destroy**."
                )

        if stop_clicked:
            with st.spinner("Terminating all active cloud instances and scaling ASG to 0..."):
                del_result = delete_all_running_instances(
                    access_key=active_key,
                    secret_key=active_secret,
                    region=active_region,
                    project_name=active_project,
                    asg_name=active_asg,
                )

            if del_result.get("success"):
                st.success(
                    f"✅ **Action Complete!** {del_result.get('terminated_count', 0)} instance(s) terminated. "
                    "Auto Scaling Group scaled to 0. AWS billing for compute instances is stopped."
                )
                with st.expander("View execution details", expanded=True):
                    for act in del_result.get("actions", []):
                        st.write(f"- {act}")
                    if del_result.get("terminated_ids"):
                        st.code(", ".join(del_result["terminated_ids"]), language="text")
            else:
                st.error(f"❌ Failed to terminate instances: {del_result.get('error')}")

        # Handle Start Action
        if start_clicked:
            with st.spinner("Scaling up Auto Scaling Group..."):
                up_result = scale_up_instances(
                    count=1,
                    access_key=active_key,
                    secret_key=active_secret,
                    region=active_region,
                    asg_name=active_asg,
                )
            if up_result.get("success"):
                st.success(up_result.get("message"))
            else:
                st.error(f"❌ Failed to scale up: {up_result.get('error')}")

    st.markdown("<br>", unsafe_allow_html=True)

    # Fetch and display current cloud status
    with st.spinner("Fetching live cloud status..."):
        cloud_status = get_cloud_status(
            access_key=active_key,
            secret_key=active_secret,
            region=active_region,
            project_name=active_project,
            asg_name=active_asg,
        )

    # Metrics row
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)

    if cloud_status.get("success"):
        running_cnt = cloud_status.get("running_count", 0)
        total_cnt = cloud_status.get("total_count", 0)
        asg_data = cloud_status.get("asg") or {}
        desired = asg_data.get("desired_capacity", "N/A")
        min_max = f"{asg_data.get('min_size', 0)} / {asg_data.get('max_size', 0)}" if "min_size" in asg_data else "N/A"

        m_col1.metric("Running Instances", running_cnt, delta="Active" if running_cnt > 0 else "Offline", delta_color="normal" if running_cnt > 0 else "off")
        m_col2.metric("ASG Desired Capacity", desired)
        m_col3.metric("ASG Min / Max", min_max)
        m_col4.metric("AWS Region", cloud_status.get("region", active_region))

        st.subheader("Cloud Instances")
        instances_list = cloud_status.get("instances", [])
        if instances_list:
            display_rows = [
                {
                    "Instance ID": inst["id"],
                    "Name": inst["name"],
                    "State": inst["state"].upper(),
                    "Type": inst["type"],
                    "Public IP": inst["public_ip"],
                    "Private IP": inst["private_ip"],
                    "Launch Time": inst["launch_time"],
                }
                for inst in instances_list
            ]
            st.dataframe(display_rows, hide_index=True, use_container_width=True)
        else:
            st.info("ℹ️ No EC2 instances found with tag `Project: researchsphere` or in the Auto Scaling Group.")

    else:
        m_col1.metric("Running Instances", "Unknown")
        m_col2.metric("ASG Desired Capacity", "Unknown")
        m_col3.metric("ASG Min / Max", "Unknown")
        m_col4.metric("AWS Region", active_region)

        st.warning(f"Could not connect to AWS: {cloud_status.get('error')}")
        st.info(
            "💡 Ensure your AWS credentials are set via environment variables (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`), "
            "AWS CLI configuration (`aws configure`), or provide them in the Configuration panel above."
        )

    st.divider()

    # Alternative 1-Click Methods
    st.subheader("📱 Alternative 1-Click Methods")
    c_m1, c_m2 = st.columns(2)
    with c_m1:
        with st.container(border=True):
            st.markdown("#### 🐙 GitHub Actions (Web)")
            st.write(
                "You can also delete all running cloud instances directly from GitHub without opening the app:\n"
                "1. Go to your GitHub repository -> **Actions** tab\n"
                "2. Select **🛑 Stop & Delete Cloud Instances (1-Click)**\n"
                "3. Click **Run workflow**"
            )
            st.caption("Workflow file: `.github/workflows/cleanup-instances.yml`")

    with c_m2:
        with st.container(border=True):
            st.markdown("#### 💻 Desktop 1-Click Script")
            st.write(
                "On your local Windows machine, you can delete running instances with a single double-click:\n"
                "- Double-click `scripts/delete_instances.bat` in File Explorer\n"
                "- Or run in PowerShell: `.\\scripts\\delete_instances.ps1`\n"
                "- Or run in terminal: `python scripts/delete_instances.py`"
            )
            st.caption("Automatically scales down ASG to 0 and terminates all active instances.")

