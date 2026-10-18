"""Text normalization shared by ResearchSphere retrieval modules."""

import re

STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being",
    "but", "by", "can", "could", "did", "do", "does", "for", "from",
    "had", "has", "have", "he", "her", "hers", "him", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "may", "might",
    "more", "most", "no", "not", "of", "on", "or", "our", "ours",
    "she", "should", "so", "such", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "those", "to",
    "was", "we", "were", "what", "when", "where", "which", "who",
    "will", "with", "would", "you", "your",
}


def preprocess_text(text):
    """Lowercase text, extract alphanumeric terms, and remove stop words."""
    if not text:
        return []

    terms = re.findall(r"[a-z0-9]+", str(text).lower())
    return [term for term in terms if term not in STOP_WORDS]
