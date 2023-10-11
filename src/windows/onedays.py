import base64
import datetime
import json
import os
import re
import unicodedata
from random import choice

import PySimpleGUI as sg
import requests
from bs4 import BeautifulSoup as bs

from ..constants import BASE_URL, MODKOS, WD


def internet_on():
    try:
        requests.get("https://8.8.8.8")
        return True
    except requests.exceptions.ConnectionError:
        return False


def get_full_list_of_onedays():
    data = {
        info.find("td", {"class": "std-left"}).text: {
            "title": info.find("td", {"class": "std-left"}).text,
            "url": BASE_URL + info.find("td", {"class": "std-left"}).a.get("href"),
            "date": info.find("td", {"class": "std-midleft"}).text,
        }
        for info in bs(
            requests.get(BASE_URL + "/oneday/onedaysalpha.php").content, "html.parser"
        ).find_all("tr")[1:-1]
    }

    for key in list(data.keys()):
        if (
            datetime.datetime.strptime(data[key]["date"], "%b %d, %Y")
            >= datetime.datetime.now()
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


def search_onedays(data, search_word=None):
    if not search_word:
        return list(data.keys())
    else:
        return [val for val in list(data.keys()) if search_word.lower() in val.lower()]


def get_specific_oneday(data, onedaykey):
    return data.get(onedaykey)


def get_oneday_data(oneday):
    if os.path.isfile(
        os.path.expanduser("~")
        + f"/.LearnedLeague/onedays/{re.sub(' ','_', oneday['title'])}.json"
    ):
        print("file exists")
        with open(
            os.path.expanduser("~")
            + f"/.LearnedLeague/onedays/{re.sub(' ','_', oneday['title'])}.json",
            "r",
        ) as fp:
            oneday = json.load(fp)
            return oneday

    page = bs(requests.get(oneday["url"]).content, "lxml")
    try:
        metrics_page = bs(
            requests.get(
                BASE_URL + page.find("ul", {"id": "profilestabs"}).a.get("href")
            ).content,
            "lxml",
        )
    except:
        metrics_page = None
    try:
        questions = [
            ". ".join(q.text.split(".")[1:]).strip()
            for q in page.find(
                "div", {"id": "qs_close", "class": "qdivshow_wide"}
            ).find_all("p")
        ]
    except:
        return None
    answers = [
        a.text.strip().split("\n")[-1]
        for a in page.find(
            "div", {"id": "qs_close", "class": "qdivshow_wide"}
        ).find_all("div", {"class": "answer3"})
    ]
    if metrics_page:
        question_metrics = [
            int(m.text.strip().split()[1])
            for m in metrics_page.find("div", {"class": "q_container"})
            .find("table", {"class": "tbl_q"})
            .find_all("tr")[1:]
        ]
        percentile_info = {
            int(
                metrics_page.find("div", {"class": "pctile_container"})
                .find_all("td", {"class": "pr"})[i]
                .text
            ): int(
                metrics_page.find("div", {"class": "pctile_container"})
                .find_all("td", {"class": None})[i]
                .text
            )
            for i, _ in enumerate(
                metrics_page.find("div", {"class": "pctile_container"}).find_all(
                    "td", {"class": "pr"}
                )
            )
            if unicodedata.normalize(
                "NFKD",
                metrics_page.find("div", {"class": "pctile_container"})
                .find_all("td", {"class": None})[i]
                .text,
            )
            != " "
        }
        number_of_players = sum(
            [
                int(row.find_all("td")[1].text)
                for row in metrics_page.find(
                    "div", {"class": "byl_container"}
                ).find_all("tr")[1:]
            ]
        )
    check_blurb = page.find("div", {"id": "blurb_close"})
    if check_blurb:
        blurb = re.sub(
            "[\r\n]+", "\n", "".join(check_blurb.text.split("blurb")[1:]).strip()
        )
    else:
        blurb = ""
    if "ModKos" in blurb.split():
        ratings = set(["G", "PG", "PG-13", "R", "X"])
        ind = [
            i
            for i, e in enumerate(
                [val.replace(".", "").strip() for val in blurb.split()]
            )
            if e in ratings
        ]
        if ind:
            modkos_rating = blurb.split()[ind[0]].replace(".", "").strip()
        else:
            modkos_rating = "None"
    else:
        modkos_rating = "None"
    oneday["blurb"] = blurb
    oneday["difficulty_rating"] = modkos_rating.replace(",", "")
    oneday["overall_average"] = round(sum(question_metrics) / len(question_metrics), 2)
    oneday["90th_percentile"] = percentile_info.get(90) or ""
    oneday["50th_percentile"] = percentile_info.get(50) or ""
    oneday["10th_percentile"] = percentile_info.get(10) or ""
    oneday["all_percentile"] = percentile_info
    oneday["number_of_players"] = number_of_players
    oneday_data = {}
    for j, question in enumerate(questions):
        oneday_data[str(j + 1)] = {
            "_question": question,
            "answer": answers[j],
            "percent": question_metrics[j],
            "question_num": str(j + 1),
        }
    oneday["data"] = oneday_data
    return oneday


def oneday_main():
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
                "OneDay Selection",
                size=(325, 105),
                layout=[
                    [
                        sg.Text("Search:", font=font),
                        sg.Input(
                            "",
                            key="oneday_search",
                            font=font,
                            size=(14, 1),
                            expand_x=True,
                        ),
                        sg.Button("Search", key="oneday_filter_search"),
                    ],
                    [
                        sg.Text(
                            "OneDay:", font=font, tooltip="Choose a OneDay to load"
                        ),
                        sg.Combo(
                            values=[],
                            key="oneday_selection",
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
                        sg.Button("Random", key="random_oneday"),
                    ],
                ],
            ),
            sg.Frame(
                "OneDay Info",
                size=(325, 105),
                layout=[
                    [sg.Text("", key="oneday_title", font=font)],
                    [
                        sg.Text(
                            "Difficulty: ",
                            font=("Arial", 14),
                            pad=((5, 0), (5, 5)),
                            enable_events=True,
                            key="difficulty_tooltip",
                            tooltip="Click to read the definition of the difficulty",
                            metadata=MODKOS,
                        ),
                        sg.Text(
                            "",
                            key="difficulty",
                            font=("Arial", 14),
                            expand_x=True,
                            pad=((0, 5), (5, 5)),
                        ),
                        sg.Text("Date:", font=("Arial", 14), pad=((5, 0), (5, 5))),
                        sg.Text(
                            "",
                            font=("Arial", 14),
                            key="oneday_date",
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
                            tooltip="Click this button to reset the quiz.",
                        ),
                    ],
                    [sg.HorizontalSeparator()],
                    [
                        sg.Text("Pts Percentile:", font=("Arial Bold", 14)),
                        sg.Text("90th:", font=("Arial", 14), pad=0),
                        sg.Text(
                            "", key="90th_percent", font=("Arial Italic", 14), pad=0
                        ),
                        sg.Text("50th:", font=("Arial", 14), pad=0),
                        sg.Text(
                            "", key="50th_percent", font=("Arial Italic", 14), pad=0
                        ),
                        sg.Text("10th:", font=("Arial", 14), pad=0),
                        sg.Text(
                            "", key="10th_percent", font=("Arial Italic", 14), pad=0
                        ),
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
                size=(975, 650),
                key="questions_column",
                vertical_scroll_only=True,
                layout=[
                    [
                        sg.Frame(
                            f"Question {i}",
                            size=(970, 300),
                            expand_x=True,
                            expand_y=True,
                            key=f"frame_question_{i}",
                            background_color=background_color,
                            layout=[
                                [
                                    sg.Multiline(
                                        key=f"question_{i}",
                                        font=("Arial", 20),
                                        disabled=True,
                                        size=(None, 8),
                                        no_scrollbar=True,
                                        expand_x=True,
                                        # expand_y=True,
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
                                        text="*******",
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
                                        disabled=False,
                                        background_color=background_color,
                                        tooltip="""If correct - get points equal to % of
                                                people who got the question wrong""",
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
                                        background_color="white",
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
                                        tooltip=(
                                            "Automated  checking may be incorrect.\n"
                                            + "Use this checkbox to override an "
                                            + "incorrect answer assessment "
                                            + "\n(both right and wrong answers)."
                                        ),
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
                    for i in range(1, 13)
                ],
            )
        ],
    ]

    list_of_onedays = (
        get_full_list_of_onedays()
    )  # one time use? store this data in a json file?
    font = "Arial", 16

    icon_file = WD + "/resources/ll_app_logo.png"
    sg.set_options(icon=base64.b64encode(open(str(icon_file), "rb").read()))
    window = sg.Window(
        "OneDay Trivia",
        layout=layout,
        finalize=True,
        return_keyboard_events=True,
        metadata="oneday_window",
    )

    window["oneday_selection"].update(values=search_onedays(list_of_onedays))

    filtered_results = search_onedays(list_of_onedays)
    oneday = get_oneday_data(
        get_specific_oneday(list_of_onedays, choice(filtered_results))
    )
    while not oneday:
        oneday = get_oneday_data(
            get_specific_oneday(list_of_onedays, choice(filtered_results))
        )

    data = oneday["data"]
    i = 1
    score = 0
    num_of_money_questions_left = 5

    window["oneday_title"].update(value=oneday["title"])
    window["difficulty"].update(value=oneday["difficulty_rating"])
    window["percent_correct"].update(value=str(oneday["overall_average"]) + "%")
    window["blurb_text"].update(value=oneday["blurb"])
    window["oneday_date"].update(value=oneday["date"])
    window["oneday_selection"].update(value=oneday["title"])
    window["90th_percent"].update(value=oneday["90th_percentile"])
    window["50th_percent"].update(value=oneday["50th_percentile"])
    window["10th_percent"].update(value=oneday["10th_percentile"])
    window["number_of_players"].update(value=oneday["number_of_players"])
    window["score"].update(value=score)
    window["num_of_money_questions_left"].update(value=num_of_money_questions_left)

    for i in data.keys():
        window[f"question_{i}"].update(value=data[i].get("_question"))
        window[f"answer_submission_{i}"].bind("<Return>", f"_submit_answer_button_{i}")

    [window[f"question_{i}"].bind("<ButtonPress-2>", "press") for i in range(1, 13)]
    [
        window[f"question_{i}"].bind("<ButtonPress-1>", "click_here")
        for i in range(1, 13)
    ]
    [
        window[f"answer_submission_{i}"].bind("<Return>", f"_submit_answer_button_{i}")
        for i in range(1, 13)
    ]
    for i in range(1, 13):
        window[f"correct_override_{i}"].TooltipObject.timeout = 300

    window.refresh()
    window["questions_column"].contents_changed()

    return window, data, oneday, list_of_onedays, filtered_results
