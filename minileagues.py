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
        return sorted(list(data.keys()))
    else:
        return sorted([val for val in list(data.keys()) if search_word.lower() in val.lower()])


def get_specific_minileague(data, mini_league_key):
    return DotMap(data.get(mini_league_key))


def get_mini_data(specific_mini, window):
    p = 0
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
            p+=1
            window["pbar"].update(current_count=p)

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
    window["pbar"].update(visible=False)
    window["pbar_status"].update(visible=False)
    return DotMap(specific_mini)

def q_num_finder(match_days, i):
    if int(i)%6 == 0:
        return match_days[f"day_{int(i)//6}"][f"Q{6}"]
    else:
        return match_days[f"day_{int(i)//6+1}"][f"Q{int(i)%6}"]


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
                    sg.Text("Mini League:", font=font, tooltip="Choose a Mini league to load"),
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
            "Questions Reset",
            size=(325, 105),
            layout=[
                [
                    sg.Text("Loading...", key="pbar_status", font=("Arial", 12)),
                    sg.ProgressBar(66, orientation="horizontal",key="pbar", size=(15,10)),
                    sg.Text(expand_x=True, key="pbar_spacer"),
                    sg.Button(
                        "Reset Quiz",
                        key="full_reset",
                        tooltip="Click this button to fully reset the quiz erasing all answers.",
                    ),
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
                for i in range(1, 67)
            ],
        )
    ],
]

data = get_full_list_of_mini_leagues()
font = "Arial", 16

icon_file = WD + "/resources/ll_app_logo.png"
sg.set_options(icon=base64.b64encode(open(str(icon_file), "rb").read()))
window = sg.Window("LL Mini Leagues", layout=layout, finalize=True, return_keyboard_events=True)

window["mini_league_selection"].update(values=search_minileagues(data))

for i in range(1, 13):
    window[f"correct_override_{i}"].TooltipObject.timeout = 300

filtered_results = search_minileagues(data)
specific_mini = get_specific_minileague(data, choice(filtered_results))
i = 1
submitted_answers = {}
window["mini_league_title"].update(value=specific_mini.title)
window["mini_league_date"].update(value=specific_mini.date)
window["mini_league_selection"].update(value=specific_mini.title)
window["number_of_players"].update(value=specific_mini.number_of_players)

specific_mini = get_mini_data(specific_mini, window)
window["percent_correct"].update(value=str(specific_mini.overall_correct) + "%")
for day in specific_mini.data.match_days.keys():
    for q in specific_mini.data.match_days[day]:
        question_object = specific_mini.data.match_days[day][q]


        window[f"question_{i}"].update(value=question_object.question)
        window[f"answer_{i}"].update(value="*******")
        window[f"show/hide_{i}"].update(text="Show Answer", disabled=False)
        window[f"answer_submission_{i}"].update(value="", disabled=False, background_color="white")
        window[f"submit_answer_button_{i}"].update(disabled=False)
        window[f"question_percent_correct_{i}"].update(
            value="Submit answer to see", font=("Arial Italic", 10)
        )
        question_object.index= i
        i+=1

while True:
    event, values = window.read()

    if event in (None, "Quit", sg.WIN_CLOSED):
        window.close()
        break

    if event == "random_mini_league":
        specific_mini = get_specific_minileague(data, choice(filtered_results))
        i = 1
        submitted_answers = {}
        window["mini_league_title"].update(value=specific_mini.title)
        window["mini_league_date"].update(value=specific_mini.date)
        window["mini_league_selection"].update(value=specific_mini.title)
        window["number_of_players"].update(value=specific_mini.number_of_players)
        specific_mini = get_mini_data(specific_mini, window)
        window["percent_correct"].update(value=str(specific_mini.overall_correct) + "%")

        for day in specific_mini.data.match_days.keys():
            for q in specific_mini.data.match_days[day]:
                question_object = specific_mini.data.match_days[day][q]

                window[f"question_{i}"].update(value=question_object.question)
                window[f"answer_{i}"].update(value="*******")
                window[f"show/hide_{i}"].update(text="Show Answer", disabled=False)
                window[f"answer_submission_{i}"].update(value="", disabled=False, background_color="white")
                window[f"submit_answer_button_{i}"].update(disabled=False)
                window[f"question_percent_correct_{i}"].update(
                    value="Submit answer to see", font=("Arial Italic", 10)
                )
                question_object.index= i
                i+=1

    if event == "mini_league_filter_search":
        filtered_results = search_minileagues(
            list_of_onedays, search_word=values["mini_league_search"]
        ) or [""]
        window["mini_league_search"].update(value="")
        if not filtered_results[0]:
            filtered_results = search_minileagues(list_of_onedays)
            sg.popup_error(
                "WARNING - No Results",
                font=("Arial", 16),
                auto_close=True,
                auto_close_duration=5,
            )
            continue

        specific_mini = get_specific_minileague(data, choice(filtered_results))

        i = 1
        submitted_answers = {}
        window["mini_league_title"].update(value=specific_mini.title)
        window["mini_league_date"].update(value=specific_mini.date)
        window["mini_league_selection"].update(value=specific_mini.title)
        window["number_of_players"].update(value=specific_mini.number_of_players)
        specific_mini = get_mini_data(specific_mini, window)
        window["percent_correct"].update(value=str(specific_mini.overall_correct) + "%")

        for day in specific_mini.data.match_days.keys():
            for q in specific_mini.data.match_days[day]:
                question_object = specific_mini.data.match_days[day][q]

                window[f"question_{i}"].update(value=question_object.question)
                window[f"answer_{i}"].update(value="*******")
                window[f"show/hide_{i}"].update(text="Show Answer", disabled=False)
                window[f"answer_submission_{i}"].update(value="", disabled=False, background_color="white")
                window[f"submit_answer_button_{i}"].update(disabled=False)
                window[f"question_percent_correct_{i}"].update(
                    value="Submit answer to see", font=("Arial Italic", 10)
                )
                question_object.index= i
                i+=1

    if event in ("mini_league_selection", "full_reset"):
        if specific_mini.title != values["mini_league_selection"]:
            window["pbar_spacer"].update(visible=False)
            window["full_reset"].update(visible=False)
            window["pbar_status"].update(visible=True)
            window["pbar"].update(visible=True, current_count=0)
            window["pbar_spacer"].update(visible=True)
            window["full_reset"].update(visible=True)
            window.refresh()
            specific_mini = get_specific_minileague(data, values["mini_league_selection"])


            window["mini_league_title"].update(value=specific_mini.title)
            window["mini_league_date"].update(value=specific_mini.date)
            window["mini_league_selection"].update(value=specific_mini.title)
            window["number_of_players"].update(value=specific_mini.number_of_players)
            specific_mini = get_mini_data(specific_mini, window)
            window["percent_correct"].update(value=str(specific_mini.overall_correct) + "%")

        submitted_answers = {}
        i = 1
        for day in specific_mini.data.match_days.keys():
            for q in specific_mini.data.match_days[day]:
                question_object = specific_mini.data.match_days[day][q]

                window[f"question_{i}"].update(value=question_object.question)
                window[f"answer_{i}"].update(value="*******")
                window[f"show/hide_{i}"].update(text="Show Answer", disabled=False)
                window[f"answer_submission_{i}"].update(value="", disabled=False, background_color="white")
                window[f"submit_answer_button_{i}"].update(disabled=False)
                window[f"question_percent_correct_{i}"].update(
                    value="Submit answer to see", font=("Arial Italic", 10)
                )
                question_object.index= i
                i+=1

    if "show/hide" in event:
        if window.find_element_with_focus().Key in ("mini_league_search", "answer_submission"):
            continue

        i = event.split("_")[-1]

        question_object = q_num_finder(specific_mini.data.match_days, i)
        answer = question_object.answer

        window[f"answer_submission_{i}"].update(disabled=True)
        window[f"submit_answer_button_{i}"].update(disabled=True)
        window[f"correct_override_{i}"].update(disabled=True)

        if window[f"show/hide_{i}"].get_text() == "Show Answer":
            try:
                window[f"show/hide_{i}"].update(text="Hide Answer")

                window[f"answer_{i}"].update(value=answer, font=("Arial", 16))
            except:
                continue

        elif window[f"show/hide_{i}"].get_text() == "Hide Answer":
            window[f"show/hide_{i}"].update(text="Show Answer")
            try:
                if answer:
                    window[f"answer_{i}"].update(value="******")
                else:
                    window[f"answer_{i}"].update(value="")
            except:
                continue
