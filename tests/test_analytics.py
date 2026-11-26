from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from backend.core.analytics import (
    build_similarity_radar,
    calculate_hun,
    expected_opponent_points,
    generate_mock_day,
    parse_leaguewide_csv,
    recommend_defense,
    run_luck_analysis,
    smoothed_category_prob,
)
from backend.core.constants import CATEGORIES

FIXTURES = Path(__file__).parent / "fixtures"


def test_recommend_defense_orders_points_correctly() -> None:
    opp_metrics = {
        "SCIENCE": {"percent": 0.90},
        "ART": {"percent": 0.25},
        "FILM": {"percent": 0.50},
        "MATH": {"percent": 0.80},
        "GEOGRAPHY": {"percent": 0.40},
        # WORLD HIST intentionally omitted -> treated as 0.0%
    }
    cats = ["SCIENCE", "ART", "FILM", "MATH", "GEOGRAPHY", "WORLD HIST"]
    recs = recommend_defense(cats, opp_metrics)
    pts_by_cat = {r["category"]: r["recommended_points"] for r in recs}

    assert pts_by_cat["WORLD HIST"] == 3
    assert pts_by_cat["ART"] == 2
    assert pts_by_cat["GEOGRAPHY"] == 2
    assert pts_by_cat["FILM"] == 1
    assert pts_by_cat["MATH"] == 1
    assert pts_by_cat["SCIENCE"] == 0
    assert recs[0]["estimated_ground_truth_pct"] is None
    assert recs[0]["difficulty"] is None


def test_recommend_defense_irt_logit_shift_and_shrinkage() -> None:
    # Strong player in SCIENCE (90%), average in ART/MATH/FILM/GEOGRAPHY/HISTORY
    player_metrics = {
        "SCIENCE": {"correct": 90, "total": 100, "percent": 0.90},
        "ART": {"correct": 50, "total": 100, "percent": 0.50},
        "MATH": {"correct": 50, "total": 100, "percent": 0.50},
        "FILM": {"correct": 50, "total": 100, "percent": 0.50},
        "GEOGRAPHY": {"correct": 50, "total": 100, "percent": 0.50},
        "WORLD HIST": {"correct": 50, "total": 100, "percent": 0.50},
    }
    # Opponent is 80% in SCIENCE, 50% in ART, and 0/1 (0%) in FILM (small sample!)
    opp_metrics = {
        "SCIENCE": {"correct": 80, "total": 100, "percent": 0.80},
        "ART": {"correct": 50, "total": 100, "percent": 0.50},
        "MATH": {"correct": 50, "total": 100, "percent": 0.50},
        "FILM": {"correct": 0, "total": 1, "percent": 0.00},
        "GEOGRAPHY": {"correct": 50, "total": 100, "percent": 0.50},
        "WORLD HIST": {"correct": 50, "total": 100, "percent": 0.50},
    }
    cats = ["SCIENCE", "ART", "MATH", "FILM", "GEOGRAPHY", "WORLD HIST"]

    # Empirical Bayes shrinkage pulls small-sample 0/1 toward overall ~64.7%
    p_film = smoothed_category_prob(opp_metrics, "FILM", prior_weight=8.0)
    assert 0.45 < p_film < 0.70

    # Player rates SCIENCE as Medium (3 = 50%). Since player is 90% in SCIENCE,
    # inferred ground-truth difficulty is much harder (< 50%), pulling opponent down below 50%.
    # Meanwhile ART is rated Gimme (1 = 90%) -> opponent very likely gets it (0 pts).
    diffs = [3, 1, 3, 2, 4, 5]
    recs = recommend_defense(
        cats,
        opp_metrics,
        player_metrics=player_metrics,
        difficulties=diffs,
        prior_weight=8.0,
    )
    by_cat = {r["category"]: r for r in recs}

    assert by_cat["SCIENCE"]["estimated_ground_truth_pct"] is not None
    assert by_cat["SCIENCE"]["estimated_ground_truth_pct"] < 20.0
    assert by_cat["SCIENCE"]["estimated_opponent_pct"] < 50.0
    assert by_cat["ART"]["recommended_points"] == 0  # Gimme for 50% opponent
    assert by_cat["WORLD HIST"]["recommended_points"] == 3  # Stumper (10%)
    assert expected_opponent_points(recs) > 0.0


def test_recommend_defense_mixed_slots_and_invalid_difficulty() -> None:
    opp_metrics = {
        c: {"correct": 50, "total": 100, "percent": 0.50}
        for c in ["SCIENCE", "ART", "FILM", "MATH", "GEOGRAPHY", "WORLD HIST"]
    }
    cats = ["SCIENCE", "ART", "FILM", "MATH", "GEOGRAPHY", "WORLD HIST"]
    recs = recommend_defense(
        cats,
        opp_metrics,
        difficulties=[5, None, 1, None, None, None],
    )
    by_cat = {r["category"]: r for r in recs}
    assert by_cat["SCIENCE"]["recommended_points"] == 3
    assert by_cat["SCIENCE"]["difficulty"] == 5
    assert by_cat["SCIENCE"]["estimated_ground_truth_pct"] is not None
    assert by_cat["ART"]["difficulty"] is None
    assert by_cat["ART"]["estimated_ground_truth_pct"] is None
    assert by_cat["FILM"]["recommended_points"] == 0

    with pytest.raises(ValueError, match="between 1 and 5"):
        recommend_defense(cats, opp_metrics, difficulties=[6, 3, 3, 3, 3, 3])
    with pytest.raises(ValueError, match="exactly 6"):
        recommend_defense(cats, opp_metrics, difficulties=[1, 2, 3])


def test_calculate_hun_and_radar() -> None:
    q1 = {
        "S109D01Q1": {"correct": True},
        "S109D01Q2": {"correct": False},
        "S109D01Q3": {"correct": True},
    }
    q2 = {
        "S109D01Q1": {"correct": True},
        "S109D01Q2": {"correct": True},
        "S109D01Q4": {"correct": True},
    }
    hun = calculate_hun(q1, q2)
    assert hun["shared_questions"] == 2
    assert hun["matching_outcomes"] == 1
    assert hun["score"] == 0.5

    radar = build_similarity_radar(
        {"SCIENCE": {"percent": 0.8}},
        {"SCIENCE": {"percent": 0.4}},
    )
    assert len(radar) >= len(CATEGORIES)
    sci = next(item for item in radar if item["category"] == "SCIENCE")
    assert sci["player1_pct"] == 80.0
    assert sci["player2_pct"] == 40.0


def test_generate_mock_day_deterministic_and_cross_platform() -> None:
    pool = [
        {"qcode": f"S100D01Q{i}", "percent": 10 * i, "question": f"Q{i}", "answer": f"A{i}"}
        for i in range(1, 10)
    ]
    d1 = generate_mock_day(pool, seed=42, threshold=20, day_date=date(2026, 5, 1))
    d2 = generate_mock_day(pool, seed=42, threshold=20, day_date=date(2026, 5, 1))
    assert d1["uuid"] == d2["uuid"]
    assert [q["qcode"] for q in d1["questions"]] == [q["qcode"] for q in d2["questions"]]
    assert all(q["percent"] > 20 for q in d1["questions"])
    assert sorted(q["assigned_point"] for q in d1["questions"]) == [0, 1, 1, 2, 2, 3]


def test_luck_analysis_with_sos_rundle_ratios_and_missing_user() -> None:
    csv_text = (FIXTURES / "lgwide.csv").read_text(encoding="utf-8")
    df = parse_leaguewide_csv(csv_text)

    res = run_luck_analysis(
        df,
        usernames=["aliceplayer", "bobopp", "NonExistentUser"],
        extra_fields=["OE", "MPD"],
        rundle_flag=False,
        use_sos=True,
        divide_pairs=[("TMP", "TCA")],
    )
    assert res["matched_usernames"] == ["AlicePlayer", "BobOpp"]
    assert res["missing_usernames"] == ["NonExistentUser"]
    assert "TMP/TCA" in res["columns"]
    assert "OE" in res["columns"]
    assert len(res["rows"]) == 2
    assert 0.0 <= res["r_squared"] <= 1.0

    # Display full rundle for matched user
    res_rundle = run_luck_analysis(
        df,
        usernames=["AlicePlayer"],
        rundle_flag=True,
        use_sos=False,
    )
    assert len(res_rundle["rows"]) == 6
    assert all(r["Rundle"] == "B_East" for r in res_rundle["rows"])
