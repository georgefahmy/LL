from __future__ import annotations

BASE_URL = "https://www.learnedleague.com"
LOGIN_URL = f"{BASE_URL}/ucp.php?mode=login"
ALL_RUNDLES_URL = f"{BASE_URL}/allrundles.php"
LGWIDE_URL = f"{BASE_URL}/lgwide.php?{{}}"
ONEDAYS_LIST_URL = f"{BASE_URL}/oneday/onedaysalpha.php"
MINILEAGUES_LIST_URL = f"{BASE_URL}/mini/"
MODKOS_URL = f"{BASE_URL}/images/misc/ModKos.png?t=1649"

ALLOWED_IMAGE_HOSTS = frozenset({"www.learnedleague.com", "learnedleague.com"})
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB

DEFAULT_BROWSER_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Sec-Ch-Ua": '"Chromium";v="131", "Not_A Brand";v="24"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"macOS"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}

CATEGORIES: list[str] = [
    "AMER HIST",
    "ART",
    "BUS/ECON",
    "CLASS MUSIC",
    "CURR EVENTS",
    "FILM",
    "FOOD/DRINK",
    "GAMES/SPORT",
    "GEOGRAPHY",
    "LANGUAGE",
    "LIFESTYLE",
    "LITERATURE",
    "MATH",
    "POP MUSIC",
    "SCIENCE",
    "TELEVISION",
    "THEATRE",
    "WORLD HIST",
]

EXCLUDED_QUIZ_MARKERS: tuple[str, ...] = (
    "Just Audio",
    "Just Images",
    "Just Memes",
    "Just GIFs",
    "Just Fuzzy Images",
)

STATS_DEFINITION: dict[str, str] = {
    "Seas.": "Season",
    "W": "Wins",
    "L": "Losses",
    "T": "Ties",
    "PTS": (
        "Points (in standings) - Determines standings order. "
        "Two points for a win, one for a tie, -1 for a forfeit loss."
    ),
    "TMP": "Total Match Points - Sum of points scored in all matches.",
    "TPA": "Total Points Allowed.",
    "MPD": "Match Points Differential - TMP minus TPA.",
    "TCA": "Total Correct Answers.",
    "CAA": "Correct Answers Against - Total correct answers by opponents.",
    "PCAA": "Points Per Correct Answer Against.",
    "UfPA": "Unforced Points Allowed above perfect defense.",
    "DE": "Defensive Efficiency - Higher is better.",
    "FW": "Forfeit Wins.",
    "FL": "Forfeit Losses.",
    "3PT": "3-Pointers.",
    "MCW": "Most Common Wrong Answers submitted.",
    "QPct": "Percent of correct answers.",
    "Rundle": "User's Rundle.",
    "Rank": "Overall Rank in the Season.",
}

LUCK_FIELDS: list[str] = [
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
    "Rank",
    "League",
    "Branch",
    "Level",
    "Matches",
    "Played",
    "Player_count",
    "norm_OE",
    "norm_DE",
    "norm_QPct",
    "norm_CAA",
    "norm_3PT",
    "norm_FL",
    "Luck_Rank_adj",
]

DEFAULT_LUCK_FIELDS: list[str] = [
    "Player",
    "W",
    "L",
    "T",
    "QPct",
    "TCA",
    "CAA",
    "DE",
    "PTS",
    "Exp_PTS",
    "Luck",
    "LuckPctile",
    "Rank",
    "Exp_Rank",
    "norm_QPct",
    "norm_SOS",
    "SOS",
]

MIN_AVAILABLE_SEASON = 60
