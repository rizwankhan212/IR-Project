"""Boolean and positional inverted indexes for ResearchSphere."""

import re

from text_processor import preprocess_text


def _tokens(text):
    """Tokenize text without removing stop words, for exact phrase matching."""
    return re.findall(r"[a-z0-9]+", str(text or "").lower())


def build_inverted_index(documents):
    """Build a term-to-document posting list for Boolean retrieval."""
    index = {}

    for doc_id, text in documents.items():
        for term in set(preprocess_text(text)):
            index.setdefault(term, []).append(doc_id)

    for term in index:
        index[term].sort()

    return index


def search_keyword(index, keyword):
    """Return documents containing the first searchable keyword."""
    terms = preprocess_text(keyword)
    if not terms:
        return []
    return index.get(terms[0], [])


def search_and(index, query):
    """Return documents containing every searchable query term."""
    terms = preprocess_text(query)
    if not terms:
        return []

    results = set(index.get(terms[0], []))
    for term in terms[1:]:
        results.intersection_update(index.get(term, []))

    return sorted(results)


def search_or(index, query):
    """Return documents containing at least one searchable query term."""
    terms = preprocess_text(query)
    results = set()

    for term in terms:
        results.update(index.get(term, []))

    return sorted(results)


def build_positional_index(documents):
    """Build a positional index: term -> document ID -> token positions."""
    index = {}

    for doc_id, text in documents.items():
        for position, term in enumerate(_tokens(text)):
            index.setdefault(term, {}).setdefault(doc_id, []).append(position)

    return index


def search_phrase(index, phrase):
    """Return document IDs containing the exact normalized phrase."""
    terms = _tokens(phrase)
    if not terms:
        return []

    first_term_postings = index.get(terms[0], {})
    matches = []

    for doc_id, first_positions in first_term_postings.items():
        other_positions = [
            set(index.get(term, {}).get(doc_id, []))
            for term in terms[1:]
        ]

        for start in first_positions:
            if all(
                start + offset in positions
                for offset, positions in enumerate(other_positions, start=1)
            ):
                matches.append(doc_id)
                break

    return sorted(matches)


def search_boolean_query(index, query, all_doc_ids):
    """Evaluate a Boolean expression with AND, OR, NOT and parentheses.

    AND has higher precedence than OR. Adjacent terms imply AND, so both
    "machine AND learning" and "machine learning" are accepted.
    """
    tokens = re.findall(r"\(|\)|\bAND\b|\bOR\b|\bNOT\b|[a-zA-Z0-9]+", str(query or ""), re.I)
    tokens = [token.upper() if token.upper() in {"AND", "OR", "NOT"} or token in {"(", ")"} else token.lower() for token in tokens]
    if not tokens:
        return []

    universe = set(all_doc_ids)
    position = 0

    def starts_unary(token):
        return token == "NOT" or token == "(" or token not in {"AND", "OR", ")"}

    def parse_primary():
        nonlocal position
        if position >= len(tokens):
            raise ValueError("Unexpected end of Boolean query.")
        token = tokens[position]
        if token == "(":
            position += 1
            value = parse_or()
            if position >= len(tokens) or tokens[position] != ")":
                raise ValueError("Missing closing parenthesis.")
            position += 1
            return value
        if token in {"AND", "OR", ")"}:
            raise ValueError(f"Unexpected operator: {token}")
        position += 1
        terms = preprocess_text(token)
        if not terms:
            return set()
        result = set(index.get(terms[0], []))
        for term in terms[1:]:
            result.intersection_update(index.get(term, []))
        return result

    def parse_unary():
        nonlocal position
        if position < len(tokens) and tokens[position] == "NOT":
            position += 1
            return universe - parse_unary()
        return parse_primary()

    def parse_and():
        nonlocal position
        result = parse_unary()
        while position < len(tokens):
            token = tokens[position]
            if token == "AND":
                position += 1
                result.intersection_update(parse_unary())
            elif starts_unary(token):
                # Implicit AND between adjacent terms/groups.
                result.intersection_update(parse_unary())
            else:
                break
        return result

    def parse_or():
        nonlocal position
        result = parse_and()
        while position < len(tokens) and tokens[position] == "OR":
            position += 1
            result.update(parse_and())
        return result

    results = parse_or()
    if position != len(tokens):
        raise ValueError(f"Unexpected token: {tokens[position]}")
    return sorted(results)
