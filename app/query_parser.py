"""Natural-language query parser for the job-search pipeline.

Responsible for turning a raw user query string into a structured
``SearchSignals`` object that the retrieval and ranking layers consume.

Key capabilities
----------------
- **Tokenisation** with stopword removal.
- **Abbreviation expansion** (ml → machine learning, etc.).
- **Negation extraction** – detects "not management", "don't want director",
  "neither … nor …" and similar patterns.
- **Location extraction** – pulls out "in <place>" while guarding against
  false positives like "in data science".
- **Mission-driven detection** – flags queries containing social-good phrases.
- **Signal merging** – unions two ``SearchSignals`` during multi-turn refine.
"""

from __future__ import annotations

import re
from typing import List

from app.constants import (
    ABBREVIATION_EXPANSIONS,
    MISSION_QUERY_TERMS,
    NEGATION_CUES,
    NEGATION_NOISE_TOKENS,
    NEGATION_TERMS,
    NON_LOCATION_PHRASES,
    NON_LOCATION_TOKENS,
    ORG_TYPES,
    SENIORITY,
    STOPWORDS,
)
from app.schema import SearchSignals


# ---------------------------------------------------------------------------
# Tokenisation & normalisation
# ---------------------------------------------------------------------------


def tokenize(text: str) -> List[str]:
    """Split text into lowercase alpha-numeric tokens, dropping stopwords.

    Args:
        text: Raw text to tokenize.

    Returns:
        Ordered list of non-stopword tokens.
    """
    return [t for t in re.findall(r"[a-zA-Z0-9]+", text.lower()) if t not in STOPWORDS]


def normalize_query(query: str) -> str:
    """Lower-case, collapse whitespace, and expand abbreviations.

    Args:
        query: Raw user query string.

    Returns:
        Normalised query with abbreviated terms expanded.
    """
    normalized = " ".join(query.lower().split())
    for short, expanded in ABBREVIATION_EXPANSIONS.items():
        normalized = re.sub(rf"\b{re.escape(short)}\b", expanded, normalized)
    return normalized


# ---------------------------------------------------------------------------
# Negation extraction
# ---------------------------------------------------------------------------


def extract_negations(query: str) -> List[str]:
    """Identify terms the user explicitly wants to *exclude*.

    Handles patterns such as:
    - ``"not management"``
    - ``"don't want director"``
    - ``"neither executive nor vp"``
    - ``"less onsite"``

    Args:
        query: Normalised query string.

    Returns:
        De-duplicated list of negated terms in discovery order.
    """
    normalized = query.lower().replace("\u2019", "'")
    normalized = re.sub(
        r"\b(don't|doesn't|didn't|can't|won't|shouldn't|isn't|aren't)\b",
        lambda m: m.group(1).replace("'", ""),
        normalized,
    )
    negations: List[str] = []

    terms_by_length = sorted(NEGATION_TERMS, key=len, reverse=True)
    cue_pattern = "|".join(re.escape(cue) for cue in NEGATION_CUES)

    # Match "<cue> ... <known term>" with up to 2 intervening words
    for term in terms_by_length:
        term_pattern = re.escape(term)
        if re.search(rf"\b(?:{cue_pattern})\b(?:\s+\w+){{0,2}}\s+{term_pattern}\b", normalized):
            negations.append(term)

    # "neither X nor Y" constructs
    for match in re.finditer(
        r"\bneither\s+([a-z][a-z\s\-]{1,40}?)\s+nor\s+([a-z][a-z\s\-]{1,40})\b",
        normalized,
    ):
        left, right = match.group(1), match.group(2)
        for side in (left, right):
            for term in terms_by_length:
                if re.search(rf"\b{re.escape(term)}\b", side):
                    negations.append(term)

    # Catch-all: "<cue> <single-word>" not in noise lists
    for match in re.finditer(rf"\b(?:{cue_pattern})\b\s+([a-z\-]{{3,}})", normalized):
        candidate = match.group(1)
        if candidate in STOPWORDS:
            continue
        if candidate in NEGATION_NOISE_TOKENS:
            continue
        if candidate in {"role", "roles", "job", "jobs", "work", "position", "positions"}:
            continue
        negations.append(candidate)

    return list(dict.fromkeys(negations))


# ---------------------------------------------------------------------------
# Location extraction
# ---------------------------------------------------------------------------


def extract_location_terms(query: str) -> List[str]:
    """Pull location phrases from ``in/near/around/within <place>`` patterns.

    Guards against false positives like "in data science" by checking
    ``NON_LOCATION_PHRASES`` and ``NON_LOCATION_TOKENS``.

    Args:
        query: Raw (or normalised) query string.

    Returns:
        De-duplicated list of probable location strings.
    """
    matches = re.findall(r"\b(?:in|near|around|within)\s+([a-zA-Z\s,]{2,40})", query)
    locations: List[str] = []
    for raw_match in matches:
        candidate = re.split(r"\b(?:with|for|that|who|where|and|or|not)\b", raw_match)[0]
        candidate = " ".join(candidate.strip(" ,.").split())
        if not candidate:
            continue
        if any(phrase in candidate for phrase in NON_LOCATION_PHRASES):
            continue
        words = re.findall(r"[a-zA-Z]+", candidate)
        if not words or len(words) > 4:
            continue
        if len(words) == 1 and words[0] in STOPWORDS:
            continue
        if any(word in NON_LOCATION_TOKENS for word in words):
            continue
        locations.append(" ".join(words))
    return list(dict.fromkeys(locations))


# ---------------------------------------------------------------------------
# Signal assembly
# ---------------------------------------------------------------------------


def parse_signals(query: str) -> SearchSignals:
    """Convert a raw query into a structured ``SearchSignals`` object.

    Orchestrates tokenisation, abbreviation expansion, negation detection,
    seniority/remote/org-type extraction, and location parsing.

    Args:
        query: The user's natural-language search query.

    Returns:
        A ``SearchSignals`` instance consumed by retrieval and ranking.
    """
    normalized_query = normalize_query(query)
    tokens = tokenize(normalized_query)
    negated_terms = extract_negations(normalized_query)
    tokens = [token for token in tokens if token not in negated_terms]

    seniority = next((s for s in SENIORITY if s in tokens), None)
    org_types = [o for o in ORG_TYPES if o in normalized_query]
    if any(term in normalized_query for term in MISSION_QUERY_TERMS) and "mission-driven" not in org_types:
        org_types.append("mission-driven")

    remote = (
        "remote" in normalized_query
        or "work from home" in normalized_query
        or "wfh" in normalized_query
        or "anywhere" in normalized_query
    )
    location_terms = extract_location_terms(normalized_query)

    return SearchSignals(
        keywords=tokens,
        excluded_keywords=negated_terms,
        remote=remote,
        seniority=seniority,
        org_types=org_types,
        location_terms=location_terms,
    )


def merge_signals(base: SearchSignals, incoming: SearchSignals) -> SearchSignals:
    """Union two signal sets, preserving sticky values from the base turn.

    Used during multi-turn refinement so that earlier intent (e.g. remote,
    seniority) is not lost when the user adds new constraints.

    Args:
        base: Signals accumulated from previous turns.
        incoming: Signals parsed from the latest refinement query.

    Returns:
        A merged ``SearchSignals`` with de-duplicated lists.
    """
    return SearchSignals(
        keywords=list(dict.fromkeys([*base.keywords, *incoming.keywords])),
        excluded_keywords=list(dict.fromkeys([*base.excluded_keywords, *incoming.excluded_keywords])),
        remote=base.remote or incoming.remote,
        seniority=incoming.seniority or base.seniority,
        org_types=list(dict.fromkeys([*base.org_types, *incoming.org_types])),
        location_terms=list(dict.fromkeys([*base.location_terms, *incoming.location_terms])),
    )
