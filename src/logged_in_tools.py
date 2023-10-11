import json
import os
import re

import PySimpleGUI as sg
import requests
from bs4 import BeautifulSoup as bs
from dotmap import DotMap

from .constants import BASE_URL, DEFAULT_FONT, LOGIN_URL


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
    if not user_data.profile_id.isnumeric():
        sg.popup_auto_close("Player Not Found.", no_titlebar=True, modal=False)
        return

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


def display_todays_questions(season, day, display_answers=False):
    sess = login()
    current_match_day = BASE_URL + f"/match.php?{season}&{day}"
    match_day_page = bs(
        sess.get(current_match_day).content,
        "html.parser",
    )
    if match_day_page.find("h1"):
        if "Results" in match_day_page.find("h1").parent.text:
            sg.popup_no_titlebar(
                "No Active Match Day in play",
                title="No Active Match",
                modal=False,
                auto_close=True,
                auto_close_duration=10,
            )
            return DotMap(metadata="continue")
    if match_day_page.find("h2"):
        if "not yet active" in match_day_page.find("h2").parent.text:
            sg.popup_no_titlebar(
                f"Match Day {day} is not yet active.",
                title=f"Warning - Match Day {day} not active.",
                modal=False,
                auto_close=True,
                auto_close_duration=10,
            )
            return DotMap(metadata="continue")
    questions_ans = DotMap()
    questions = [
        val.text
        for val in match_day_page.find_all("span", {"id": re.compile("q_field")})
    ]
    submitted_answers = [
        val.text.strip()
        for val in match_day_page.find_all("div", {"class": re.compile("ans_1")})
    ]
    correct_answers = [
        val.text.strip()
        for val in match_day_page.find_all("div", {"class": re.compile("ans_2")})
    ]
    points_assigned = [
        val.text.strip()
        for val in match_day_page.find_all("div", {"class": re.compile("ans_3")})
    ]
    for i in range(0, 6):
        questions_ans[i + 1].id = i + 1
        questions_ans[i + 1].question = questions[i]
        questions_ans[i + 1].submitted_ans = (
            (submitted_answers[i] if submitted_answers else "--")
            if display_answers
            else "hidden"
        )
        questions_ans[i + 1].correct_ans = (
            (correct_answers[i] if submitted_answers else "--")
            if display_answers
            else "hidden"
        )
        questions_ans[i + 1].points_assigned = (
            points_assigned[i] if submitted_answers else "--"
        )

    return sg.Window(
        f"Today's Questions - LL {season} Match Day {day}",
        layout=[
            [
                sg.Text(
                    f"Today's Questions - LL {season} Match Day {day}",
                    font=DEFAULT_FONT,
                ),
                sg.Text(expand_x=True),
            ],
            [
                sg.Column(
                    vertical_scroll_only=True,
                    expand_x=True,
                    expand_y=True,
                    layout=[
                        [
                            sg.Frame(
                                title="",
                                expand_x=True,
                                expand_y=True,
                                background_color="light gray",
                                layout=(
                                    [
                                        sg.Frame(
                                            "",
                                            layout=[
                                                [
                                                    sg.Text(
                                                        f"Q{q.id}:",
                                                        font=DEFAULT_FONT,
                                                        background_color="light gray",
                                                    ),
                                                ],
                                            ],
                                            vertical_alignment="t",
                                            background_color="light gray",
                                            relief=None,
                                            border_width=0,
                                            pad=0,
                                        ),
                                        sg.Multiline(
                                            f"{q.question}",
                                            background_color="light gray",
                                            disabled=True,
                                            no_scrollbar=True,
                                            justification="l",
                                            expand_x=True,
                                            expand_y=True,
                                            border_width=0,
                                            font=DEFAULT_FONT,
                                        ),
                                    ],
                                    [
                                        sg.Text(
                                            q.submitted_ans,
                                            expand_x=True,
                                            justification="l",
                                            background_color="orange",
                                            border_width=1,
                                            font=DEFAULT_FONT,
                                        ),
                                        sg.Text(
                                            q.points_assigned,
                                            expand_x=False,
                                            size=(2, 1),
                                            justification="c",
                                            border_width=1,
                                            relief=sg.RELIEF_GROOVE,
                                            background_color="light gray",
                                            font=DEFAULT_FONT,
                                        ),
                                    ],
                                    [
                                        sg.Text(
                                            background_color="light gray", expand_x=True
                                        ),
                                        sg.Text(
                                            q.correct_ans,
                                            expand_x=False,
                                            justification="r",
                                            background_color="light green",
                                            font=DEFAULT_FONT,
                                        ),
                                    ],
                                ),
                            )
                        ]
                        for q in questions_ans.values()
                    ],
                )
            ],
        ],
        size=(650, 850),
        resizable=True,
        finalize=True,
        modal=False,
        metadata="todays_question_window",
    )
