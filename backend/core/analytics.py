from __future__ import annotations

import calendar
import io
import math
import random
import uuid
from datetime import UTC, date, datetime
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import rankdata
from statsmodels.formula.api import ols

from .constants import CATEGORIES, DEFAULT_LUCK_FIELDS, LUCK_FIELDS

_MOCK_NAMESPACE = uuid.UUID(int=1)
_POINT_ALLOCATION = [3, 2, 2, 1, 1, 0]
DIFFICULTY_PROBS: dict[int, float] = {
    1: 0.90,  # Gimme
    2: 0.75,  # Easy
    3: 0.50,  # Medium
    4: 0.25,  # Hard
    5: 0.10,  # Stumper
}
DEFAULT_PRIOR_WEIGHT: float = 8.0
_PROB_EPS: float = 0.01


def _clamp_prob(p: float) -> float:
    return min(1.0 - _PROB_EPS, max(_PROB_EPS, float(p)))


def _logit(p: float) -> float:
    clamped = _clamp_prob(p)
    return math.log(clamped / (1.0 - clamped))


def _sigmoid(x: float) -> float:
    if x >= 0.0:
        return 1.0 / (1.0 + math.exp(-x))
    exp_x = math.exp(x)
    return exp_x / (1.0 + exp_x)


def _lookup_category_metric(
    metrics: dict[str, dict[str, Any]],
    category: str,
) -> dict[str, Any]:
    cat = category.strip()
    metric = metrics.get(cat) or {}
    if not metric:
        cat_upper = cat.upper()
        for key, val in metrics.items():
            if key.upper() == cat_upper:
                return val or {}
    return metric


def overall_player_accuracy(metrics: dict[str, dict[str, Any]]) -> float:
    """Compute weighted career accuracy across categories, defaulting to 0.50."""
    if not metrics:
        return 0.50
    total_correct = 0.0
    total_answered = 0.0
    pct_values: list[float] = []
    for val in metrics.values():
        if not isinstance(val, dict):
            continue
        tot = float(val.get("total", 0) or 0)
        if tot > 0:
            total_answered += tot
            total_correct += float(val.get("correct", 0) or 0)
        elif val.get("percent") is not None:
            pct_values.append(float(val["percent"]))
    if total_answered > 0:
        return _clamp_prob(total_correct / total_answered)
    if pct_values:
        return _clamp_prob(sum(pct_values) / len(pct_values))
    return 0.50


def smoothed_category_prob(
    metrics: dict[str, dict[str, Any]],
    category: str,
    *,
    prior_weight: float = DEFAULT_PRIOR_WEIGHT,
) -> float:
    """Empirical Bayes shrunk category accuracy toward the player's overall accuracy."""
    overall_acc = overall_player_accuracy(metrics)
    metric = _lookup_category_metric(metrics, category)
    if metric:
        total = float(metric.get("total", 0) or 0)
        if total > 0:
            correct = float(metric.get("correct", 0) or 0)
            prob = (correct + prior_weight * overall_acc) / (total + prior_weight)
            return _clamp_prob(prob)
        if metric.get("percent") is not None:
            return _clamp_prob(float(metric["percent"]))
    return _clamp_prob(overall_acc)


def expected_opponent_points(recommendations: list[dict[str, Any]]) -> float:
    """Compute sum(recommended_points * estimated_opponent_prob) rounded to 2 decimals."""
    total = sum(
        float(r["recommended_points"]) * (float(r["estimated_opponent_pct"]) / 100.0)
        for r in recommendations
    )
    return round(total, 2)


def recommend_defense(
    categories: list[str],
    opponent_metrics: dict[str, dict[str, Any]],
    *,
    player_metrics: dict[str, dict[str, Any]] | None = None,
    difficulties: list[int | None] | None = None,
    prior_weight: float = DEFAULT_PRIOR_WEIGHT,
) -> list[dict[str, Any]]:
    """Assign [3, 2, 2, 1, 1, 0] points using Empirical-Bayes Logit IRT or category % fallback."""
    if len(categories) != 6:
        raise ValueError("Exactly 6 question categories are required.")

    if difficulties is not None:
        if len(difficulties) != 6:
            raise ValueError("Difficulties list must have exactly 6 entries.")
        for d in difficulties:
            if d is not None and (isinstance(d, bool) or not isinstance(d, int) or d < 1 or d > 5):
                raise ValueError("Each difficulty rating must be an integer between 1 and 5.")

    has_any_difficulty = bool(difficulties and any(d is not None for d in difficulties))

    slots: list[dict[str, Any]] = []
    for idx, raw_cat in enumerate(categories):
        cat = raw_cat.strip()
        opp_metric = _lookup_category_metric(opponent_metrics, cat)
        raw_opp_pct = round(float(opp_metric.get("percent", 0.0) or 0.0) * 100.0, 2)
        d = difficulties[idx] if difficulties is not None else None

        if not has_any_difficulty:
            estimated_opp_pct = raw_opp_pct
            estimated_truth_pct: float | None = None
            slot_diff: int | None = None
        else:
            p_opp_cat = smoothed_category_prob(
                opponent_metrics, cat, prior_weight=prior_weight
            )
            theta_opp = _logit(p_opp_cat)
            if d is None:
                estimated_opp_pct = round(p_opp_cat * 100.0, 2)
                estimated_truth_pct = None
                slot_diff = None
            else:
                p_me_q = DIFFICULTY_PROBS[d]
                theta_me = (
                    _logit(
                        smoothed_category_prob(
                            player_metrics, cat, prior_weight=prior_weight
                        )
                    )
                    if player_metrics
                    else 0.0
                )
                ground_truth_logit = _logit(p_me_q) - theta_me
                estimated_truth_pct = round(_sigmoid(ground_truth_logit) * 100.0, 2)
                opp_logit = ground_truth_logit + theta_opp
                estimated_opp_pct = round(_sigmoid(opp_logit) * 100.0, 2)
                slot_diff = d

        slots.append(
            {
                "slot": idx + 1,
                "category": cat,
                "opponent_percent": raw_opp_pct,
                "recommended_points": 0,
                "difficulty": slot_diff,
                "estimated_opponent_pct": estimated_opp_pct,
                "estimated_ground_truth_pct": estimated_truth_pct,
            }
        )

    sort_field = "estimated_opponent_pct" if has_any_difficulty else "opponent_percent"
    ordered = sorted(slots, key=lambda item: (item[sort_field], item["slot"]))
    for rank_idx, item in enumerate(ordered):
        item["recommended_points"] = _POINT_ALLOCATION[rank_idx]

    return slots


def calculate_hun(
    qhist_1: dict[str, dict[str, Any]],
    qhist_2: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Calculate Head-Up Number (HUN) overlap similarity between two players' question histories."""
    shared = 0
    matching = 0
    for qid, val1 in qhist_1.items():
        if qid in qhist_2:
            shared += 1
            if bool(val1.get("correct")) == bool(qhist_2[qid].get("correct")):
                matching += 1
    score = round(matching / shared, 4) if shared > 0 else 0.0
    return {
        "score": score,
        "shared_questions": shared,
        "matching_outcomes": matching,
    }


def build_similarity_radar(
    metrics_1: dict[str, dict[str, Any]],
    metrics_2: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Build aligned 18-category percentages (0..100) for two players."""
    all_cats = list(CATEGORIES)
    for extra in sorted(set(metrics_1.keys()) | set(metrics_2.keys())):
        if extra not in all_cats:
            all_cats.append(extra)

    points: list[dict[str, Any]] = []
    for cat in all_cats:
        p1 = float((metrics_1.get(cat) or {}).get("percent", 0.0) or 0.0) * 100.0
        p2 = float((metrics_2.get(cat) or {}).get("percent", 0.0) or 0.0) * 100.0
        points.append(
            {
                "category": cat,
                "player1_pct": round(p1, 2),
                "player2_pct": round(p2, 2),
            }
        )
    return points


def generate_mock_day(
    questions: list[dict[str, Any]],
    *,
    seed: int | None = None,
    threshold: int = 0,
    day_date: date | None = None,
) -> dict[str, Any]:
    """Generate a deterministic 6-question Mock Match Day (cross-platform safe)."""
    bounded_thresh = max(0, min(95, int(threshold)))
    eligible = [q for q in questions if int(q.get("percent", 0)) > bounded_thresh]
    if len(eligible) < 6:
        eligible = list(questions)
    if len(eligible) < 6:
        raise ValueError("Not enough questions available to generate a Mock Match Day.")

    target_date = day_date or datetime.now(UTC).date()
    day_epoch = calendar.timegm(target_date.timetuple())
    combined_seed = (int(seed) if seed is not None else 0) + day_epoch + bounded_thresh

    rng = random.Random(combined_seed)
    eligible_sorted = sorted(eligible, key=lambda q: str(q["qcode"]))
    chosen = rng.sample(eligible_sorted, 6)
    chosen_ordered_by_diff = sorted(chosen, key=lambda q: int(q.get("percent", 0)))

    assigned_by_qcode: dict[str, int] = {}
    for idx, item in enumerate(chosen_ordered_by_diff):
        assigned_by_qcode[str(item["qcode"])] = _POINT_ALLOCATION[idx]

    # Present in shuffled order while retaining assigned_point based on difficulty
    display_order = list(chosen)
    rng.shuffle(display_order)

    result_questions: list[dict[str, Any]] = []
    for idx, q in enumerate(display_order):
        q_copy = dict(q)
        q_copy["index"] = idx + 1
        q_copy["assigned_point"] = assigned_by_qcode[str(q["qcode"])]
        result_questions.append(q_copy)

    code = "-".join(sorted(str(q["qcode"]) for q in result_questions))
    match_uuid = str(uuid.uuid3(_MOCK_NAMESPACE, code))

    return {
        "uuid": match_uuid,
        "code": code,
        "date": target_date.isoformat(),
        "seed": seed,
        "threshold": bounded_thresh,
        "questions": result_questions,
    }


def parse_leaguewide_csv(csv_text: str) -> pd.DataFrame:
    """Parse LearnedLeague lgwide.php CSV safely across pandas versions."""
    if not csv_text or not csv_text.strip():
        raise ValueError("Empty league-wide CSV payload received.")

    df = pd.read_csv(io.StringIO(csv_text), low_memory=False)
    if "Player" not in df.columns:
        raise ValueError("CSV payload missing 'Player' column (session may have expired).")

    df = df.rename(
        columns={
            "Wins": "W",
            "Losses": "L",
            "Ties": "T",
            "Pts": "PTS",
            "Rundle Rank": "Rank",
        }
    )
    df["Player"] = df["Player"].astype(str).str.strip()
    df["Rundle"] = df["Rundle"].astype(str).str.strip()
    df = df[df["Player"].ne("") & df["Player"].ne("nan")].copy()
    df = df.replace(["--", np.inf, -np.inf], 0)

    numeric_cols = [
        "W",
        "L",
        "T",
        "PTS",
        "Rank",
        "MPD",
        "TMP",
        "TCA",
        "PCA",
        "UfPE",
        "OE",
        "QPct",
        "TPA",
        "CAA",
        "PCAA",
        "UfPA",
        "DE",
        "NUfP",
        "QPO",
        "QPD",
        "OPD",
        "FW",
        "FL",
        "3PT",
        "MCW",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    df = df.set_index("Player", drop=False)
    return df


def _safe_zscore(series: pd.Series) -> pd.Series:
    std = float(series.std())
    if not np.isfinite(std) or std == 0.0:
        return pd.Series(0.0, index=series.index)
    return (series - float(series.mean())) / std


def run_luck_analysis(
    df: pd.DataFrame,
    *,
    usernames: list[str] | None = None,
    extra_fields: list[str] | None = None,
    rundle_flag: bool = False,
    use_sos: bool = False,
    divide_pairs: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    """Compute OLS-based Expected Points, Luck, and Luck Percentile for a league-wide season."""
    work = df.copy()
    work["Level"] = work["Rundle"].astype(str).str[0]
    work["Matches"] = work["W"] + work["L"] + work["T"]
    work["Played"] = work["Matches"] - work["FL"]
    work["Player_count"] = work.groupby("Rundle")["Rundle"].transform("count")

    rundle_qpct_mean = work.groupby("Rundle")["QPct"].transform("mean")
    sos_denom = 6.0 * (work["Matches"] - work["FW"]) * rundle_qpct_mean
    work["SOS"] = np.where(sos_denom > 0, work["CAA"] / sos_denom, 0.0)

    normalize_vars = ["OE", "DE", "QPct", "CAA", "FL", "MPD", "TCA", "SOS"]
    for var in normalize_vars:
        if var in work.columns:
            work[f"norm_{var}"] = (
                work.groupby("Rundle")[var].transform(_safe_zscore).fillna(0.0)
            )

    terms = ["0", "Played", "norm_OE*FL", "norm_QPct*FL", "norm_DE"]
    if use_sos:
        terms.append("norm_SOS")
    formula = "PTS ~ " + " + ".join(terms)

    model = ols(formula, data=work).fit()
    mean_rundle_size = float(work.groupby("Rundle")["Player"].nunique().mean() or 1.0)

    work["Exp_PTS"] = pd.to_numeric(model.predict(work), errors="coerce").fillna(0.0)
    work = work.replace([np.inf, -np.inf], 0.0)
    work["Exp_Rank"] = (
        work.groupby("Rundle")["Exp_PTS"]
        .rank(ascending=False, method="dense")
        .fillna(1)
        .astype(int)
    )
    work["Luck"] = work["PTS"] - work["Exp_PTS"]
    work["Luck_Rank"] = (work["Exp_Rank"] - work["Rank"]).astype(int)
    work["Luck_Rank_adj"] = np.where(
        work["Player_count"] > 0,
        (work["Luck_Rank"] / work["Player_count"]) * mean_rundle_size,
        0.0,
    )
    work["LuckPctile"] = (
        rankdata(work["Luck_Rank_adj"], method="max") / max(1, len(work)) * 100.0
    ).round(2)

    fields = list(DEFAULT_LUCK_FIELDS)
    valid_extra = set(LUCK_FIELDS) | set(work.columns)
    for f in extra_fields or []:
        if f in valid_extra and f not in fields:
            fields.append(f)

    if divide_pairs:
        for num_col, den_col in divide_pairs:
            if num_col in work.columns and den_col in work.columns:
                ratio_name = f"{num_col}/{den_col}"
                num_vals = pd.to_numeric(work[num_col], errors="coerce").fillna(0.0)
                den_vals = pd.to_numeric(work[den_col], errors="coerce").fillna(0.0)
                work[ratio_name] = np.where(den_vals != 0, num_vals / den_vals, 0.0)
                if ratio_name not in fields:
                    fields.append(ratio_name)

    # Case-insensitive username resolution
    lower_to_actual = {str(p).lower(): str(p) for p in work["Player"].tolist()}
    requested = [u.strip() for u in (usernames or []) if u.strip()]
    matched_usernames: list[str] = []
    missing_usernames: list[str] = []
    for req in requested:
        actual = lower_to_actual.get(req.lower())
        if actual:
            if actual not in matched_usernames:
                matched_usernames.append(actual)
        else:
            missing_usernames.append(req)

    if rundle_flag and matched_usernames:
        rundles = work.loc[matched_usernames, "Rundle"].unique().tolist()
        if "Rundle" not in fields:
            fields.append("Rundle")
        filtered = work[work["Rundle"].isin(rundles)].sort_values(
            by=["Rundle", "LuckPctile"],
            ascending=[True, False],
        )
    elif matched_usernames:
        if "Rundle" not in fields:
            fields.append("Rundle")
        filtered = work.loc[matched_usernames].sort_values(
            by=["LuckPctile"],
            ascending=False,
        )
    else:
        if "Rundle" not in fields:
            fields.append("Rundle")
        filtered = work.sort_values(by=["LuckPctile"], ascending=False).head(250)

    selected_cols = [col for col in fields if col in filtered.columns]
    rows: list[dict[str, Any]] = []
    for _, row in filtered[selected_cols].iterrows():
        clean_row: dict[str, Any] = {}
        for col in selected_cols:
            val = row[col]
            if isinstance(val, (np.floating, float)):
                clean_row[col] = None if not math.isfinite(float(val)) else round(float(val), 3)
            elif isinstance(val, (np.integer, int)):
                clean_row[col] = int(val)
            else:
                clean_row[col] = str(val)
        rows.append(clean_row)

    r_squared = float(model.rsquared) if math.isfinite(float(model.rsquared)) else 0.0
    return {
        "columns": selected_cols,
        "rows": rows,
        "matched_usernames": matched_usernames,
        "missing_usernames": missing_usernames,
        "formula": formula,
        "r_squared": round(r_squared, 4),
        "total_players": int(len(work)),
    }
