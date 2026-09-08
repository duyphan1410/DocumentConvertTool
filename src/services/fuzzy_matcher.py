"""
Vietnamese Fuzzy Matcher Service.
Author: Huy (Algorithm & Fuzzy Matching Engine)
PKB Phase 1 (v1.10.0) — High Precision Vietnamese Diacritic Invariant & Token Similarity Engine.
"""
from __future__ import annotations
import difflib
import re
import unicodedata
from typing import Optional, List, Tuple


def normalize_vietnamese(text: str) -> str:
    """
    Normalizes Vietnamese text by stripping diacritics (NFD decomposition),
    converting 'đ'/'Đ' to 'd'/'D', removing non-alphanumeric characters, and collapsing whitespace.
    """
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    ascii_text = ''.join(c for c in nfkd if not unicodedata.combining(c))
    ascii_text = ascii_text.replace('đ', 'd').replace('Đ', 'D')
    # Replace non-alphanumeric characters with space
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', ' ', ascii_text).lower().strip()
    return re.sub(r'\s+', ' ', cleaned)


def tokenize_vietnamese(text: str) -> List[str]:
    """
    Tokenizes normalized Vietnamese text into distinct word tokens.
    """
    normalized = normalize_vietnamese(text)
    return [t for t in normalized.split() if t]


def calculate_similarity(s1: str, s2: str) -> float:
    """
    Calculates similarity score (0.0 to 1.0) between two Vietnamese strings.
    Blends exact character match, normalized match, prefix bonus, token-sort, and SequenceMatcher.
    """
    if not s1 or not s2:
        return 0.0
    if s1 == s2:
        return 1.0

    norm1 = normalize_vietnamese(s1)
    norm2 = normalize_vietnamese(s2)

    if not norm1 or not norm2:
        return 0.0
    if norm1 == norm2:
        return 0.98

    # 1. Prefix containment bonus (crucial for auto-complete typing)
    if norm1.startswith(norm2) or norm2.startswith(norm1):
        len_ratio = min(len(norm1), len(norm2)) / max(len(norm1), len(norm2))
        prefix_score = 0.85 + (0.13 * len_ratio)
    elif norm2 in norm1 or norm1 in norm2:
        len_ratio = min(len(norm1), len(norm2)) / max(len(norm1), len(norm2))
        prefix_score = 0.75 + (0.15 * len_ratio)
    else:
        prefix_score = 0.0

    # 2. Character SequenceMatcher
    seq_ratio = difflib.SequenceMatcher(None, norm1, norm2).ratio()

    # 3. Token-based matching (Token-Sort & Token-Set)
    tokens1 = tokenize_vietnamese(s1)
    tokens2 = tokenize_vietnamese(s2)

    token_score = 0.0
    if tokens1 and tokens2:
        sorted1 = " ".join(sorted(tokens1))
        sorted2 = " ".join(sorted(tokens2))
        token_sort_ratio = difflib.SequenceMatcher(None, sorted1, sorted2).ratio()

        set1 = set(tokens1)
        set2 = set(tokens2)
        intersection = set1.intersection(set2)
        union = set1.union(set2)
        jaccard = len(intersection) / len(union) if union else 0.0

        token_score = max(token_sort_ratio, jaccard)

    # Return composite max score
    return round(max(prefix_score, seq_ratio, token_score), 4)


def rank_candidates(
    query: str,
    candidates: List[str],
    limit: int = 15,
    min_threshold: float = 0.35,
) -> List[Tuple[str, float]]:
    """
    Ranks a list of candidate strings against `query` using fuzzy similarity scoring.
    Returns sorted list of (candidate, score) tuples in descending order.
    """
    if not query or not candidates:
        return []

    norm_query = normalize_vietnamese(query)
    scored_candidates: List[Tuple[str, float]] = []

    for cand in candidates:
        if not cand:
            continue
        # Exact match gets 1.0
        if cand == query:
            score = 1.0
        elif normalize_vietnamese(cand) == norm_query:
            score = 0.98
        else:
            score = calculate_similarity(query, cand)

        if score >= min_threshold:
            scored_candidates.append((cand, score))

    # Sort primarily by score descending, secondarily by candidate length (prefer shorter exact matches)
    scored_candidates.sort(key=lambda item: (-item[1], len(item[0]), item[0]))
    return scored_candidates[:limit]


def resolve_candidate(
    query: str,
    candidates: List[str],
    threshold: float = 0.70,
) -> Optional[str]:
    """
    Finds the single best candidate string that exceeds the similarity `threshold`.
    Returns None if no candidate satisfies the threshold.
    """
    ranked = rank_candidates(query, candidates, limit=1, min_threshold=threshold)
    return ranked[0][0] if ranked else None


def find_fuzzy_substring_occurrences(
    text: str,
    target: str,
    min_similarity: float = 0.85,
) -> List[Tuple[int, int, str, float]]:
    """
    Finds substring occurrences in `text` that match `target` with Vietnamese fuzzy similarity.
    Returns list of (start_index, end_index, matched_substring, similarity_score).
    """
    if not text or not target or len(target) < 2:
        return []

    target_tokens = tokenize_vietnamese(target)
    if not target_tokens:
        return []

    target_word_count = len(target_tokens)
    target_norm = " ".join(target_tokens)

    results: List[Tuple[int, int, str, float]] = []

    # 1. Exact character scan (fast path)
    exact_pattern = re.compile(re.escape(target), re.IGNORECASE)
    for m in exact_pattern.finditer(text):
        results.append((m.start(), m.end(), m.group(0), 1.0))

    # 2. Sliding window scan over word tokens with exact word count alignment
    words_with_spans = [(m.start(), m.end(), m.group(0)) for m in re.finditer(r'\S+', text)]
    total_words = len(words_with_spans)

    if total_words >= target_word_count:
        for i in range(total_words - target_word_count + 1):
            start_span = words_with_spans[i][0]
            end_span = words_with_spans[i + target_word_count - 1][1]

            # Strip trailing punctuation from end_span
            raw_sub = text[start_span:end_span]
            sub_tokens = tokenize_vietnamese(raw_sub)
            if len(sub_tokens) != target_word_count:
                continue

            sub_norm = " ".join(sub_tokens)
            if sub_norm == target_norm:
                sim = 0.98
            else:
                sim = difflib.SequenceMatcher(None, sub_norm, target_norm).ratio()

            if sim >= min_similarity:
                results.append((start_span, end_span, raw_sub, round(sim, 4)))

    # Deduplicate overlapping spans (keep highest score)
    if not results:
        return []

    results.sort(key=lambda r: (r[0], -r[3]))
    deduped: List[Tuple[int, int, str, float]] = []
    for r in results:
        # Check if overlaps with last accepted span
        if not deduped:
            deduped.append(r)
            continue
        last_s, last_e, _, last_score = deduped[-1]
        curr_s, curr_e, _, curr_score = r
        if curr_s < last_e:
            if curr_score > last_score:
                deduped[-1] = r
        else:
            deduped.append(r)

    return deduped

