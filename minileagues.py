import requests
import datetime
import webbrowser
import wikipedia
import unicodedata
import base64
import os
import PySimpleGUI as sg
import re
import json

from bs4 import BeautifulSoup as bs
from random import choice
from pprint import pprint
from answer_correctness import combined_correctness
from PyDictionary import PyDictionary
from time import sleep
from collections import OrderedDict
from dotmap import DotMap


BASE_URL = "https://www.learnedleague.com"
WD = os.getcwd()


def get_full_list_of_mini_leagues():
    data = {
        info.find("td", {"class": "std-left"}).text: {
            "title": info.find("td", {"class": "std-left"}).text,
            "url": BASE_URL + info.find("td", {"class": "std-left"}).a.get("href"),
            "date": info.find("td", {"class": "std-midleft"}).text,
            "number_of_players": info.find("td", {"class": "std-mid"}).text,
        }
        for info in bs(requests.get(BASE_URL + "/mini/").content, "html.parser")
        .find("table", {"class": "std min"})
        .find("tbody")
        .find_all("tr")[3:-1]
        if info.find("td", {"class": "std-left"})
    }
    for key in list(data.keys()):
        if datetime.datetime.strptime(data[key]["date"], "%b %d, %Y") <= datetime.datetime(
            2014, 1, 1
        ):
            del data[key]

    for key in list(data.keys()):
        if any(
            [
                val in key
                for val in [
                    "Just Audio",
                    "Just Images",
                    "Just Memes",
                    "Just GIFs",
                    "Just Fuzzy Images",
                ]
            ]
        ):
            del data[key]
    return data


def search_minileagues(data, search_word=None):
    if not search_word:
        return list(data.keys())
    else:
        return [val for val in list(data.keys()) if search_word.lower() in val.lower()]


def get_specific_minileague(data, mini_league_key):
    return data.get(mini_league_key)


def get_mini_data(specific_mini):
    page = bs(requests.get(specific_mini["url"]).content, "lxml")
    matches = {
        re.split("(Match[^M]*|Champ[C]+)", match.text)[0]: BASE_URL + match.a.get("href")
        for match in page.find("table", {"class": "mtch"}).find_all("tr")
        if match.text
    }
    for key in list(matches.keys()):
        if "12" in matches[key]:
            del matches[key]
    mini_details = {"raw_matches": matches}
    mini_details["match_days"] = OrderedDict()
    for i, match in enumerate(mini_details["raw_matches"].values()):
        mini_details["match_days"]["day_" + str(i + 1)] = {}
        match_page = bs(requests.get(match).content, "lxml")
        for q, a in zip(
            match_page.find_all(True, {"class": ["ind-Q20", "a-red"]})[0::2],
            match_page.find_all(True, {"class": ["ind-Q20", "a-red"]})[1::2],
        ):
            mini_details["match_days"]["day_" + str(i + 1)][
                q.text.strip().split("-")[0].strip().split(".")[0]
            ] = {
                "question": "-".join(q.text.strip().split("-")[1:]).strip(),
                "answer": a.text.strip(),
            }
        for j in range(1, 7):
            mini_details["match_days"]["day_" + str(i + 1)][f"Q{j}"]["%_correct"] = [
                v.text.strip()
                for v in match_page.find("table", {"class": "std sortable"})
                .find("tfoot")
                .find_all("td", {"class": "ind-Q3-t"})
            ][2:-1][j - 1]
    specific_mini["data"] = mini_details
    total = [
        int(specific_mini.get("data").get("match_days").get(day).get(f"Q{i}").get("%_correct"))
        for i in range(1, 7)
        for day in specific_mini.get("data").get("match_days")
    ]
    specific_mini["overall_correct"] = round(sum(total) / len(total), 2)
    return DotMap(specific_mini)


data = get_full_list_of_mini_leagues()
filtered_results = search_minileagues(data)
specific_mini = get_specific_minileague(data, choice(filtered_results))
specific_mini = get_mini_data(specific_mini)


font = "Arial", 16
sg.theme("Reddit")
background_color = "LightSteelBlue3"
layout = [
    [
        sg.Frame(
            "Mini League Selection",
            size=(325, 105),
            layout=[
                [
                    sg.Text("Search:", font=font),
                    sg.Input("", key="mini_league_search", font=font, size=(14, 1), expand_x=True),
                    sg.Button("Search", key="mini_league_filter_search"),
                ],
                [
                    sg.Text("mini_league:", font=font, tooltip="Choose a Mini league to load"),
                    sg.Combo(
                        values=[],
                        key="mini_league_selection",
                        font=font,
                        size=(40, 1),
                        expand_x=True,
                        readonly=True,
                        enable_events=True,
                    ),
                ],
                [
                    sg.Button("Show Description", key="show_hide_blurb"),
                    sg.Text(expand_x=True),
                    sg.Button("Random", key="random_mini_league"),
                ],
            ],
        ),
        sg.Frame(
            "Mini league Info",
            size=(325, 105),
            layout=[
                [sg.Text("", key="mini_league_title", font=font)],
                [
                    sg.Text(
                        "Difficulty: ",
                        font=("Arial", 14),
                        pad=((5, 0), (5, 5)),
                        enable_events=True,
                        key="difficulty_tooltip",
                        tooltip="https://www.learnedleague.com/images/misc/ModKos.png?t=1649",
                        metadata="https://www.learnedleague.com/images/misc/ModKos.png?t=1649",
                    ),
                    sg.Text(
                        "",
                        key="difficulty",
                        font=("Arial", 14),
                        expand_x=True,
                        pad=((0, 5), (5, 5)),
                    ),
                    sg.Text("Date:", font=("Arial", 14), pad=((5, 0), (5, 5))),
                    sg.Text("", font=("Arial", 14), key="mini_league_date", pad=((0, 5), (5, 5))),
                ],
                [
                    sg.Text("% Correct: ", font=("Arial", 14), pad=((5, 0), (5, 5))),
                    sg.Text("", key="percent_correct", font=("Arial", 14), pad=((0, 5), (5, 5))),
                    sg.Text(expand_x=True),
                    sg.Text("Num Players: ", font=("Arial", 14), pad=((5, 0), (5, 5))),
                    sg.Text("", key="number_of_players", font=("Arial", 14), pad=((0, 5), (5, 5))),
                ],
            ],
        ),
        sg.Frame(
            "Question Metrics",
            size=(325, 105),
            layout=[
                [
                    sg.Text("Your Current Score:", font=font),
                    sg.Text("", key="score", font=font),
                    sg.Text(expand_x=True),
                    sg.Button(
                        "Reset Quiz",
                        key="full_reset",
                        tooltip="Click this button to fully reset the quiz erasing all answers.",
                    ),
                ],
                [sg.HorizontalSeparator()],
                [
                    sg.Text("Pts Percentile:", font=("Arial Bold", 14)),
                    sg.Text("90th:", font=("Arial", 14), pad=0),
                    sg.Text("", key="90th_percent", font=("Arial Italic", 14), pad=0),
                    sg.Text("50th:", font=("Arial", 14), pad=0),
                    sg.Text("", key="50th_percent", font=("Arial Italic", 14), pad=0),
                    sg.Text("10th:", font=("Arial", 14), pad=0),
                    sg.Text("", key="10th_percent", font=("Arial Italic", 14), pad=0),
                ],
                [
                    sg.Text("Money Questions Remaining: ", font=font),
                    sg.Text(f"({5})", font=font, key="num_of_money_questions_left"),
                ],
            ],
        ),
    ],
    [
        sg.Frame(
            "Blurb",
            expand_x=True,
            key="blurb_frame",
            size=(300, 1),
            layout=[
                [
                    sg.Multiline(
                        "",
                        expand_x=True,
                        expand_y=True,
                        disabled=True,
                        no_scrollbar=True,
                        key="blurb_text",
                        font=("Arial", 14),
                    )
                ],
            ],
        )
    ],
    [
        sg.Column(
            expand_x=True,
            expand_y=True,
            scrollable=True,
            size=(975, 615),
            vertical_scroll_only=True,
            layout=[
                [
                    sg.Frame(
                        f"Question {i}",
                        size=(970, 300),
                        expand_x=True,
                        expand_y=True,
                        background_color=background_color,
                        layout=[
                            [
                                sg.Multiline(
                                    key=f"question_{i}",
                                    font=("Arial", 20),
                                    disabled=True,
                                    no_scrollbar=True,
                                    expand_x=True,
                                    expand_y=True,
                                    enable_events=True,
                                    right_click_menu=["&Right", ["!Lookup Selection"]],
                                )
                            ],
                            [
                                sg.Button(
                                    "Show Answer",
                                    key=f"show/hide_{i}",
                                    size=(12, 1),
                                    tooltip="Reveal the Answer - (s)",
                                    mouseover_colors=("black", "white"),
                                    disabled_button_color=("black", "gray"),
                                ),
                                sg.Text(
                                    key=f"answer_{i}",
                                    font=("Arial", 16),
                                    size=(10, 1),
                                    expand_x=True,
                                    background_color=background_color,
                                ),
                            ],
                            [
                                sg.Checkbox(
                                    "Money Question",
                                    key=f"money_check_{i}",
                                    font=font,
                                    background_color=background_color,
                                    tooltip="If correct - get points equal to % of people who got the question wrong",
                                ),
                            ],
                            [
                                sg.Text(
                                    "Answer: ",
                                    font=("Arial", 16),
                                    background_color=background_color,
                                ),
                                sg.Input(
                                    "",
                                    key=f"answer_submission_{i}",
                                    font=("Arial", 16),
                                    expand_x=True,
                                    use_readonly_for_disable=True,
                                ),
                                sg.Button(
                                    "Submit Answer",
                                    key=f"submit_answer_button_{i}",
                                    disabled_button_color=("black", "gray"),
                                    bind_return_key=True,
                                ),
                                sg.Text(expand_x=True, background_color=background_color),
                                sg.Checkbox(
                                    "Ans Override",
                                    key=f"correct_override_{i}",
                                    disabled=True,
                                    background_color=background_color,
                                    enable_events=True,
                                    tooltip=(
                                        "Automated answer checking may be incorrect.\n"
                                        + "Use this checkbox to override an incorrect answer assessment "
                                        + "\n(both right and wrong answers)."
                                    ),
                                ),
                                sg.Text(
                                    "%Corr:",
                                    font=font,
                                    tooltip="Correct Answer Percentage (all players)",
                                    background_color=background_color,
                                ),
                                sg.Text(
                                    "Submit answer to see",
                                    key=f"question_percent_correct_{i}",
                                    font=("Arial Italic", 10),
                                    tooltip="Correct Answer Percentage (all players)",
                                    background_color=background_color,
                                ),
                            ],
                        ],
                    )
                ]
                for i in range(1, 13)
            ],
        )
    ],
]
