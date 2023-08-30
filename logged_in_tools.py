import json
import os
import re

import PySimpleGUI as sg
import requests
from bs4 import BeautifulSoup as bs
from dotmap import DotMap

DEFAULT_FONT = ("Arial", 14)
BASE_URL = "https://www.learnedleague.com"
LOGIN_URL = BASE_URL + "/ucp.php?mode=login"
USER_QHIST = BASE_URL + "/profiles.php?%s&9"


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


def get_question_history(sess=None, username=None, user_data=None):
    if not sess:
        sess = login()
    if not user_data:
        user_data = DotMap()
    if not username:
        username = sess.headers.get("profile")
    else:
        username = username.lower()
    profile_id = sess.get(
        f"https://learnedleague.com/profiles.php?{username}"
    ).url.split("?")[-1]
    response = sess.get(f"https://learnedleague.com/profiles.php?{profile_id}&9")
    page = bs(response.content, "html.parser")
    all_categories = page.find_all("ul", {"class": "mktree"})
    question_history = DotMap()
    for category in all_categories:
        category_name = re.sub(
            " ", "_", category.find("span", {"class": "catname"}).text
        )
        questions = category.find("table", {"class": "qh"}).find_all("tr")[1:]
        for i, question in enumerate(questions):
            q_id = (
                question.find_all("td")[0].find_all("a")[2].get("href").split("?")[-1]
            )
            question_history[q_id] = DotMap(
                question_category=category_name,
                # question=question.find_all("td")[1].text,
                correct="green" in question.find_all("td")[2].img.get("src"),
                url=BASE_URL + question.find_all("td")[0].find_all("a")[2].get("href"),
            )

    user_data.question_history = question_history
    user_data.ok = response.ok
    return user_data


def get_user_stats(sess=None, username=None, user_data=None):
    if not sess:
        sess = login()
    if not user_data:
        user_data = DotMap()
    if not username:
        username = sess.headers.get("profile")
    else:
        username = username.lower()

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
    return user_data
