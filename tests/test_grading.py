from __future__ import annotations

from backend.core.grading import grade_answer


def test_exact_and_case_insensitive_match() -> None:
    res = grade_answer("erie canal", "ERIE CANAL")
    assert res.correct is True
    assert res.best_score == 1.0


def test_typo_tolerance() -> None:
    res = grade_answer("Ursula LeGuin", "URSULA K. LE GUIN")
    assert res.correct is True
    assert res.best_score > 0.6


def test_alternate_slash_and_parentheses() -> None:
    assert grade_answer("nur-sultan", "ASTANA / NUR-SULTAN").correct is True
    assert grade_answer("astana", "ASTANA / NUR-SULTAN").correct is True
    assert grade_answer("neon", "NEON (Ne)").correct is True


def test_short_substring_and_wrong_answer_rejected() -> None:
    assert grade_answer("a", "ASTANA").correct is False
    assert grade_answer("z", "VERTIGO").correct is False
    assert grade_answer("citizen kane", "VERTIGO").correct is False
    assert grade_answer("", "VERTIGO").correct is False
