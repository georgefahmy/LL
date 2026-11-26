from __future__ import annotations

import argparse
import math
import os
import random
import re
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.core.analytics import (  # noqa: E402
    DEFAULT_PRIOR_WEIGHT,
    DIFFICULTY_PROBS,
    _logit,
    _sigmoid,
    parse_leaguewide_csv,
    recommend_defense,
    smoothed_category_prob,
)
from backend.core.auth import parse_cookie_header  # noqa: E402
from backend.core.cache import CacheStore  # noqa: E402
from backend.core.constants import CATEGORIES  # noqa: E402
from backend.core.http_client import LLHttpClient  # noqa: E402
from backend.core.scrapers.profiles import fetch_player_profile  # noqa: E402

_QCODE_RE = re.compile(r"^S(\d+)D(\d+)Q(\d+)$", re.IGNORECASE)
_POINT_ALLOCATION = [3, 2, 2, 1, 1, 0]
_PRIOR_SWEEP_GRID = [0.0, 2.0, 5.0, 8.0, 12.0, 20.0]


@dataclass
class MetricAccumulator:
    name: str
    matchdays: int = 0
    total_opp_points: float = 0.0
    total_brier: float = 0.0
    total_logloss: float = 0.0
    total_questions: int = 0

    def record_matchday(
        self,
        assigned_points: list[int],
        predicted_probs: list[float],
        actual_correct: list[bool],
    ) -> None:
        self.matchdays += 1
        for pts, prob, y_bool in zip(
            assigned_points, predicted_probs, actual_correct, strict=True
        ):
            y = 1.0 if y_bool else 0.0
            p = min(0.99, max(0.01, float(prob)))
            self.total_opp_points += float(pts) * y
            self.total_brier += (p - y) ** 2
            self.total_logloss += -(y * math.log(p) + (1.0 - y) * math.log(1.0 - p))
            self.total_questions += 1

    @property
    def avg_opp_points(self) -> float:
        return self.total_opp_points / self.matchdays if self.matchdays else 0.0

    @property
    def brier(self) -> float:
        return self.total_brier / self.total_questions if self.total_questions else 0.0

    @property
    def logloss(self) -> float:
        return self.total_logloss / self.total_questions if self.total_questions else 0.0


@dataclass
class MatchdayQuestion:
    qcode: str
    q_num: int
    category: str
    me_correct: bool
    opp_correct: bool
    db_percent: float | None


@dataclass
class PreparedMatchday:
    season: int
    day: int
    questions: list[MatchdayQuestion]
    my_metrics: dict[str, dict[str, Any]]
    opp_metrics: dict[str, dict[str, Any]]


def _parse_qcode(qcode: str) -> tuple[int, int, int] | None:
    match = _QCODE_RE.match(qcode.strip())
    if not match:
        return None
    return int(match.group(1)), int(match.group(2)), int(match.group(3))


def load_db_questions(db_path: Path) -> dict[str, dict[str, Any]]:
    """Load historical questions and get-rates from SQLite."""
    if not db_path.exists():
        return {}
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT qcode, season, day, q_num, category, percent
            FROM questions
            WHERE qcode GLOB 'S*D*Q*'
            ORDER BY season ASC, day ASC, q_num ASC
            """
        ).fetchall()
    finally:
        conn.close()

    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        qcode = str(row["qcode"]).strip().upper()
        result[qcode] = {
            "qcode": qcode,
            "season": int(row["season"]),
            "day": int(row["day"]),
            "q_num": int(row["q_num"]),
            "category": str(row["category"]).strip(),
            "percent": float(row["percent"]),
        }
    return result


def build_synthetic_profiles(
    db_questions: dict[str, dict[str, Any]],
    *,
    num_players: int = 8,
    max_days: int = 200,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Generate synthetic players using real historical questions & league get-rates."""
    by_day: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for q in db_questions.values():
        by_day[(q["season"], q["day"])].append(q)

    complete_days = sorted(
        (day_key, sorted(qs, key=lambda x: x["q_num"]))
        for day_key, qs in by_day.items()
        if len(qs) == 6
    )
    if max_days > 0 and len(complete_days) > max_days:
        complete_days = complete_days[-max_days:]

    if not complete_days:
        raise ValueError("No complete 6-question matchdays found in database.")

    rng = random.Random(seed)
    all_cats = sorted(
        set(CATEGORIES) | {q["category"] for _, qs in complete_days for q in qs if q["category"]}
    )

    profiles: list[dict[str, Any]] = []
    for idx in range(num_players):
        name = "SyntheticMe" if idx == 0 else f"SyntheticOpp_{idx}"
        overall_skill = rng.gauss(0.15 if idx == 0 else 0.0, 0.45)
        cat_skills = {cat: overall_skill + rng.gauss(0.0, 0.70) for cat in all_cats}
        qhist: dict[str, dict[str, Any]] = {}

        for _, qs in complete_days:
            for q in qs:
                cat = q["category"]
                base_logit = _logit(q["percent"] / 100.0)
                p_correct = _sigmoid(base_logit + cat_skills.get(cat, overall_skill))
                qhist[q["qcode"]] = {
                    "question_category": cat,
                    "correct": rng.random() < p_correct,
                }

        profiles.append(
            {
                "profile_id": str(900000 + idx),
                "username": name.lower(),
                "formatted_username": name,
                "opponents": {},
                "category_metrics": {},
                "question_history": qhist,
            }
        )
    return profiles


def load_profile_local_or_live(
    identifier: str,
    cache: CacheStore,
    client: LLHttpClient | None,
    *,
    profile_id: str | None = None,
    offline: bool = False,
    ttl_minutes: int = 10080,
) -> dict[str, Any]:
    lookup_key = (profile_id or identifier).strip()
    if offline or client is None:
        cached = cache.get_cached_profile(lookup_key, ttl_minutes=10_000_000)
        if cached is None and profile_id:
            cached = cache.get_cached_profile(identifier, ttl_minutes=10_000_000)
        if cached is None:
            raise RuntimeError(
                f"Profile '{identifier}' not found in local cache (offline mode)."
            )
        return cached
    return fetch_player_profile(
        identifier,
        client,
        cache,
        profile_id=profile_id,
        ttl_minutes=ttl_minutes,
    )


def select_players_from_lgwide_csv(
    csv_path: Path,
    *,
    rundle: str | None = None,
    max_players: int = 8,
    seed: int = 42,
) -> list[str]:
    """Select players from a LearnedLeague lgwide.php CSV export."""
    csv_text = csv_path.read_text(encoding="utf-8")
    df = parse_leaguewide_csv(csv_text)
    if rundle:
        mask = df["Rundle"].str.upper() == rundle.strip().upper()
        filtered = df[mask]
        if filtered.empty:
            available = sorted(df["Rundle"].unique().tolist())[:10]
            raise ValueError(
                f"Rundle '{rundle}' not found in {csv_path}. Sample rundles: {available}"
            )
        df = filtered

    players = [str(p) for p in df["Player"].tolist() if str(p).strip()]
    if len(players) <= max_players:
        return players
    rng = random.Random(seed)
    return rng.sample(players, max_players)


def _counts_to_metrics(counts: dict[str, list[int]]) -> dict[str, dict[str, Any]]:
    metrics: dict[str, dict[str, Any]] = {}
    for cat, (correct, total) in counts.items():
        pct = (correct / total) if total > 0 else 0.0
        metrics[cat] = {
            "correct": correct,
            "total": total,
            "percent": round(pct, 6),
        }
    return metrics


def _index_history_by_day(
    question_history: dict[str, dict[str, Any]],
) -> dict[tuple[int, int], dict[int, tuple[str, dict[str, Any]]]]:
    by_day: dict[tuple[int, int], dict[int, tuple[str, dict[str, Any]]]] = defaultdict(dict)
    for raw_qcode, item in question_history.items():
        parsed = _parse_qcode(raw_qcode)
        if parsed is None:
            continue
        season, day, q_num = parsed
        by_day[(season, day)][q_num] = (raw_qcode.strip().upper(), item)
    return by_day


def prepare_matchdays_for_pair(
    me_profile: dict[str, Any],
    opp_profile: dict[str, Any],
    db_questions: dict[str, dict[str, Any]],
    *,
    min_history_days: int = 3,
    require_db_percent: bool = True,
) -> list[PreparedMatchday]:
    """Build strictly causal pre-matchday category snapshots for shared 6-question days."""
    me_days = _index_history_by_day(me_profile.get("question_history", {}))
    opp_days = _index_history_by_day(opp_profile.get("question_history", {}))

    all_days = sorted(set(me_days.keys()) | set(opp_days.keys()))
    me_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    opp_counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])

    prepared: list[PreparedMatchday] = []
    days_seen = 0

    for day_key in all_days:
        me_qmap = me_days.get(day_key, {})
        opp_qmap = opp_days.get(day_key, {})
        shared_qnums = sorted(set(me_qmap.keys()) & set(opp_qmap.keys()))

        if len(shared_qnums) == 6 and days_seen >= min_history_days:
            md_questions: list[MatchdayQuestion] = []
            missing_db = False
            for q_num in shared_qnums:
                qcode, me_item = me_qmap[q_num]
                _, opp_item = opp_qmap[q_num]
                db_q = db_questions.get(qcode)
                db_pct = float(db_q["percent"]) if db_q is not None else None
                if require_db_percent and db_pct is None:
                    missing_db = True
                    break
                cat = (
                    str(me_item.get("question_category") or "").strip()
                    or str(opp_item.get("question_category") or "").strip()
                    or (str(db_q["category"]).strip() if db_q else "")
                )
                md_questions.append(
                    MatchdayQuestion(
                        qcode=qcode,
                        q_num=q_num,
                        category=cat,
                        me_correct=bool(me_item.get("correct")),
                        opp_correct=bool(opp_item.get("correct")),
                        db_percent=db_pct,
                    )
                )

            if not missing_db and len(md_questions) == 6:
                prepared.append(
                    PreparedMatchday(
                        season=day_key[0],
                        day=day_key[1],
                        questions=md_questions,
                        my_metrics=_counts_to_metrics(me_counts),
                        opp_metrics=_counts_to_metrics(opp_counts),
                    )
                )

        # Update running career totals strictly AFTER snapshotting the current matchday
        for qcode, item in me_qmap.values():
            cat = str(item.get("question_category") or "").strip()
            if not cat and qcode in db_questions:
                cat = str(db_questions[qcode]["category"]).strip()
            if cat:
                me_counts[cat][1] += 1
                if item.get("correct"):
                    me_counts[cat][0] += 1

        for qcode, item in opp_qmap.values():
            cat = str(item.get("question_category") or "").strip()
            if not cat and qcode in db_questions:
                cat = str(db_questions[qcode]["category"]).strip()
            if cat:
                opp_counts[cat][1] += 1
                if item.get("correct"):
                    opp_counts[cat][0] += 1

        if me_qmap or opp_qmap:
            days_seen += 1

    return prepared


def _assign_points_ascending(scores: list[float]) -> list[int]:
    order = sorted(range(len(scores)), key=lambda i: (scores[i], i))
    assigned = [0] * len(scores)
    for rank_idx, slot_idx in enumerate(order):
        assigned[slot_idx] = _POINT_ALLOCATION[rank_idx]
    return assigned


def _snap_prob_to_difficulty(p: float) -> int:
    return min(DIFFICULTY_PROBS, key=lambda d: abs(DIFFICULTY_PROBS[d] - p))


def run_benchmark(
    matchdays: list[PreparedMatchday],
    *,
    prior_weight: float = DEFAULT_PRIOR_WEIGHT,
    noise_levels: list[float] | None = None,
    seed: int = 42,
) -> list[MetricAccumulator]:
    """Evaluate baseline, IRT, and oracle strategies on identical prepared matchdays."""
    if not matchdays:
        return []

    has_all_db_pct = all(q.db_percent is not None for md in matchdays for q in md.questions)
    sigmas = noise_levels if noise_levels is not None else [0.0, 0.5, 1.0, 1.5]
    sigma_rngs = {sigma: random.Random(seed) for sigma in sigmas}

    cat_only_acc = MetricAccumulator("Category-Only (Current)")
    smoothed_cat_acc = MetricAccumulator(f"Smoothed Category-Only (m={prior_weight:g})")
    binary_irt_acc = MetricAccumulator(f"IRT (Binary Proxy, m={prior_weight:g})")
    sim_irt_accs = {
        sigma: MetricAccumulator(f"IRT (Sim 5-Pt, sigma={sigma:g})")
        for sigma in sigmas
    }
    oracle_acc = MetricAccumulator("Oracle (League Get-Rate)")

    for md in matchdays:
        cats = [q.category for q in md.questions]
        actual = [q.opp_correct for q in md.questions]

        # 1. Current category-only baseline
        recs_cat = recommend_defense(cats, md.opp_metrics)
        cat_only_acc.record_matchday(
            [r["recommended_points"] for r in recs_cat],
            [r["estimated_opponent_pct"] / 100.0 for r in recs_cat],
            actual,
        )

        # 2. Smoothed category-only
        smoothed_probs = [
            smoothed_category_prob(md.opp_metrics, c, prior_weight=prior_weight)
            for c in cats
        ]
        smoothed_cat_acc.record_matchday(
            _assign_points_ascending(smoothed_probs),
            smoothed_probs,
            actual,
        )

        # 3. IRT (Binary Proxy: True -> 2 (75%), False -> 4 (25%))
        binary_diffs = [2 if q.me_correct else 4 for q in md.questions]
        recs_bin = recommend_defense(
            cats,
            md.opp_metrics,
            player_metrics=md.my_metrics,
            difficulties=binary_diffs,
            prior_weight=prior_weight,
        )
        binary_irt_acc.record_matchday(
            [r["recommended_points"] for r in recs_bin],
            [r["estimated_opponent_pct"] / 100.0 for r in recs_bin],
            actual,
        )

        # 4 & 5. Simulated 5-pt IRT across noise levels + Oracle (requires .data/app.db percent)
        if has_all_db_pct:
            for sigma in sigmas:
                sim_diffs: list[int] = []
                for q in md.questions:
                    q_pct = (q.db_percent or 50.0) / 100.0
                    theta_me = _logit(
                        smoothed_category_prob(
                            md.my_metrics, q.category, prior_weight=prior_weight
                        )
                    )
                    noise = sigma_rngs[sigma].gauss(0.0, sigma) if sigma > 0.0 else 0.0
                    p_perceived = _sigmoid(_logit(q_pct) + theta_me + noise)
                    sim_diffs.append(_snap_prob_to_difficulty(p_perceived))
                recs_sim = recommend_defense(
                    cats,
                    md.opp_metrics,
                    player_metrics=md.my_metrics,
                    difficulties=sim_diffs,
                    prior_weight=prior_weight,
                )
                sim_irt_accs[sigma].record_matchday(
                    [r["recommended_points"] for r in recs_sim],
                    [r["estimated_opponent_pct"] / 100.0 for r in recs_sim],
                    actual,
                )

            oracle_probs = [
                min(0.99, max(0.01, (q.db_percent or 50.0) / 100.0))
                for q in md.questions
            ]
            oracle_acc.record_matchday(
                _assign_points_ascending(oracle_probs),
                oracle_probs,
                actual,
            )

    results = [cat_only_acc, smoothed_cat_acc, binary_irt_acc]
    if has_all_db_pct:
        results.extend(sim_irt_accs[s] for s in sigmas)
        results.append(oracle_acc)
    return results


def run_prior_sweep(
    matchdays: list[PreparedMatchday],
    *,
    prior_grid: list[float] | None = None,
    sigma: float = 0.5,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Sweep Empirical Bayes prior_weight m and collect IRT performance metrics."""
    grid = prior_grid or _PRIOR_SWEEP_GRID
    has_all_db_pct = all(q.db_percent is not None for md in matchdays for q in md.questions)
    rows: list[dict[str, Any]] = []

    for m in grid:
        rng = random.Random(seed)
        bin_acc = MetricAccumulator("binary")
        sim_acc = MetricAccumulator("sim")
        smooth_acc = MetricAccumulator("smooth")

        for md in matchdays:
            cats = [q.category for q in md.questions]
            actual = [q.opp_correct for q in md.questions]

            smoothed_probs = [
                smoothed_category_prob(md.opp_metrics, c, prior_weight=m) for c in cats
            ]
            smooth_acc.record_matchday(
                _assign_points_ascending(smoothed_probs), smoothed_probs, actual
            )

            bin_diffs = [2 if q.me_correct else 4 for q in md.questions]
            recs_bin = recommend_defense(
                cats,
                md.opp_metrics,
                player_metrics=md.my_metrics,
                difficulties=bin_diffs,
                prior_weight=m,
            )
            bin_acc.record_matchday(
                [r["recommended_points"] for r in recs_bin],
                [r["estimated_opponent_pct"] / 100.0 for r in recs_bin],
                actual,
            )

            if has_all_db_pct:
                sim_diffs: list[int] = []
                for q in md.questions:
                    q_pct = (q.db_percent or 50.0) / 100.0
                    theta_me = _logit(
                        smoothed_category_prob(md.my_metrics, q.category, prior_weight=m)
                    )
                    noise = rng.gauss(0.0, sigma) if sigma > 0.0 else 0.0
                    sim_diffs.append(
                        _snap_prob_to_difficulty(_sigmoid(_logit(q_pct) + theta_me + noise))
                    )
                recs_sim = recommend_defense(
                    cats,
                    md.opp_metrics,
                    player_metrics=md.my_metrics,
                    difficulties=sim_diffs,
                    prior_weight=m,
                )
                sim_acc.record_matchday(
                    [r["recommended_points"] for r in recs_sim],
                    [r["estimated_opponent_pct"] / 100.0 for r in recs_sim],
                    actual,
                )

        rows.append(
            {
                "m": m,
                "smooth_pts": smooth_acc.avg_opp_points,
                "smooth_logloss": smooth_acc.logloss,
                "bin_pts": bin_acc.avg_opp_points,
                "bin_logloss": bin_acc.logloss,
                "sim_pts": sim_acc.avg_opp_points if has_all_db_pct else None,
                "sim_logloss": sim_acc.logloss if has_all_db_pct else None,
            }
        )
    return rows


def print_benchmark_table(results: list[MetricAccumulator]) -> None:
    if not results:
        print("No benchmark results to display.")
        return
    header = (
        f"{'Strategy':<38} | {'Matchdays':>9} | {'Avg Opp Pts':>11} | "
        f"{'Brier':>8} | {'Log-Loss':>8}"
    )
    print("\n" + header)
    print("-" * len(header))
    for acc in results:
        print(
            f"{acc.name:<38} | {acc.matchdays:>9d} | {acc.avg_opp_points:>11.4f} | "
            f"{acc.brier:>8.4f} | {acc.logloss:>8.4f}"
        )


def print_prior_sweep(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    has_sim = rows[0]["sim_pts"] is not None
    print("\nEmpirical Bayes Prior Weight Sweep (m):")
    if has_sim:
        header = (
            f"{'m':>5} | {'Smooth Pts':>10} | {'Smooth LL':>9} | "
            f"{'Bin IRT Pts':>11} | {'Bin LL':>8} | {'Sim(0.5) Pts':>12} | {'Sim LL':>8}"
        )
        print(header)
        print("-" * len(header))
        for r in rows:
            print(
                f"{r['m']:>5.1f} | {r['smooth_pts']:>10.4f} | {r['smooth_logloss']:>9.4f} | "
                f"{r['bin_pts']:>11.4f} | {r['bin_logloss']:>8.4f} | "
                f"{r['sim_pts']:>12.4f} | {r['sim_logloss']:>8.4f}"
            )
        best_pts = min(rows, key=lambda r: r["sim_pts"])
        best_ll = min(rows, key=lambda r: r["sim_logloss"])
        print(
            f"Best m (Sim 5-Pt sigma=0.5): min Opp Pts at m={best_pts['m']:g} "
            f"({best_pts['sim_pts']:.4f}), min Log-Loss at m={best_ll['m']:g} "
            f"({best_ll['sim_logloss']:.4f})"
        )
    else:
        header = (
            f"{'m':>5} | {'Smooth Pts':>10} | {'Smooth LL':>9} | "
            f"{'Bin IRT Pts':>11} | {'Bin LL':>8}"
        )
        print(header)
        print("-" * len(header))
        for r in rows:
            print(
                f"{r['m']:>5.1f} | {r['smooth_pts']:>10.4f} | {r['smooth_logloss']:>9.4f} | "
                f"{r['bin_pts']:>11.4f} | {r['bin_logloss']:>8.4f}"
            )
        best_pts = min(rows, key=lambda r: r["bin_pts"])
        best_ll = min(rows, key=lambda r: r["bin_logloss"])
        print(
            f"Best m (Binary IRT): min Opp Pts at m={best_pts['m']:g} "
            f"({best_pts['bin_pts']:.4f}), min Log-Loss at m={best_ll['m']:g} "
            f"({best_ll['bin_logloss']:.4f})"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest and calibrate the Empirical-Bayes Logit IRT defense model."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=REPO_ROOT / ".data" / "app.db",
        help="Path to SQLite database (default: .data/app.db)",
    )
    parser.add_argument(
        "--player",
        type=str,
        default=None,
        help="Focal LearnedLeague player username or profile ID.",
    )
    parser.add_argument(
        "--opponents",
        type=str,
        default=None,
        help="Comma-separated opponent usernames or profile IDs.",
    )
    parser.add_argument(
        "--lgwide-csv",
        type=Path,
        default=None,
        help="Path to LearnedLeague lgwide.php CSV export for batch player selection.",
    )
    parser.add_argument(
        "--rundle",
        type=str,
        default=None,
        help="Optional rundle filter when --lgwide-csv is used.",
    )
    parser.add_argument(
        "--max-players",
        type=int,
        default=8,
        help="Maximum players to load from --lgwide-csv (default: 8).",
    )
    parser.add_argument(
        "--cookie",
        type=str,
        default=None,
        help="LearnedLeague session Cookie header (defaults to LL_COOKIE env var).",
    )
    parser.add_argument(
        "--offline",
        action="store_true",
        help="Use only locally cached profiles in --db without contacting LearnedLeague.",
    )
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Run benchmark on synthetic players simulated from real .data/app.db questions.",
    )
    parser.add_argument(
        "--synthetic-players",
        type=int,
        default=8,
        help="Number of synthetic players in --synthetic mode (default: 8).",
    )
    parser.add_argument(
        "--max-days",
        type=int,
        default=200,
        help="Max recent matchdays to include in --synthetic mode (0 = all, default: 200).",
    )
    parser.add_argument(
        "--prior-weight",
        type=float,
        default=DEFAULT_PRIOR_WEIGHT,
        help=f"Empirical Bayes prior weight m (default: {DEFAULT_PRIOR_WEIGHT}).",
    )
    parser.add_argument(
        "--noise-levels",
        type=str,
        default="0.0,0.5,1.0,1.5",
        help="Comma-separated logit noise sigmas for simulated 5-pt IRT ratings.",
    )
    parser.add_argument(
        "--min-history-days",
        type=int,
        default=3,
        help="Minimum prior matchdays before scoring a matchday (default: 3).",
    )
    parser.add_argument(
        "--sweep-prior",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Sweep prior_weight m in [0, 2, 5, 8, 12, 20] (default: enabled).",
    )
    parser.add_argument(
        "--ttl-minutes",
        type=int,
        default=10080,
        help="Profile cache TTL in minutes when scraping live profiles (default: 10080).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for synthetic generation and noise sampling (default: 42).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    noise_levels = [
        float(part.strip()) for part in args.noise_levels.split(",") if part.strip()
    ]

    db_questions = load_db_questions(args.db)
    print(f"Loaded {len(db_questions)} historical questions from {args.db}")

    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []

    if args.synthetic:
        if not db_questions:
            print(f"Error: no historical questions found in {args.db}", file=sys.stderr)
            return 1
        profiles = build_synthetic_profiles(
            db_questions,
            num_players=max(2, args.synthetic_players),
            max_days=args.max_days,
            seed=args.seed,
        )
        me_prof = profiles[0]
        pairs = [(me_prof, opp) for opp in profiles[1:]]
        print(
            f"Generated {len(profiles)} synthetic players across "
            f"{len(me_prof['question_history']) // 6} matchdays ({len(pairs)} pairings)."
        )
    else:
        if not args.player and not args.lgwide_csv:
            print(
                "Error: specify --synthetic, --player <username>, or --lgwide-csv <path>.",
                file=sys.stderr,
            )
            return 1

        raw_cookie = args.cookie or os.environ.get("LL_COOKIE", "")
        cookies = parse_cookie_header(raw_cookie) if raw_cookie.strip() else {}
        if not args.offline and not cookies:
            print(
                "No --cookie or LL_COOKIE provided; falling back to --offline cache lookup."
            )
            args.offline = True

        cache = CacheStore(args.db)
        client: LLHttpClient | None = None
        try:
            if not args.offline:
                client = LLHttpClient(cookies=cookies)

            if args.lgwide_csv:
                selected_names = select_players_from_lgwide_csv(
                    args.lgwide_csv,
                    rundle=args.rundle,
                    max_players=args.max_players,
                    seed=args.seed,
                )
                print(
                    f"Selected {len(selected_names)} players from {args.lgwide_csv}: "
                    f"{selected_names}"
                )
                loaded_profiles = [
                    load_profile_local_or_live(
                        name,
                        cache,
                        client,
                        offline=args.offline,
                        ttl_minutes=args.ttl_minutes,
                    )
                    for name in selected_names
                ]
                if args.player:
                    me_prof = load_profile_local_or_live(
                        args.player,
                        cache,
                        client,
                        offline=args.offline,
                        ttl_minutes=args.ttl_minutes,
                    )
                    me_pid = me_prof.get("profile_id")
                    pairs = [
                        (me_prof, opp)
                        for opp in loaded_profiles
                        if opp.get("profile_id") != me_pid
                    ]
                else:
                    pairs = [
                        (p1, p2)
                        for i, p1 in enumerate(loaded_profiles)
                        for j, p2 in enumerate(loaded_profiles)
                        if i != j
                    ]
            else:
                assert args.player is not None
                me_prof = load_profile_local_or_live(
                    args.player,
                    cache,
                    client,
                    offline=args.offline,
                    ttl_minutes=args.ttl_minutes,
                )
                opp_map = me_prof.get("opponents", {})
                if args.opponents:
                    opp_targets = [
                        (o.strip(), opp_map.get(o.strip()))
                        for o in args.opponents.split(",")
                        if o.strip()
                    ]
                else:
                    opp_targets = list(opp_map.items())[: args.max_players]

                if not opp_targets:
                    print(
                        f"Error: no opponents specified or found on profile '{args.player}'.",
                        file=sys.stderr,
                    )
                    return 1

                for opp_name, opp_pid in opp_targets:
                    opp_prof = load_profile_local_or_live(
                        opp_name,
                        cache,
                        client,
                        profile_id=opp_pid,
                        offline=args.offline,
                        ttl_minutes=args.ttl_minutes,
                    )
                    pairs.append((me_prof, opp_prof))
        finally:
            if client is not None:
                client.close()
            cache.close()

    all_matchdays: list[PreparedMatchday] = []
    for me_prof, opp_prof in pairs:
        all_matchdays.extend(
            prepare_matchdays_for_pair(
                me_prof,
                opp_prof,
                db_questions,
                min_history_days=args.min_history_days,
                require_db_percent=bool(db_questions),
            )
        )

    # If real profile questions didn't overlap with .data/app.db, fall back without DB percent
    if not all_matchdays and db_questions and not args.synthetic:
        for me_prof, opp_prof in pairs:
            all_matchdays.extend(
                prepare_matchdays_for_pair(
                    me_prof,
                    opp_prof,
                    db_questions,
                    min_history_days=args.min_history_days,
                    require_db_percent=False,
                )
            )

    if not all_matchdays:
        print("No complete shared 6-question matchdays found to evaluate.", file=sys.stderr)
        return 1

    print(
        f"Evaluating {len(all_matchdays)} matchdays across {len(pairs)} player pairings "
        f"(min_history_days={args.min_history_days})..."
    )
    results = run_benchmark(
        all_matchdays,
        prior_weight=args.prior_weight,
        noise_levels=noise_levels,
        seed=args.seed,
    )
    print_benchmark_table(results)

    if args.sweep_prior:
        sweep_rows = run_prior_sweep(all_matchdays, seed=args.seed)
        print_prior_sweep(sweep_rows)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
