# ResearchSphere

**Research Paper Intelligence and Search Engine**

ResearchSphere is a Streamlit-based mini project that helps users
organize, search, and explore research papers. It demonstrates core
Information Retrieval concepts through a simple interactive interface.

## Features

-   **Research paper library:** Store and browse papers and their
    extracted metadata.
-   **Keyword search:** Retrieve papers using TF-IDF or BM25 ranking.
-   **Boolean retrieval:** Search using `AND`, `OR`, `NOT`, and
    parentheses.
-   **Phrase search:** Find papers containing an exact phrase.
-   **Index Explorer:** Inspect terms and their postings in the inverted
    index.
-   **Ranking comparison:** Compare TF-IDF and BM25 result rankings.
-   **Search history:** Revisit previous searches.
-   **Document clustering:** Group papers with similar textual content
    using TF-IDF and K-Means.
-   **Topic keywords:** View representative terms for each cluster.
-   **Cluster exploration and export:** Browse papers within a cluster
    and export results as CSV.
-   **IR analysis and evaluation:** Explore retrieval-related analysis
    and the existing evaluation module.

> The Paper Viewer has been removed from this version.

## Document Clustering

The clustering feature discovers groups of similar papers without
requiring predefined topic labels.

1.  The system combines each paper's title, abstract, keywords, and
    extracted full text where available.
2.  `TfidfVectorizer` converts the text into numerical TF-IDF vectors.
3.  K-Means assigns papers to the selected number of clusters.
4.  The system displays cluster sizes and representative keywords.
5.  Users can explore the papers in each cluster and export cluster
    results.

Papers without usable text are skipped. At least two papers with usable
text are required, and the selected number of clusters must be between 2
and the number of usable papers.

The optional PCA plot projects the vectors into two dimensions for
visual exploration. PCA is used for visualization only; K-Means performs
clustering on the TF-IDF vectors.

## Technology Stack

-   **Language:** Python
-   **Interface:** Streamlit
-   **Information Retrieval:** TF-IDF, cosine similarity, BM25, inverted
    index, Boolean retrieval, phrase search
-   **Document clustering:** scikit-learn TF-IDF vectorization and
    K-Means
-   **Visualization:** Plotly and PCA
-   **Data storage:** SQLite
-   **PDF text extraction:** PyMuPDF (through the existing project
    module)

## Project Structure

The supplied update package contains the following files:

``` text
researchsphere_cluster_release/
├── app.py
├── document_clustering.py
├── inverted_index.py
├── search_history.py
└── README.md
```

This is a feature update package, not a standalone copy of every project
dependency. Keep the remaining files from your existing ResearchSphere
project, including `database.py`, `evaluation.py`, `ir_analysis.py`,
`metadata_extractor.py`, `pdf_reader.py`, `search_engine.py`, and
`text_processor.py`, along with your SQLite database and paper files.

## Requirements

Use Python 3.10 or later where possible, and install the following
packages if they are not already installed:

``` bash
pip install streamlit scikit-learn numpy plotly pandas pymupdf
```

Install any additional dependencies required by your existing project
modules.

## Setup and Run

1.  Back up your current project.
2.  Extract the update package.
3.  Copy the included `app.py`, `document_clustering.py`,
    `inverted_index.py`, and `search_history.py` into your existing
    project directory, replacing the corresponding files when prompted.
4.  Keep the rest of your existing project files and the existing
    `data/research_papers.db` database.
5.  Open a terminal in the project directory.
6.  Run:

``` bash
streamlit run app.py
```

Streamlit will display a local URL in the terminal. Open that URL in
your browser.

## Using Document Clustering

1.  Open **Document Clustering** from the sidebar.
2.  Choose the number of clusters.
3.  Run clustering on the available paper collection.
4.  Review cluster sizes and representative keywords.
5.  Select a cluster to explore its papers.
6.  Export the selected cluster or the full clustering results to CSV if
    the export option is available in the interface.

Results depend on the quality and amount of text extracted from the
available papers. Clusters are algorithm-generated groups and should be
interpreted using their representative keywords and paper contents.

## Notes and Limitations

-   Clustering quality depends on the paper collection and the extracted
    text.
-   TF-IDF emphasizes word usage, so papers with related meanings but
    different vocabulary may not always be grouped together.
-   K-Means requires the number of clusters to be selected before
    clustering.
-   Automatically generated cluster keywords are descriptive terms, not
    guaranteed human-readable topic labels.
-   Keep a backup before replacing project files.
-   The update package does not include your existing database or PDF
    collection.

## 1-Click Cloud Instance Control & Deletion

To prevent ongoing AWS EC2 charges when not in use, you can terminate all running cloud instances in **one click** using any of the following methods:

### 1. In the Web App (Streamlit UI)
1. Navigate to **Cloud Management** in the sidebar.
2. Click **🛑 Delete & Terminate All Running Cloud Instances**.
3. The Auto Scaling Group will immediately scale down to `0` and terminate all active EC2 instances.
4. You can also click **🟢 Scale Up (1 Instance)** to turn the instances back on anytime.

### 2. GitHub Actions (Web UI)
1. In your GitHub repository, open the **Actions** tab.
2. Select **🛑 Stop & Delete Cloud Instances (1-Click)**.
3. Click **Run workflow**.

### 3. Desktop / Local 1-Click Script
- **Windows double-click:** Double-click [`scripts/delete_instances.bat`](file:///d:/Rizwan%20Codes/IR%20project/TF-Project/scripts/delete_instances.bat).
- **PowerShell:** Run [`scripts/delete_instances.ps1`](file:///d:/Rizwan%20Codes/IR%20project/TF-Project/scripts/delete_instances.ps1).
- **Terminal:** Run `python scripts/delete_instances.py`.

## Academic Purpose

ResearchSphere demonstrates practical Information Retrieval techniques
and an unsupervised learning approach to discovering groups of related
research papers. It is intended for educational and mini-project use.

