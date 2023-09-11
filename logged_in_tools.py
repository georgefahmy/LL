import json
import os
import re

import PySimpleGUI as sg
import requests
from bs4 import BeautifulSoup as bs
from bs4 import SoupStrainer as ss
from dotmap import DotMap

USER_DATA_DIR = os.path.expanduser("~") + "/.LearnedLeague/user_data/"
DEFAULT_FONT = ("Arial", 14)
BASE_URL = "https://www.learnedleague.com"
LOGIN_URL = BASE_URL + "/ucp.php?mode=login"
USER_QHIST = BASE_URL + "/profiles.php?%s&9"
CATEGORIES = [
    "AMER_HIST",
    "ART",
    "BUS/ECON",
    "CLASS_MUSIC",
    "CURR_EVENTS",
    "FILM",
    "FOOD/DRINK",
    "GAMES/SPORT",
    "GEOGRAPHY",
    "LANGUAGE",
    "LIFESTYLE",
    "LITERATURE",
    "MATH",
    "POP_MUSIC",
    "SCIENCE",
    "TELEVISION",
    "THEATRE",
    "WORLD_HIST",
]
STATS_DEFINITION = {
    "Seas.": "Season",
    "W": "Wins",
    "L": "Losses",
    "T": "Ties",
    "PTS": "Points (in standings) - This determines the order of the standings. Two points for a win, one for a tie, -1 for a forfeit loss",
    "MPD": "Match Points Differential - The difference between Match Points scored and Match Points allowed (TMP-TPA)",
    "TMP": "Total Match Points - Sum of points scored in all matches",
    "TPA": "Total Points Allowed",
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
    "Rank": "Overall Rank in the Season",
}


def login(logout=False):
    if os.path.isfile(os.path.expanduser("~") + "/.LearnedLeague/login_info.json"):
        login_info = json.load(
            open(os.path.expanduser("~") + "/.LearnedLeague/login_info.json")
        )
    else:
        login_info = {}
    if not login_info.get("auto_login_check"):
        event, login_info = sg.Window(
            "Learned League Login",
            [
                [
                    sg.Text("Username", font=DEFAULT_FONT, expand_x=True),
                    sg.Text(expand_x=True),
                    sg.Input(
                        login_info.get("username") or "",
                        size=(30, 1),
                        key="username",
                        font=DEFAULT_FONT,
                        expand_x=True,
                    ),
                ],
                [
                    sg.Text("Password", font=DEFAULT_FONT, expand_x=True),
                    sg.Text(expand_x=True),
                    sg.Input(
                        login_info.get("password") or "",
                        password_char="*",
                        size=(30, 1),
                        key="password",
                        font=DEFAULT_FONT,
                        expand_x=True,
                    ),
                ],
                [
                    sg.Checkbox(
                        "Auto-Login",
                        key="auto_login_check",
                    ),
                    sg.Text(expand_x=True),
                    sg.Button("Submit", key="submit"),
                    sg.Button("Cancel", key="cancel"),
                ],
            ],
            disable_close=False,
        ).read(close=True)

        if event == "cancel":
            return False

    if logout:
        login_info["auto_login_check"] = False

    json.dump(
        login_info,
        open(os.path.expanduser("~") + "/.LearnedLeague/login_info.json", "w"),
        indent=4,
        sort_keys=False,
    )
    if not logout:
        payload = {
            "login": "Login",
            "username": login_info.get("username"),
            "password": login_info.get("password"),
        }
        sess = requests.Session()
        sess.post(LOGIN_URL, data=payload)
        sess.headers["profile"] = login_info.get("username").lower()
        return sess


def display_category_metrics(user_data):
    sorted_categories = sorted(
        list(user_data.category_metrics.keys()),
        key=lambda x: (user_data.category_metrics[x]["percent"]),
        reverse=True,
    )
    cat_metrics = sg.Window(
        f"Category Metrics - {user_data.username}",
        layout=[
            [
                [
                    sg.Text(
                        (
                            f"{category}: "
                            + f"({user_data.category_metrics[category].correct}"
                            + f"/{user_data.category_metrics[category].total})"
                        ),
                        expand_x=True,
                        justification="l",
                        font=DEFAULT_FONT,
                    ),
                    sg.Text(
                        f"{user_data.category_metrics[category].percent*100:3.2f}%",
                        font=DEFAULT_FONT,
                        justification="r",
                    ),
                    sg.ProgressBar(
                        max_value=user_data.category_metrics[category].get("total"),
                        orientation="h",
                        size_px=(100, 20),
                        key=category,
                    ),
                ]
                for category in sorted_categories
            ]
        ],
        finalize=True,
        modal=False,
    )
    [
        cat_metrics[category].update(
            current_count=user_data.category_metrics[category].get("correct")
        )
        for category in user_data.category_metrics.keys()
    ]
