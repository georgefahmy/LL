from __future__ import annotations

import re
from dataclasses import dataclass

from rapidfuzz import fuzz

_SPLIT_RE = re.compile(r"[^/,()]+")
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class GradeResult:
    correct: bool
    best_score: float
    matched_variant: str | None
    variants: list[str]


def _normalize(text: str) -> str:
    return _WS_RE.sub(" ", text.strip().lower())


def extract_answer_variants(correct_answer: str) -> list[str]:
    raw_parts = [part.strip() for part in _SPLIT_RE.findall(correct_answer) if part.strip()]
    if raw_parts:
        variants = raw_parts
    elif correct_answer.strip():
        variants = [correct_answer.strip()]
    else:
        variants = []
    seen: set[str] = set()
    unique: list[str] = []
    for v in variants:
        key = _normalize(v)
        if key and key not in seen:
            seen.add(key)
            unique.append(v)
    return unique


def grade_answer(
    submitted: str,
    correct_answer: str,
    *,
    threshold_partial: float = 0.6,
    threshold_token_sort: float = 0.6,
) -> GradeResult:
    """Fuzzy-grade a trivia answer against accepted variants."""
    sub_norm = _normalize(submitted)
    variants = extract_answer_variants(correct_answer)
    if not sub_norm or not variants:
        return GradeResult(
            correct=False,
            best_score=0.0,
            matched_variant=None,
            variants=variants,
        )

    best_score = 0.0
    matched_variant: str | None = None
    is_correct = False

    for variant in variants:
        var_norm = _normalize(variant)
        if sub_norm == var_norm:
            return GradeResult(
                correct=True,
                best_score=1.0,
                matched_variant=variant,
                variants=variants,
            )

        partial_sim = fuzz.partial_ratio(sub_norm, var_norm) / 100.0
        token_sim = fuzz.token_sort_ratio(sub_norm, var_norm) / 100.0
        candidate_best = max(partial_sim, token_sim)

        if candidate_best > best_score:
            best_score = candidate_best

        # Guard partial_ratio against trivial 1-2 character substrings
        partial_ok = (len(sub_norm) >= 3 or len(var_norm) <= 3) and partial_sim > threshold_partial
        token_ok = token_sim > threshold_token_sort

        if partial_ok or token_ok:
            is_correct = True
            matched_variant = variant

    return GradeResult(
        correct=is_correct,
        best_score=round(best_score, 4),
        matched_variant=matched_variant,
        variants=variants,
    )
