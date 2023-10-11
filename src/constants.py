import os

WD = os.getcwd()
DEFAULT_FONT = ("Arial", 14)

USER_DATA_DIR = os.path.expanduser("~") + "/.LearnedLeague/user_data/"

MODKOS = "https://www.learnedleague.com/images/misc/ModKos.png?t=1649"

BASE_URL = "https://www.learnedleague.com"
LOGIN_URL = BASE_URL + "/ucp.php?mode=login"
USER_QHIST = BASE_URL + "/profiles.php?%s&9"

FILENAME = "LearnedLeague.dmg"
VOLUME_NAME = FILENAME.split(".")[0]

CATEGORIES = [
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

STATS_DEFINITION = {
    "Seas.": "Season",
    "W": "Wins",
    "L": "Losses",
    "T": "Ties",
    "PTS": "Points (in standings) - This determines the order of the standings. Two points for a win, one for a tie, -1 for a forfeit loss",
    "TMP": "Total Match Points - Sum of points scored in all matches",
    "TPA": "Total Points Allowed",
    "MPD": "Match Points Differential - The difference between Match Points scored and Match Points allowed (TMP-TPA)",
    "TCA": "Total Correct Answers",
    "CAA": "Correct Answers Against - Total number of questions answered correctly by one's opponents in all matches",
    "PCAA": "Points Per Correct Answer Against - The average value allowed per correct answer of one's opponent",
    "UfPA": """Unforced Points Allowed -
The total number of points allowed above that which would have been allowed with perfect defense
(i.e. if one's opponent answered four correct and scored 7, he gave up 3 UfPA [7-4]).
Perfect defensive points - (1: 0, 2: 1, 3: 2, 4: 4, 5: 6, 6: 9)""",
    "DE": "Defensive Efficiency -\nThe total number of UfPA you could have but did not allow\ndivided by the total number you could have allowed. The higher the number the better",
    "FW": "Forfeit Wins",
    "FL": "Forfeit Losses",
    "3PT": "3-Pointers",
    "MCW": "Most Common Wrong Answers -\nNumber of answers submitted\nwhich were the Most Common Wrong Answer for its question",
    "QPct": "Percent of correct answers",
    "Rundle": "User's Rundle",
    "Rank": "Overall Rank in the Season",
}
