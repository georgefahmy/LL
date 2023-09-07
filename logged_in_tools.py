import json
import os
import re

import PySimpleGUI as sg
import requests
from bs4 import BeautifulSoup as bs
from dotmap import DotMap

USER_DATA_DIR = os.path.expanduser("~") + "/.LearnedLeague/user_data/"
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
    Num correct - perfect defensive points (0, 1, 1, 2, 2, 3)""",
    "DE": "Defensive Efficiency",
    "FW": "Forfeit Wins",
    "FL": "Forfeit Losses",
    "3PT": "3-Pointers",
    "MCW": "Most Common Wrong Answers",
    "STR": "Streak",
    "QPct": "Percent of correct answers",
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


class UserData:
    def __init__(self, username=None):
        self.username = username


def get_question_history(
    sess=None, username=None, user_data=None, save=False, display=True
):
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
    category_metrics = DotMap()
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
            correct = "green" in question.find_all("td")[2].img.get("src")
            question_text = question.find_all("td")[1].text
            category_metrics[category_name].total += 1

            if correct:
                category_metrics[category_name].correct += 1
            else:
                category_metrics[category_name].correct += 0

            question_history[q_id] = DotMap(
                question_category=category_name,
                correct=correct,
                question=question_text,
                url=BASE_URL + question.find_all("td")[0].find_all("a")[2].get("href"),
            )

        category_metrics[category_name].percent = (
            category_metrics[category_name].correct
            / category_metrics[category_name].total
        )
    user_data.category_metrics = category_metrics
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
    if (
        "This is not an active player account."
        in page.find("div", {"class": "inner"}).text
    ):
        return user_data

    header = [
        val.text
        for val in page.find("table", {"class": "std std_bord stats"})
        .find("thead")
        .find_all("td")
    ]
    total = [
        val.text
        for val in page.find("table", {"class": "std std_bord stats"})
        .find("tbody")
        .find("tr", {"class": "grandtotal-row"})
        .find_all("td")
    ]
    current_season = [
        val.text
        for val in page.find("table", {"class": "std std_bord stats"})
        .find("tbody")
        .find("tr", {"class": ""})
        .find_all("td")
    ]
    user_data["stats"] = DotMap()
    user_data["stats"]["total"] = DotMap()
    user_data["stats"]["current_season"] = DotMap()
    for i, header_value in enumerate(header):
        if header_value == "Season":
            header_value = "Seas."
        if i == 0:
            user_data["stats"]["total"][header_value] = "Total"
            continue
        user_data["stats"]["total"][header_value] = total[i]

    for i, header_value in enumerate(header):
        user_data["stats"]["current_season"][header_value] = current_season[i]

    if save:
        save_user(user_data)

    return user_data


def load_user_data(username, current_day=None):
    # TODO update load user data to take into account the current match day
    # so its not constantly trying to download new data

    if os.path.isfile(USER_DATA_DIR + username + ".json"):
        with open(USER_DATA_DIR + username + ".json") as fp:
            user_data = DotMap(json.load(fp))

            if user_data.get("question_history"):
                if (
                    "question"
                    not in list(user_data.question_history.values())[0].keys()
                ):
                    print("Loaded existing data - Question text misssing")
                    user_data = get_question_history(
                        login(),
                        username=username,
                        save=True,
                        user_data=user_data,
                    )

            if not user_data.get("question_history"):
                print("Loaded existing data - No question History")
                user_data = get_question_history(
                    login(),
                    username=username,
                    save=True,
                    user_data=user_data,
                )

            if user_data.get("stats"):
                if not user_data.get("stats").get("total"):
                    print("Loaded existing data - Old Stats format")
                    user_data = get_user_stats(
                        login(), username=username, save=True, user_data=user_data
                    )

            if not user_data.get("stats"):
                print("Loaded existing data - No Stats available")
                user_data = get_user_stats(
                    login(), username=username, save=True, user_data=user_data
                )

            if not user_data.get("category_metrics"):
                print("Loaded existing data - No Category Metrics")
                user_data = get_question_history(
                    login(),
                    username=username,
                    save=True,
                    user_data=user_data,
                )
            if current_day not in user_data.question_history.keys():
                print("Loaded existing data - Missing current day")
                sess = login()
                user_data = get_question_history(
                    sess,
                    username=username,
                    save=True,
                    user_data=user_data,
                )
                user_data = get_user_stats(
                    sess, username=username, save=True, user_data=user_data
                )
                sess.close()

    else:
        print("No existing data - downloading new data")
        sess = login()
        user_data = get_question_history(sess, username=username)
        user_data = get_user_stats(
            sess, username=username, user_data=user_data, save=True
        )
        sess.close()
    return user_data


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
        json.dump(user_dict, fp, indent=4)
