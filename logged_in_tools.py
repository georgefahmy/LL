import json
import os
import re

import PySimpleGUI as sg
import requests
from bs4 import BeautifulSoup as bs
from dotmap import DotMap
from numpy import percentile

DEFAULT_FONT = ("Arial", 14)
BASE_URL = "https://www.learnedleague.com"
LOGIN_URL = BASE_URL + "/ucp.php?mode=login"
USER_QHIST = BASE_URL + "/profiles.php?%s&9"
STATS_DEFINITION = {
    "W": "Wins",
    "L": "Losses",
    "T": "Ties",
    "PTS": "Points (in standings)",
    "MPD": "Match Points Differential",
    "TMP": "Total Match Points",
    "TCA": "Total Correct Answers",
    "TPA": "Total Points Allowed",
    "CAA": "Correct Answers Against",
    "PCAA": "Points Per Correct Answer Against",
    "UfPA": """Unforced Points Allowed
        Num correct - perfect defensive points (0, 1, 1, 2, 2, 3)
        """,
    "DE": "Defensive Efficiency",
    "FW": "Forfeit Wins",
    "FL": "Forfeit Losses",
    "3PT": "3-Pointers",
    "MCW": "Most Common Wrong Answers",
    "STR": "Streak",
    "QPct": "Percent of correct answers",
}


def login():
    if os.path.isfile(os.path.expanduser("~") + "/.LearnedLeague/login_info.json"):
        login_info = json.load(
            open(os.path.expanduser("~") + "/.LearnedLeague/login_info.json")
        )
    else:
        login_info = {}
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
                    sg.Text(expand_x=True),
                    sg.Button("Submit", key="submit"),
                    sg.Button("Cancel", key="cancel"),
                ],
            ],
            disable_close=False,
        ).read(close=True)

        if event == "cancel":
            return False
    json.dump(
        login_info,
        open(os.path.expanduser("~") + "/.LearnedLeague/login_info.json", "w"),
        indent=4,
        sort_keys=False,
    )

    payload = {
        "login": "Login",
        "username": login_info.get("username"),
        "password": login_info.get("password"),
    }
    sess = requests.Session()
    sess.post(LOGIN_URL, data=payload)
    sess.headers["profile"] = login_info.get("username").lower()
    return sess


class UserData:
    def __init__(self, username=None):
        self.username = username


def get_question_history(sess=None, username=None, user_data=None, save=False):
    if not sess:
        sess = login()

    if not user_data:
        user_data = DotMap()

    if not username and not user_data:
        username = sess.headers.get("profile")
    elif not username and user_data:
        username = user_data.username
    else:
        username = username.lower()

    if not user_data.username:
        user_data.username = username

    profile_id = sess.get(
        f"https://learnedleague.com/profiles.php?{username}"
    ).url.split("?")[-1]
    try:
        response = sess.get(f"https://learnedleague.com/profiles.php?{profile_id}&9")
    except Exception as e:
        print(e)
        user_data.ok = False
        return user_data
    page = bs(response.content, "html.parser")
    all_categories = page.find_all("ul", {"class": "mktree"})
    question_history = DotMap()
    for category in all_categories:
        category_name = re.sub(
            " ", "_", category.find("span", {"class": "catname"}).text
        )
        questions = category.find("table", {"class": "qh"}).find_all("tr")[1:]
        for question in questions:
            q_id = (
                question.find_all("td")[0].find_all("a")[2].get("href").split("?")[-1]
            )
            q_id = f'S{q_id.split("&")[0]}D{q_id.split("&")[1]}Q{q_id.split("&")[2]}'
            question_history[q_id] = DotMap(
                question_category=category_name,
                correct="green" in question.find_all("td")[2].img.get("src"),
                url=BASE_URL + question.find_all("td")[0].find_all("a")[2].get("href"),
            )

    user_data.question_history = question_history
    user_data.ok = response.ok

    if save:
        save_user(user_data)

    return user_data


def get_user_stats(sess=None, username=None, user_data=None, save=False):
    if not sess:
        sess = login()

    if not user_data:
        user_data = DotMap()

    if not username and not user_data:
        username = sess.headers.get("profile")
    elif not username and user_data:
        username = user_data.username
    else:
        username = username.lower()

    if not user_data.username:
        user_data.username = username

    profile_id = sess.get(
        f"https://learnedleague.com/profiles.php?{username}"
    ).url.split("?")[-1]
    response = sess.get(f"https://learnedleague.com/profiles.php?{profile_id}&2")
    page = bs(response.content, "html.parser")
    header = [
        val.text
        for val in page.find("table", {"class": "std std_bord stats"})
        .find("thead")
        .find_all("td")
    ]
    body = [
        val.text
        for val in page.find("table", {"class": "std std_bord stats"})
        .find("tbody")
        .find("tr", {"class": "grandtotal-row"})
        .find_all("td")
    ]
    user_data["stats"] = DotMap()
    for i, header_value in enumerate(header):
        user_data["stats"][header_value] = body[i]

    if save:
        save_user(user_data)

    return user_data


def calc_category_metrics(user_data):
    qhist = user_data.question_history
    category_metrics = DotMap()
    for val in qhist.values():
        category_metrics[val.question_category].total += 1
        if val.correct:
            category_metrics[val.question_category].correct += 1
        else:
            category_metrics[val.question_category].correct += 0
        percent = (
            category_metrics[val.question_category].correct
            / category_metrics[val.question_category].total
        )
        category_metrics[val.question_category].percent = percent
    user_data.category_metrics = category_metrics
    return user_data


def calc_hun_score(user1_qhist_dict, user2_qhist_dict, save=False, debug=False):
    raw = 0
    total = 0

    for key, values in user1_qhist_dict.question_history.items():
        if key in user2_qhist_dict.question_history.keys():
            total += 1
            if values.correct == user2_qhist_dict.question_history[key].correct:
                raw += 1

    if not total:
        hun_score = 0
    else:
        hun_score = raw / total

    user1_qhist_dict.hun[user2_qhist_dict.username] = hun_score
    user2_qhist_dict.hun[user1_qhist_dict.username] = hun_score

    if save:
        save_user(user1_qhist_dict)
        save_user(user2_qhist_dict)

    if debug:
        print(raw, total)

    return user1_qhist_dict, user2_qhist_dict


def save_user(user_dict):
    user_data_dir = os.path.expanduser("~") + "/.LearnedLeague/user_data"
    if not os.path.isdir(user_data_dir):
        os.mkdir(user_data_dir)

    filename = user_data_dir + "/" + user_dict.username + ".json"
    with open(filename, "w") as fp:
        json.dump(user_dict, fp, indent=4, sort_keys=True)
