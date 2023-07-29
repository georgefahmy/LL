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


def internet_on():
    try:
        requests.get("https://8.8.8.8")
        return True
    except requests.exceptions.ConnectionError as err:
        return False


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
        int(specific_mini.get("data").get("match_days").get(day).get(f"Q{i}").get("%_correct"))
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
            window[f"question_{i}"].expand(expand_x=True, expand_y=True, expand_row=False)

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
        window[f"frame_question_66"].set_size(
            (
                970,
                (
                    75
                    + list(window[f"frame_question_66"].Widget.children.values())[0].winfo_height()
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
                            "", font=("Arial", 14), key="mini_league_date", pad=((0, 5), (5, 5))
                        ),
                    ],
                    [
                        sg.Text("% Correct: ", font=("Arial", 14), pad=((5, 0), (5, 5))),
                        sg.Text(
                            "", key="percent_correct", font=("Arial", 14), pad=((0, 5), (5, 5))
                        ),
                        sg.Text(expand_x=True),
                        sg.Text("Num Players: ", font=("Arial", 14), pad=((5, 0), (5, 5))),
                        sg.Text(
                            "", key="number_of_players", font=("Arial", 14), pad=((0, 5), (5, 5))
                        ),
                    ],
                    [
                        sg.Text("Score:", font=("Arial", 14), pad=((5, 0), (5, 5))),
                        sg.Text("", font=("Arial", 14), key="score", pad=((0, 5), (5, 5))),
                    ],
                ],
            ),
            sg.Frame(
                "Options",
                size=(275, 105),
                layout=[
                    [
                        sg.Text("Loading...", key="pbar_status", font=("Arial", 12)),
                        sg.ProgressBar(66, orientation="horizontal", key="pbar", size=(10, 10)),
                        sg.Text(expand_x=True, key="pbar_spacer"),
                        sg.Button(
                            "Reset Quiz",
                            key="full_reset",
                            tooltip="Click this button to fully reset the quiz erasing all answers.",
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
    [window[f"question_{i}"].bind("<ButtonPress-2>", "press") for i in range(1, 67)]
    [window[f"question_{i}"].bind("<ButtonPress-1>", "click_here") for i in range(1, 67)]
    [
        window[f"answer_submission_{i}"].bind("<Return>", f"_submit_answer_button_{i}")
        for i in range(1, 67)
    ]

    filtered_results = search_minileagues(data)
    specific_mini = get_specific_minileague(data, choice(filtered_results))
    specific_mini = load_questions(specific_mini, window)
    while True:
        event, values = window.read()

        if event in (None, "Quit", sg.WIN_CLOSED):
            window.close()
            break

        if "Escape" in event:
            window["question_1"].set_focus()

        if "press" in event:
            i = int(event.split("_")[-1].split("press")[0])

            question_widget = window[f"question_{i}"].Widget
            selection_ranges = question_widget.tag_ranges(sg.tk.SEL)
            if selection_ranges:
                window[f"question_{i}"].set_right_click_menu(["&Right", ["Lookup Selection"]])
                selected_text = question_widget.get(*selection_ranges)
            else:
                window[f"question_{i}"].set_right_click_menu(["&Right", ["!Lookup Selection"]])
                continue

        if event == "Lookup Selection":
            if len(selected_text.split()) == 1:
                # selected text is a single word, so just do a lookup
                try:
                    definition = PyDictionary().meaning(selected_text)

                    result = (
                        selected_text
                        + "\n"
                        + "\n".join(
                            [key + ": " + ", ".join(value) for key, value in definition.items()]
                        )
                    )
                    print(result)
                    sg.popup_ok(result, title="Dictionary Result", font=("Arial", 16))
                    continue
                except:
                    result = "No results available - Try another search."
            else:
                try:
                    result = wikipedia.summary(
                        selected_text, sentences=2, auto_suggest=True, redirect=True
                    )
                except:
                    result = "No results available - Try another search."

                sg.popup_ok(result, title="Wiki Summary", font=("Arial", 16))

        if event == "random_mini_league":
            specific_mini = get_specific_minileague(data, choice(filtered_results))
            specific_mini = load_questions(specific_mini, window)

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

            specific_mini = load_questions(specific_mini, window)

        if "show/hide" in event:
            if window.find_element_with_focus().Key in ("answer_submission"):
                continue

            i = event.split("_")[-1]

            question_object = q_num_finder(specific_mini.data.match_days, i)
            answer = question_object.answer

            window[f"answer_submission_{i}"].update(disabled=True)
            window[f"submit_answer_button_{i}"].update(disabled=True)
            window[f"correct_override_{i}"].update(disabled=True)
            window[f"question_percent_correct_{i}"].update(
                value=question_object["%_correct"] + "%", font=font
            )

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

        if "submit_answer_button" in event:
            i = event.split("_")[-1]
            if not values[f"answer_submission_{i}"]:
                continue

            submitted_answer = values[f"answer_submission_{i}"].lower()
            question_object = q_num_finder(specific_mini.data.match_days, i)
            answer = question_object.answer
            window[f"answer_{i}"].update(value=answer, font=("Arial", 16))
            window[f"answer_submission_{i}"].update(disabled=True)
            window[f"submit_answer_button_{i}"].update(disabled=True)
            window[f"show/hide_{i}"].update(text="Show Answer", disabled=True)
            window[f"question_percent_correct_{i}"].update(
                value=question_object["%_correct"] + "%", font=font
            )

            answers = re.findall("([^\/,()]+)", answer)
            if len(answers) > 1:
                correct = [
                    combined_correctness(submitted_answer, answer.strip(), True)
                    for answer in answers
                ]
            else:
                correct = [combined_correctness(submitted_answer, answer.strip())]

            if any(correct):
                right_answer = True
                window[f"answer_submission_{i}"].Widget.configure(readonlybackground="light green")
                specific_mini.data.score += 1
            else:
                right_answer = False
                window[f"answer_submission_{i}"].Widget.configure(readonlybackground="red")

            window[f"question_{i}"].set_focus()
            window[f"correct_override_{i}"].update(disabled=False)
            window["score"].update(value=specific_mini.data.score)

            # TODO Check back for this in the future
            # c = window["questions_column"].Widget
            # c.children["!canvas"].yview_moveto(
            #     (
            #         (c.children["!canvas"].yview()[-1] + c.children["!canvas"].yview()[0])
            #         * (
            #             list(
            #                 list(list(c.children.values())[0].children.values())[
            #                     0
            #                 ].children.values()
            #             )[int(i) - 1].winfo_height()
            #             / c.winfo_height()
            #         )
            #     )
            # )
            return window

        if "correct_override" in event:
            if right_answer:
                right_answer = False
                specific_mini.data.score -= 1
                window[f"answer_submission_{i}"].Widget.configure(readonlybackground="red")
            else:
                right_answer = True
                window[f"answer_submission_{i}"].Widget.configure(readonlybackground="light green")
                specific_mini.data.score += 1
            window["score"].update(value=specific_mini.data.score)

    return True


if __name__ == "__main__":
    window = minileague()
