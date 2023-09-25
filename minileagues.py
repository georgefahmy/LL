import base64
import datetime
import os
import re
from collections import OrderedDict
from random import choice

import PySimpleGUI as sg
import requests
from bs4 import BeautifulSoup as bs
from dotmap import DotMap

BASE_URL = "https://www.learnedleague.com"
WD = os.getcwd()


def internet_on():
    """Check to see if the application has access to the internet

    Returns:
        bool: True/False flag of internet access
    """
    try:
        requests.get("https://8.8.8.8")
        return True
    except requests.exceptions.ConnectionError:
        return False


def get_full_list_of_mini_leagues():
    """Get the full list of available mini leagues. This is a large list of mini league dictonaries

    Returns:
        dict: the complete list of mini league dicts
    """
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
        if datetime.datetime.strptime(
            data[key]["date"], "%b %d, %Y"
        ) <= datetime.datetime(2014, 1, 1):
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
    """_summary_

    Args:
        data (dict): minileague dict
        search_word (str, optional): Keyword to search for in the mini league titles. Defaults to None.

    Returns:
        list: list of mini league titles matching the search
    """
    if not search_word:
        return sorted(list(data.keys()))
    else:
        return sorted(
            [val for val in list(data.keys()) if search_word.lower() in val.lower()]
        )


def get_specific_minileague(data, mini_league_key):
    """return the specific mini league based on the key

    Args:
        data (dict): full dict of mini league data
        mini_league_key (str): mini league key - the title

    Returns:
        _type_: _description_
    """
    return DotMap(data.get(mini_league_key))


def get_mini_data(specific_mini, window):
    """_summary_

    Args:
        specific_mini (dict): mini league data
        window (obj): mini league application window

    Returns:
        dict: full details of the mini league with quesitons and answers
    """
    p = 0
    page = bs(requests.get(specific_mini["url"]).content, "lxml")
    matches = {
        re.split("(Match[^M]*|Champ[C]+)", match.text)[0]: BASE_URL
        + match.a.get("href")
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
            p += 1
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
        int(
            specific_mini.get("data")
            .get("match_days")
            .get(day)
            .get(f"Q{i}")
            .get("%_correct")
        )
        for i in range(1, 7)
        for day in specific_mini.get("data").get("match_days")
    ]
    specific_mini["overall_correct"] = round(sum(total) / len(total), 2)
    window["pbar"].update(visible=False)
    window["pbar_status"].update(visible=False)
    return DotMap(specific_mini)


def q_num_finder(match_days, i):
    if int(i) % 6 == 0:
        return match_days[f"day_{int(i)//6}"][f"Q{6}"]
    else:
        return match_days[f"day_{int(i)//6+1}"][f"Q{int(i)%6}"]


def load_questions(specific_mini, window):
    """Load the mini league questions into the window and update the window formatting

    Args:
        specific_mini (dict): specific mini league complete data dictionary
        window (obj): mini league applciation window

    Returns:
        dict: the specific mini league data dictionary
    """
    i = 1
    window["mini_league_title"].update(value=specific_mini.title)
    window["mini_league_date"].update(value=specific_mini.date)
    window["mini_league_selection"].update(value=specific_mini.title)
    window["number_of_players"].update(value=specific_mini.number_of_players)

    specific_mini = get_mini_data(specific_mini, window)
    window["percent_correct"].update(value=str(specific_mini.overall_correct) + "%")
    for day in specific_mini.data.match_days.keys():
        for q in specific_mini.data.match_days[day]:
            question_object = specific_mini.data.match_days[day][q]
            question_object.index = i

            window[f"answer_{i}"].update(value="*******")
            window[f"show/hide_{i}"].update(text="Show Answer", disabled=False)
            window[f"answer_submission_{i}"].update(
                value="", disabled=False, background_color="white"
            )
            window[f"submit_answer_button_{i}"].update(disabled=False)
            window[f"question_percent_correct_{i}"].update(
                value="Submit answer to see", font=("Arial Italic", 10)
            )
            window[f"question_{i}"].update(value=question_object.question)
            w = window[f"question_{i}"].Widget
            w.configure(yscrollcommand=False, state="disabled")
            height = w.tk.call(w._w, "count", "-displaylines", "1.0", "end")
            window[f"question_{i}"].set_size((970, height + 1))
            window[f"question_{i}"].expand(
                expand_x=True, expand_y=True, expand_row=False
            )

            window.refresh()
            window[f"frame_question_{i}"].set_size(
                (
                    970,
                    (
                        75
                        + list(window[f"frame_question_{i}"].Widget.children.values())[
                            0
                        ].winfo_height()
                    ),
                )
            )
            i += 1
        window["frame_question_66"].set_size(
            (
                970,
                (
                    75
                    + list(window["frame_question_66"].Widget.children.values())[
                        0
                    ].winfo_height()
                ),
            )
        )
        window.refresh()
        window["questions_column"].contents_changed()

    specific_mini.data.score = 0
    return specific_mini


def minileague():
    if not internet_on():
        sg.popup_ok(
            "No Internet Connection.\nPlease reconnect or just play regular LL trivia.",
            font=("arial", 14),
        )
        return True
    font = "Arial", 16
    sg.theme("Reddit")
    background_color = "LightSteelBlue3"
    layout = [
        [
            sg.Frame(
                "Mini League Selection",
                size=(275, 105),
                layout=[
                    [
                        sg.Text(
                            "Mini League:",
                            font=font,
                            tooltip="Choose a Mini league to load",
                        ),
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
                ],
            ),
            sg.Frame(
                "Mini league Info",
                size=(425, 105),
                layout=[
                    [
                        sg.Text("", key="mini_league_title", font=font),
                        sg.Text(expand_x=True),
                        sg.Text("Date:", font=("Arial", 14), pad=((5, 0), (5, 5))),
                        sg.Text(
                            "",
                            font=("Arial", 14),
                            key="mini_league_date",
                            pad=((0, 5), (5, 5)),
                        ),
                    ],
                    [
                        sg.Text(
                            "% Correct: ", font=("Arial", 14), pad=((5, 0), (5, 5))
                        ),
                        sg.Text(
                            "",
                            key="percent_correct",
                            font=("Arial", 14),
                            pad=((0, 5), (5, 5)),
                        ),
                        sg.Text(expand_x=True),
                        sg.Text(
                            "Num Players: ", font=("Arial", 14), pad=((5, 0), (5, 5))
                        ),
                        sg.Text(
                            "",
                            key="number_of_players",
                            font=("Arial", 14),
                            pad=((0, 5), (5, 5)),
                        ),
                    ],
                    [
                        sg.Text("Score:", font=("Arial", 14), pad=((5, 0), (5, 5))),
                        sg.Text(
                            "", font=("Arial", 14), key="score", pad=((0, 5), (5, 5))
                        ),
                    ],
                ],
            ),
            sg.Frame(
                "Options",
                size=(275, 105),
                layout=[
                    [
                        sg.Text("Loading...", key="pbar_status", font=("Arial", 12)),
                        sg.ProgressBar(
                            66, orientation="horizontal", key="pbar", size=(10, 10)
                        ),
                        sg.Text(expand_x=True, key="pbar_spacer"),
                        sg.Button(
                            "Reset Quiz",
                            key="full_reset",
                            tooltip="""
                                Click this button to fully reset the quiz
                                erasing all answers.""",
                        ),
                    ],
                    [
                        sg.Text(expand_x=True),
                        sg.Button("Random", key="random_mini_league"),
                    ],
                ],
            ),
        ],
        [
            sg.Column(
                expand_x=True,
                expand_y=True,
                scrollable=True,
                size=(975, 615),
                vertical_scroll_only=True,
                justification="c",
                element_justification="c",
                key="questions_column",
                layout=[
                    [
                        sg.Frame(
                            f"Question {i}",
                            size=(970, 300),
                            expand_x=True,
                            expand_y=False,
                            background_color=background_color,
                            key=f"frame_question_{i}",
                            layout=[
                                [
                                    sg.Multiline(
                                        key=f"question_{i}",
                                        font=("Arial", 20),
                                        disabled=True,
                                        auto_size_text=True,
                                        auto_refresh=True,
                                        no_scrollbar=True,
                                        expand_x=True,
                                        expand_y=True,
                                        enable_events=True,
                                        right_click_menu=[
                                            "&Right",
                                            ["!Lookup Selection"],
                                        ],
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
                                    sg.Text(
                                        expand_x=True, background_color=background_color
                                    ),
                                    sg.Checkbox(
                                        "Ans Override",
                                        key=f"correct_override_{i}",
                                        disabled=True,
                                        background_color=background_color,
                                        enable_events=True,
                                    ),
                                    sg.Text(
                                        "%Corr:",
                                        font=font,
                                        tooltip="Percent Correct (all players)",
                                        background_color=background_color,
                                    ),
                                    sg.Text(
                                        "Submit answer to see",
                                        key=f"question_percent_correct_{i}",
                                        font=("Arial Italic", 10),
                                        tooltip="Percent Correct (all players)",
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
    filtered_results = search_minileagues(data)

    font = "Arial", 16

    icon_file = WD + "/resources/ll_app_logo.png"
    sg.set_options(icon=base64.b64encode(open(str(icon_file), "rb").read()))
    window = sg.Window(
        "LL Mini Leagues",
        layout=layout,
        finalize=True,
        return_keyboard_events=True,
        metadata="minileague_window",
    )

    specific_mini = get_specific_minileague(data, choice(filtered_results))
    specific_mini = load_questions(specific_mini, window)

    window["mini_league_selection"].update(
        values=filtered_results, value=specific_mini.title
    )
    [window[f"question_{i}"].bind("<ButtonPress-2>", "press") for i in range(1, 67)]
    [
        window[f"question_{i}"].bind("<ButtonPress-1>", "click_here")
        for i in range(1, 67)
    ]
    [
        window[f"answer_submission_{i}"].bind("<Return>", f"_submit_answer_button_{i}")
        for i in range(1, 67)
    ]

    return window, data, filtered_results, specific_mini
