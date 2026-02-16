"""Search-engine constants, tuning weights, and curated vocabulary lists.

This module centralises every hard-coded value used by the retrieval and
ranking pipeline so that the rest of the search code stays focused on logic.

Sections
--------
- **Scoring weights** – vector/keyword blend, signal boosts, penalties.
- **Retrieval knobs** – candidate pool sizes, rerank window, multi-query caps.
- **Stopwords & seniority** – basic NLP vocabularies.
- **Abbreviation expansions** – common role-domain shorthands (ml → machine learning).
- **Mission-driven lists** – query-level, content-level, and org-name patterns
  used to detect mission-driven intent and boost matching results.
- **Negation / exclusion vocabularies** – terms, cues, noise tokens, and
  variant expansions for the hard-exclusion filter.
- **Location guard lists** – phrases and tokens that look like locations but
  are actually role/domain terms (e.g. "data science").
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Scoring weights – control how vector, keyword, and signal scores are blended
# ---------------------------------------------------------------------------

VECTOR_WEIGHT = 0.65
"""Weight applied to the cosine-similarity score from FAISS."""

KEYWORD_WEIGHT = 0.25
"""Weight applied to the keyword-coverage ratio from DuckDB."""

MAX_SIGNAL_BOOST = 0.30
"""Hard ceiling on the total additive signal boost per candidate."""

REMOTE_BOOST = 0.15
"""Additive boost when the user wants remote and the listing mentions it."""

SENIORITY_BOOST = 0.10
"""Additive boost when the detected seniority level appears in the listing."""

ORG_TYPE_BOOST = 0.05
"""Additive boost for matching organisation type (nonprofit, startup, etc.)."""

LOCATION_BOOST = 0.05
"""Additive boost when a parsed location term appears in the listing."""

MISSION_BOOST = 0.05
"""Additive boost for mission-driven matches (content terms + org patterns)."""

NEGATION_PENALTY = 0.20
"""Per-term penalty subtracted when an excluded keyword still appears."""

# ---------------------------------------------------------------------------
# Retrieval knobs – control candidate pool sizes and multi-query behaviour
# ---------------------------------------------------------------------------

VECTOR_SEARCH_MULTIPLIER = 10
"""Multiply top_k by this to get the initial FAISS retrieval window."""

MAX_VECTOR_CANDIDATES = 500
"""Absolute cap on the number of FAISS candidates per query."""

KEYWORD_SEARCH_MULTIPLIER = 25
"""Multiply top_k by this to size the DuckDB keyword fallback pool."""

MAX_KEYWORD_CANDIDATES = 1000
"""Absolute cap on DuckDB keyword candidates."""

MAX_MULTI_QUERIES = 4
"""Maximum number of distinct retrieval query rewrites."""

MULTI_QUERY_HIT_BONUS = 0.02
"""Score bonus for each additional multi-query that retrieves the same row."""

RERANK_TOP_N = 40
"""Number of top candidates passed through the lightweight reranker."""

RERANK_BLEND = 0.20
"""Blending factor for the reranker's adjustment into the final score."""

EMBEDDING_CACHE_SIZE = 256
"""LRU cache slots for deduplicated embedding calls."""

# ---------------------------------------------------------------------------
# Confidence thresholds – detect low-quality result sets for retry logic
# ---------------------------------------------------------------------------

CONFIDENCE_MIN_TOP_SCORE = 0.30
"""Top-1 score below this triggers the low-confidence retry path."""

CONFIDENCE_MIN_SPREAD = 0.03
"""Score spread (top − bottom of window) below this flags low confidence."""

CONFIDENCE_TOP_WINDOW = 5
"""Number of top results inspected when computing confidence metrics."""

# ---------------------------------------------------------------------------
# Stopwords – removed during tokenisation to focus on meaningful terms
# ---------------------------------------------------------------------------

STOPWORDS = {
    "a", "an", "the", "for", "with", "and", "or", "to", "of", "in", "on",
    "at", "jobs", "job", "role", "roles", "position", "positions", "looking",
    "want", "find", "show", "me", "some", "please", "need", "something",
    "i", "am", "interested", "not",
}

# ---------------------------------------------------------------------------
# Seniority / org-type enums
# ---------------------------------------------------------------------------

SENIORITY = ["intern", "junior", "mid", "senior", "staff", "principal", "lead"]
"""Recognised seniority levels parsed from queries."""

ORG_TYPES = ["nonprofit", "non-profit", "ngo", "startup", "government", "public"]
"""Organisation types that trigger an org-type signal boost."""

# ---------------------------------------------------------------------------
# Abbreviation expansions – expand short-hands before embedding
# ---------------------------------------------------------------------------

ABBREVIATION_EXPANSIONS = {
    "ml": "machine learning",
    "ds": "data science",
    "swe": "software engineer",
    "ai": "artificial intelligence",
    "pm": "product manager",
}

# ---------------------------------------------------------------------------
# Mission-driven vocabularies
# ---------------------------------------------------------------------------

MISSION_QUERY_TERMS = [
    "social good", "mission driven", "mission-driven", "social impact",
    "public benefit", "purpose driven", "purpose-driven", "do good",
    "make a difference", "give back", "help people", "help communities",
    "socially responsible",
]
"""Phrases in the *query* that signal mission-driven intent."""

MISSION_MATCH_TERMS = [
    "social good", "mission", "impact", "equity", "community", "climate",
    "sustainability", "public benefit", "nonprofit", "non-profit", "ngo",
    "humanitarian", "advocacy", "civic", "social services", "social work",
    "human services", "public health", "public interest", "philanthropy",
    "charitable", "underserved", "vulnerable populations",
    "workforce development",
]
"""Content-level terms matched against title / preview / company text."""

MISSION_ORG_PATTERNS = [
    "volunteers of america", "catholic charities", "salvation army",
    "goodwill", "ymca", "ywca", "boys & girls club",
    "boys and girls club", "united way", "habitat for humanity",
    "planned parenthood", "americorps", "sierra club", "red cross",
    "peace corps", "teach for america", "surfrider foundation",
    "mellon foundation", "community health", "community legal aid",
    "community partners", "community care",
]
"""Known mission-driven org-name fragments mined from the dataset."""

# ---------------------------------------------------------------------------
# Negation / exclusion vocabularies
# ---------------------------------------------------------------------------

NEGATION_TERMS = {
    "management", "managerial", "people management", "manager", "managers",
    "leadership", "director", "directors", "executive", "executives", "vp",
    "onsite", "on-site",
}
"""Canonical terms that can appear after a negation cue."""

NEGATION_CUES = [
    "not", "no", "without", "exclude", "excluding", "except", "avoid",
    "never", "dont", "do not", "doesnt", "does not", "didnt", "did not",
    "shouldnt", "should not", "cannot", "cant", "will not", "wont",
    "less", "fewer",
]
"""Linguistic cues that precede a negated term."""

NEGATION_NOISE_TOKENS = {
    "include", "including", "exclude", "excluding", "show", "list", "give",
    "want", "need", "prefer", "more", "less",
}
"""Tokens that look like negation targets but are noise (e.g. 'don't include')."""

EXCLUSION_VARIANTS = {
    "management": ["management", "manager", "managers", "managerial", "people management"],
    "manager": ["manager", "managers", "management", "managerial"],
    "director": ["director", "directors", "director-level"],
    "executive": ["executive", "executives", "exec", "c-suite", "c suite", "vp", "vice president"],
    "vp": ["vp", "vice president", "vice-president"],
    "onsite": ["onsite", "on-site", "in office", "in-office"],
}
"""Maps an excluded term to all morphological variants for hard filtering."""

# ---------------------------------------------------------------------------
# Location guard lists – prevent false-positive location extraction
# ---------------------------------------------------------------------------

NON_LOCATION_PHRASES = {
    "data science", "machine learning", "software engineering",
    "product management", "social good", "mission driven",
}
"""Multi-word phrases that should never be parsed as a location."""

NON_LOCATION_TOKENS = {
    "job", "jobs", "role", "roles", "engineering", "management",
    "manager", "science",
}
"""Single tokens whose presence disqualifies a candidate location phrase."""
