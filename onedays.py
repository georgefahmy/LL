import requests
import datetime
import webbrowser
import wikipedia
import unicodedata
import base64
import os
import PySimpleGUI as sg
import re

from bs4 import BeautifulSoup as bs
from random import choice
from pprint import pprint
from answer_correctness import combined_correctness
from PyDictionary import PyDictionary

BASE_URL = "https://www.learnedleague.com"
WD = os.getcwd()


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
        if datetime.datetime.strptime(data[key]["date"], "%b %d, %Y") >= datetime.datetime.now():
            del data[key]

    for key in list(data.keys()):
        if any([val in key for val in ["Just Audio", "Just Images", "Just Memes", "Just GIFs", "Just Fuzzy Images"]]):
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
    page = bs(requests.get(oneday["url"]).content, "lxml")
    try:
        metrics_page = bs(
            requests.get(BASE_URL + page.find("ul", {"id": "profilestabs"}).a.get("href")).content,
            "lxml",
        )
    except:
        metrics_page = None
    try:
        questions = [
            ". ".join(q.text.split(".")[1:]).strip()
            for q in page.find("div", {"id": "qs_close", "class": "qdivshow_wide"}).find_all("p")
        ]
    except:
        return None
    answers = [
        a.text.strip().split("\n")[-1]
        for a in page.find("div", {"id": "qs_close", "class": "qdivshow_wide"}).find_all(
            "div", {"class": "answer3"}
        )
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
    check_blurb = page.find("div", {"id": "blurb_close"})
    if check_blurb:
        blurb = re.sub("[\r\n]+", "\n", "".join(check_blurb.text.split("blurb")[1:]).strip())
    else:
        blurb = ""
    if "ModKos" in blurb.split():
        ratings = set(["G", "PG", "PG-13", "R", "X"])
        ind = [
            i
            for i, e in enumerate([val.replace(".", "").strip() for val in blurb.split()])
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
    oneday_data = {}
    for j, question in enumerate(questions):
        oneday_data[j + 1] = {
            "_question": question,
            "answer": answers[j],
            "percent": question_metrics[j],
            "question_num": str(j + 1),
        }
    oneday["data"] = oneday_data
    return oneday


def oneday_main():
    font = "Arial", 16
    layout = [
        [
            sg.Frame(
                "OneDay Selection",
                size=(325, 105),
                layout=[
                    [
                        sg.Text("Search:", font=font),
                        sg.Input("", key="oneday_search", font=font, size=(14, 1), expand_x=True),
                        sg.Button("Search", key="oneday_filter_search"),
                    ],
                    [
                        sg.Text("OneDay:", font=font, tooltip="Choose a OneDay to load"),
                        sg.Combo(
                            values=[],
                            key="oneday_selection",
                            font=font,
                            size=(40, 1),
                            expand_x=True,
                            readonly=True,
                            enable_events=True,
                            tooltip="Choose a OneDay to load",
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
                            font=font,
                            enable_events=True,
                            key="difficulty_tooltip",
                            tooltip="https://www.learnedleague.com/images/misc/ModKos.png?t=1649",
                            metadata="https://www.learnedleague.com/images/misc/ModKos.png?t=1649",
                        ),
                        sg.Text("", key="difficulty", font=font, expand_x=True),
                        sg.Text("Date:", font=font),
                        sg.Text("", font=font, key="oneday_date"),
                    ],
                    [
                        sg.Text("Overall Correct Rate: ", font=font),
                        sg.Text("", key="percent_correct", font=font),
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
                        sg.Text(f"({5})", font=font, key="num_of_money_questions_left")
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
                scrollable = True,
                size=(975,600),
                vertical_scroll_only = True,
                layout=[
                    [
                        sg.Frame(
                            f"Question {i}",
                            size=(970,300),
                            expand_x=True,
                            expand_y=True,
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
                                        auto_size_text=True,
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
                                    )
                                ],
                                [
                                    sg.Checkbox(
                                        "Money Question",
                                        key=f"money_check_{i}",
                                        font=font,
                                        tooltip="If correct - get points equal to % of people who got the question wrong",
                                    ),
                                ],
                                [
                                    sg.Text("Answer: ", font=("Arial", 16)),
                                    sg.Input(
                                        "",
                                        key=f"answer_submission_{i}",
                                        font=("Arial", 16),
                                        expand_x=True,
                                        disabled_readonly_background_color="light gray",
                                        disabled_readonly_text_color="black"
                                    ),
                                    sg.Button(
                                        "Submit Answer",
                                        key=f"submit_answer_button_{i}",
                                        disabled_button_color=("black", "gray"),
                                        bind_return_key=True,
                                    ),
                                    sg.Text(expand_x=True),
                                    sg.Text(
                                        "CA%:",
                                        font=font,
                                        tooltip="Correct Answer Percentage (all players)",
                                    ),
                                    sg.Text(
                                        "Submit answer to see",
                                        key=f"question_percent_correct_{i}",
                                        font=("Arial Italic", 10),
                                        tooltip="Correct Answer Percentage (all players)",
                                    ),
                                ],
                            ],
                        )
                    ]
                    for i in range(1,13)
                ]
            )
        ],
    ]

    list_of_onedays = get_full_list_of_onedays()  # one time use? store this data in a json file?
    font = "Arial", 16
    close_popup = False

    icon_file = WD + "/resources/ll_app_logo.png"
    sg.set_options(icon=base64.b64encode(open(str(icon_file), "rb").read()))
    window = sg.Window("OneDay Trivia", layout=layout, finalize=True, return_keyboard_events=True)

    window["oneday_selection"].update(values=search_onedays(list_of_onedays))

    [window[f"question_{i}"].bind("<ButtonPress-2>", "press") for i in range(1, 13)]
    [window[f"question_{i}"].bind("<ButtonPress-1>", "click_here") for i in range(1, 13)]
    [window[f"answer_submission_{i}"].bind("<Return>", f"_submit_answer_button_{i}") for i in range(1,13)]

    filtered_results = search_onedays(list_of_onedays)
    oneday = get_oneday_data(get_specific_oneday(list_of_onedays, choice(filtered_results)))
    while not oneday:
        oneday = get_oneday_data(get_specific_oneday(list_of_onedays, choice(filtered_results)))

    data = oneday["data"]
    i = 1
    score = 0
    num_of_money_questions_left = 5
    submitted_answers = {}
    for i in data.keys():
        question_object = data[i]
        window["oneday_title"].update(value=oneday["title"])
        window["difficulty"].update(value=oneday["difficulty_rating"])
        window["percent_correct"].update(value=str(oneday["overall_average"]) + "%")
        window["blurb_text"].update(value=oneday["blurb"])
        window["oneday_date"].update(value=oneday["date"])
        window["oneday_selection"].update(value=oneday["title"])
        window["90th_percent"].update(value=oneday["90th_percentile"])
        window["50th_percent"].update(value=oneday["50th_percentile"])
        window["10th_percent"].update(value=oneday["10th_percentile"])
        window["score"].update(value=score)
        window["num_of_money_questions_left"].update(value=num_of_money_questions_left)

        window[f"question_{i}"].update(value=question_object["_question"])
        window[f"answer_{i}"].update(value="*******")
        window[f"money_check_{i}"].update(disabled=False, value=False)
        window[f"show/hide_{i}"].update(text="Show Answer", disabled=False)
        window[f"answer_submission_{i}"].update(value="", disabled=False)
        window[f"submit_answer_button_{i}"].update(disabled=False)
        window[f"question_percent_correct_{i}"].update(
            value="Submit answer to see", font=("Arial Italic", 10)
        )

    while True:
        event, values = window.read()

        if event in (None, "Quit", sg.WIN_CLOSED):
            window.close()
            break

        # if event:
        #     print(event, values)

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
            if len(selected_text.split()):
                # selected text is a single word, so just do a lookup
                try:
                    definition = PyDictionary().meaning(selected_text)

                    result = "\n".join([key + ": " + ", ".join(value) for key, value in definition.items()])
                    print(result)
                    sg.popup_ok(result, title="Dictionary Result", font=("Arial", 16))
                    continue
                except:
                    result = "No results available - Try another search."
            try:
                result = wikipedia.summary(
                    selected_text, sentences=2, auto_suggest=True, redirect=True
                )
            except:
                result = "No results available - Try another search."

            sg.popup_ok(result, title="Wiki Summary", font=("Arial", 16))

        if event == "show_hide_blurb":
            size = window["blurb_frame"].get_size()
            if size[1] == 150:
                window["blurb_frame"].set_size((300, 1))
                window["show_hide_blurb"].update(text="Show Description")
            else:
                window["blurb_frame"].set_size((size[0], 150))
                window["show_hide_blurb"].update(text="Hide Description")

        if event == "random_oneday":
            oneday = get_oneday_data(get_specific_oneday(list_of_onedays, choice(filtered_results)))
            data = oneday["data"]
            score = 0
            submitted_answers = {}
            for i in data.keys():
                question_object = data[i]
                window["oneday_title"].update(value=oneday["title"])
                window["difficulty"].update(value=oneday["difficulty_rating"])
                window["percent_correct"].update(value=str(oneday["overall_average"]) + "%")
                window["blurb_text"].update(value=oneday["blurb"])
                window["oneday_date"].update(value=oneday["date"])
                window["oneday_selection"].update(value=oneday["title"])
                window["90th_percent"].update(value=oneday["90th_percentile"])
                window["50th_percent"].update(value=oneday["50th_percentile"])
                window["10th_percent"].update(value=oneday["10th_percentile"])
                window["score"].update(value=score)
                window["num_of_money_questions_left"].update(value=num_of_money_questions_left)

                window[f"question_{i}"].update(value=question_object["_question"])
                window[f"answer_{i}"].update(value="*******")
                window[f"money_check_{i}"].update(disabled=False, value=False)
                window[f"show/hide_{i}"].update(text="Show Answer", disabled=False)
                window[f"answer_submission_{i}"].update(value="", disabled=False)
                window[f"submit_answer_button_{i}"].update(disabled=False)
                window[f"question_percent_correct_{i}"].update(
                    value="Submit answer to see", font=("Arial Italic", 10)
                )


        if event == "oneday_filter_search":
            filtered_results = search_onedays(list_of_onedays, search_word=values["oneday_search"])
            window["oneday_selection"].update(value=filtered_results[0], values=filtered_results)
            window["oneday_search"].update(value="")
            oneday = get_oneday_data(get_specific_oneday(list_of_onedays, filtered_results[0]))
            data = oneday["data"]
            i = 1
            score = 0
            submitted_answers = {}
            for i in data.keys():
                question_object = data[i]
                window["oneday_title"].update(value=oneday["title"])
                window["difficulty"].update(value=oneday["difficulty_rating"])
                window["percent_correct"].update(value=str(oneday["overall_average"]) + "%")
                window["blurb_text"].update(value=oneday["blurb"])
                window["oneday_date"].update(value=oneday["date"])
                window["oneday_selection"].update(value=oneday["title"])
                window["90th_percent"].update(value=oneday["90th_percentile"])
                window["50th_percent"].update(value=oneday["50th_percentile"])
                window["10th_percent"].update(value=oneday["10th_percentile"])
                window["score"].update(value=score)
                window["num_of_money_questions_left"].update(value=num_of_money_questions_left)

                window[f"question_{i}"].update(value=question_object["_question"])
                window[f"answer_{i}"].update(value="*******")
                window[f"money_check_{i}"].update(disabled=False, value=False)
                window[f"show/hide_{i}"].update(text="Show Answer", disabled=False)
                window[f"answer_submission_{i}"].update(value="", disabled=False)
                window[f"submit_answer_button_{i}"].update(disabled=False)
                window[f"question_percent_correct_{i}"].update(
                    value="Submit answer to see", font=("Arial Italic", 10)
                )

        if event == "oneday_selection":
            oneday = get_oneday_data(
                get_specific_oneday(list_of_onedays, values["oneday_selection"])
            )
            data = oneday["data"]
            i = 1
            score = 0
            submitted_answers = {}
            for i in data.keys():
                question_object = data[i]
                window["oneday_title"].update(value=oneday["title"])
                window["difficulty"].update(value=oneday["difficulty_rating"])
                window["percent_correct"].update(value=str(oneday["overall_average"]) + "%")
                window["blurb_text"].update(value=oneday["blurb"])
                window["oneday_date"].update(value=oneday["date"])
                window["oneday_selection"].update(value=oneday["title"])
                window["90th_percent"].update(value=oneday["90th_percentile"])
                window["50th_percent"].update(value=oneday["50th_percentile"])
                window["10th_percent"].update(value=oneday["10th_percentile"])
                window["score"].update(value=score)
                window["num_of_money_questions_left"].update(value=num_of_money_questions_left)

                window[f"question_{i}"].update(value=question_object["_question"])
                window[f"answer_{i}"].update(value="*******")
                window[f"money_check_{i}"].update(disabled=False, value=False)
                window[f"show/hide_{i}"].update(text="Show Answer", disabled=False)
                window[f"answer_submission_{i}"].update(value="", disabled=False)
                window[f"submit_answer_button_{i}"].update(disabled=False)
                window[f"question_percent_correct_{i}"].update(
                    value="Submit answer to see", font=("Arial Italic", 10)
                )


        if "show/hide" in event:
            if window.find_element_with_focus().Key in ("oneday_search", "answer_submission"):
                continue

            i = int(event.split("_")[-1])
            question_object = data[i]
            answer = question_object["answer"]

            if not values[f"answer_submission_{i}"]:
                confirm, _ = sg.Window(
                    "Confirm",
                    element_justification="c",
                    layout=[
                        [sg.Text("You have not submitted an answer.", font=("Arial", 14))],
                        [
                            sg.Text(
                                "Do you want to continue? (and forfeit your guess)",
                                font=("Arial", 14),
                            )
                        ],
                        [
                            sg.Yes(s=12),
                            sg.No(s=12),
                        ],
                    ],
                    disable_close=False,
                ).read(close=True)

            if confirm == "Yes":
                window[f"answer_submission_{i}"].update(disabled=True)
                window[f"submit_answer_button_{i}"].update(disabled=True)
                window[f"money_check_{i}"].update(disabled=True)
                window[f"show/hide_{i}"].update(visible=False)
                window[f"question_percent_correct_{i}"].update(
                    value=question_object["percent"], font=font
                )
            else:
                continue

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
                        window[f"answer_{i}"].update(value="*******")
                    else:
                        window[f"answer_{i}"].update(value="")
                except:
                    continue

        if "submit_answer_button" in event:

            i = int(event.split("_")[-1])
            question_object = data[i]

            if not values[f"answer_submission_{i}"]:
                continue
            submitted_answer = values[f"answer_submission_{i}"].lower()
            answer = question_object["answer"]
            window[f"answer_{i}"].update(value=answer, font=("Arial", 16))
            window[f"show/hide_{i}"].update(visible=False)
            window[f"question_percent_correct_{i}"].update(value=question_object["percent"], font=font)

            answers = re.findall("([^\/,()]+)", answer)
            if len(answers) > 1:
                correct = [
                    combined_correctness(submitted_answer, answer.strip(), True)
                    for answer in answers
                ]
            else:
                correct = [combined_correctness(submitted_answer, answer.strip())]

            if all(correct):
                score += 15

                if values[f"money_check_{i}"]:
                    wrong_percent = 100 - question_object["percent"]
                    score += wrong_percent

            if values[f"money_check_{i}"]:
                num_of_money_questions_left -= 1
                window["num_of_money_questions_left"].update(value=num_of_money_questions_left)



            window[f"money_check_{i}"].update(disabled=True)
            window["score"].update(value=score)
            window[f"answer_submission_{i}"].update(disabled=True)
            window[f"submit_answer_button_{i}"].update(disabled=True)
            window[f"answer_submission_{i}"].unbind("<Return>")
            submitted_answers[question_object["question_num"]] = {
                "correct_answer": answer,
                "submitted_answer": submitted_answer,
                "money_question": values[f"money_check_{i}"],
                "correct": any(correct),
            }
            pprint(submitted_answers)
            window[f"question_{i}"].set_focus()

            if num_of_money_questions_left == 0:
                [window[f"money_check_{i}"].update(disabled=True) for i in range(1,13)]

        if len(submitted_answers) == 12:
            percentile_info = oneday["all_percentile"]
            final_percentile = list(percentile_info.keys())[
                list(percentile_info.values()).index(
                    min(list(percentile_info.values()), key=lambda x: abs(int(x) - score))
                )
            ]
            close_popup = True
            if not close_popup:
                close_popup = sg.popup_ok(
                    f"Final Score: {score} pts\nFinal percentile: {final_percentile}%",
                    title="Final Score",
                    font=font,
                )

        if event == "difficulty_tooltip":
            webbrowser.open(window["difficulty_tooltip"].metadata)
    return True


if __name__ == "__main__":
    oneday_main()
