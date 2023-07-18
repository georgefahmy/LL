import requests
from bs4 import BeautifulSoup as bs
import json
import base64
import sys
import os
from cryptography.fernet import Fernet
import PySimpleGUI as sg
from random import choice
import re
from pprint import pprint
import jellyfish
import datetime
from answer_correctness import combined_correctness

BASE_URL = "https://www.learnedleague.com"
WD = os.getcwd()


def encrypt_answer(answer):
    key = Fernet.generate_key()
    return (Fernet(key).encrypt(answer.encode()).decode(), key.decode())


def decrypt_answer(question):
    encrypted_answer = question.get("answer")
    key = question.get("key")

    if type(encrypted_answer) != bytes:
        encrypted_answer = encrypted_answer.encode()
    if type(key) != bytes:
        key = key.encode()
    return Fernet(key).decrypt(encrypted_answer).decode()


def get_full_list_of_onedays():
    if os.path.isfile("resources/oneday_data.json"):
        with open("resources/oneday_data.json", "r") as fp:
            data = json.load(fp)
    else:
        data = {}
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
    with open("resources/oneday_data.json", "w") as fp:
        json.dump(data, fp, sort_keys=True, indent=4)
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
    else:
        question_metrics = [0] * len(questions)

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
    oneday_data = {}
    for j, question in enumerate(questions):
        encrypted_answer, key = encrypt_answer(answers[j])
        oneday_data[j + 1] = {
            "_question": question,
            "answer": encrypted_answer,
            "key": key,
            "percent": question_metrics[j],
            "question_num": str(j + 1),
        }
    oneday["data"] = oneday_data
    return oneday


list_of_onedays = get_full_list_of_onedays()  # one time use? store this data in a json file?
font = "Arial", 16
layout = [
    [
        sg.Frame(
            "OneDay Selection",
            size=(325, 110),
            layout=[
                [
                    sg.Text("Search:", font=font),
                    sg.Input("", key="oneday_search", font=font, size=(14, 1), expand_x=True),
                    sg.Button("Search", font=font, key="oneday_filter_search"),
                ],
                [
                    sg.Text("Load OneDay:", font=font),
                    sg.Text("", expand_x=True),
                    sg.Combo(
                        values=search_onedays(list_of_onedays),
                        key="oneday_selection",
                        font=font,
                        enable_events=True,
                    ),
                ],
                [
                    sg.Button("Show Description", key="show_hide_blurb"), sg.Text(expand_x=True),sg.Button("Random", key="random_oneday")
                ],
            ],
        ),
        sg.Frame(
            "OneDay Info",
            size=(325, 110),
            layout=[
                [sg.Text("", key="oneday_title", font=font)],
                [
                    sg.Text("Difficulty: ", font=font),
                    sg.Text("", key="difficulty", font=font, expand_x=True),
                    sg.Text("Date:", font=font),
                    sg.Text("", font=font, key="oneday_date"),
                ],
                [
                    sg.Text("Overall Correct Answers: ", font=font),
                    sg.Text("", key="percent_correct", font=font),
                ],
            ],
        ),
        sg.Frame(
            "Question Metrics",
            size=(325, 110),
            layout=[
                [sg.Text("Current Score:", font=font), sg.Text("", key="score",font=font)],
                [
                    sg.Text("% Correct:", font=font, tooltip="Submit answer to see this stat"),
                    sg.Text("Submit answer to see", key="question_percent_correct",font=("Arial_italic",10)),
                ]
            ]
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
        sg.Frame(
            "Question",
            size=(300, 300),
            expand_x=True,
            layout=[
                [
                    sg.Multiline(
                        key="question",
                        font=("Arial", 24),
                        disabled=True,
                        no_scrollbar=True,
                        expand_x=True,
                        expand_y=True,
                        # enable_events=True,
                        # right_click_menu=["&Right", ["!Lookup Selection"]], # Future expansion for looking up selections
                    )
                ],
                [
                    sg.Frame(
                        "Answer",
                        expand_x=True,
                        layout=[
                            [sg.Text(key="answer", font=("Arial", 16), size=(10, 1), expand_x=True)]
                        ],
                    )
                ],
                [
                    sg.Checkbox(
                        "Money Question",
                        key="money_check",
                        font=font,
                        tooltip="Select to mark this as a money question\n% of people who got the question wrong = # of points (plus 15)",
                    ),
                    sg.Button(
                        "Show Answer",
                        key="show/hide",
                        size=(12, 1),
                        font=("Arial", 12),
                        tooltip="Reveal the Answer - (s)",
                    ),
                    sg.Text("", expand_x=True),
                    sg.Combo(
                        values=[],
                        default_value="1",
                        key="dropdown",
                        size=(3, 1),
                        font=("Arial", 16),
                        readonly=True,
                        enable_events=True,
                    ),
                    sg.Button(
                        "Next", key="next", disabled=True, disabled_button_color=("black", "gray")
                    ),
                    sg.Button(
                        "Previous",
                        key="previous",
                        disabled=True,
                        disabled_button_color=("black", "gray"),
                    ),
                ],
            ],
        )
    ],
    [
        sg.Frame(
            "Submission",
            expand_x=True,
            layout=[
                [
                    sg.Text("Answer: ", font=("Arial", 16)),
                    sg.Input("", key="answer_submission", font=("Arial", 16), expand_x=True),
                    sg.Button("Submit Answer", key="submit_answer_button", disabled_button_color=("black", "gray")),
                ],
            ]
        )
    ],
]
icon_file = WD + "/resources/ll_app_logo.png"
sg.set_options(icon=base64.b64encode(open(str(icon_file), "rb").read()))
window = sg.Window("OneDay Trivia", layout=layout, finalize=True)
window.bind("<s>", "show_key")
window.bind("<n>", "next_key")
window.bind("<p>", "previous_key")
# window["question"].bind("<ButtonPress-2>", "press")
# window["question"].bind("<ButtonPress-1>", "click_here")
window["answer_submission"].bind("<Return>", "answer_sub_enter_button")

filtered_results = search_onedays(list_of_onedays)
oneday = get_oneday_data(get_specific_oneday(list_of_onedays, choice(filtered_results)))
while not oneday:
    oneday = get_oneday_data(get_specific_oneday(list_of_onedays, choice(filtered_results)))

data = oneday["data"]
i = 1
score = 0
question_object = data[i]
window["oneday_title"].update(value=oneday["title"])
window["difficulty"].update(value=oneday["difficulty_rating"])
window["percent_correct"].update(value=str(oneday["overall_average"]) + "%")
window["blurb_text"].update(value=oneday["blurb"])
window["oneday_date"].update(value=oneday["date"])
window["oneday_selection"].update(value=oneday["title"])
window["next"].update(disabled=False)
window["previous"].update(disabled=True)
window["question"].update(value=question_object["_question"])
window["answer"].update(value="*******")
window["dropdown"].update(value=1, values=[x for x in data.keys()])
window["score"].update(value = score)
submitted_answers = {}

while True:
    event, values = window.read()

    if event in (None, "Quit", sg.WIN_CLOSED):
        window.close()
        break

    # if event:
    #     print(event, values)

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
        i = 1
        score = 0
        question_object = data[i]
        window["oneday_title"].update(value=oneday["title"])
        window["difficulty"].update(value=oneday["difficulty_rating"])
        window["percent_correct"].update(value=str(oneday["overall_average"]) + "%")
        window["blurb_text"].update(value=oneday["blurb"])
        window["oneday_date"].update(value=oneday["date"])
        window["oneday_selection"].update(value=oneday["title"])
        window["next"].update(disabled=False)
        window["previous"].update(disabled=True)
        window["question"].update(value=question_object["_question"])
        window["answer"].update(value="*******")
        window["dropdown"].update(value=1, values=[x for x in data.keys()])
        window["score"].update(value = score)
        submitted_answers = {}

    if event == "oneday_filter_search":
        filtered_results = search_onedays(list_of_onedays, search_word=values["oneday_search"])
        window["oneday_selection"].update(values=filtered_results)
        window["oneday_search"].update(value="")

    if event == "oneday_selection":
        oneday = get_oneday_data(get_specific_oneday(list_of_onedays, values["oneday_selection"]))
        data = oneday["data"]
        i = 1
        score = 0
        question_object = data[i]
        window["oneday_title"].update(value=oneday["title"])
        window["difficulty"].update(value=oneday["difficulty_rating"])
        window["percent_correct"].update(value=str(oneday["overall_average"]) + "%")
        window["blurb_text"].update(value=oneday["blurb"])
        window["question"].update(value=question_object["_question"])
        window["answer"].update(value="*******")
        window["dropdown"].update(value=1, values=[x for x in data.keys()])
        window["next"].update(disabled=False)
        window["previous"].update(disabled=True)
        window["score"].update(value = score)
        window["question_percent_correct"].update(value="")
        submitted_answers = {}

    if event in ("show/hide", "show_key"):
        if window.find_element_with_focus().Key in ("oneday_search", "answer_submission"):
            continue

        answer = decrypt_answer(question_object)

        if not values["answer_submission"]:
            confirm, _ = sg.Window(
                'Confirm',
                element_justification="c",
                layout=[
                    [
                        sg.T('You have not submitted an answer.', font=("Arial", 14))
                    ],
                    [
                        sg.T('Do you want to continue? (and forfeit your guess)', font=("Arial", 14))
                    ],
                    [
                        sg.Yes(s=12),
                        sg.No(s=12),
                    ]
                ],
                disable_close=False
            ).read(close=True)

        if confirm == "Yes":
            window["answer_submission"].update(disabled=True)
            window["submit_answer_button"].update(disabled=True)
        else:
            continue

        if window["show/hide"].get_text() == "Show Answer":
            try:
                window["show/hide"].update(text="Hide Answer")

                window["answer"].update(value=answer, font=("Arial", 16))
            except:
                continue

        elif window["show/hide"].get_text() == "Hide Answer":
            window["show/hide"].update(text="Show Answer")
            try:
                if answer:
                    window["answer"].update(value="*******")
                else:
                    window["answer"].update(value="")
            except:
                continue

    if event in ["next", "previous", "dropdown", "next_key", "previous_key"]:
        if window.find_element_with_focus().Key in ("oneday_search", "answer_submission"):
            continue

        if event in ("next", "next_key"):
            if event == "next_key" and i == len(data.keys()):
                continue
            i += 1

        elif event in ("previous", "previous_key"):
            if event == "previous_key" and i == 1:
                continue
            i -= 1

        elif event == "dropdown":
            i = values["dropdown"]

        question_object = data[i]
        answer = question_object.get("answer")

        window["question"].update(value=question_object["_question"])
        window["answer"].update(value="*******")
        window["dropdown"].update(value=i)
        window["show/hide"].update(text="Show Answer")
        window["answer_submission"].update(value="")
        window["money_check"].update(disabled=False, value=False)
        window["question_percent_correct"].update(value="Submit answer to see", font=("Arial", 10))
        window["answer_submission"].update(disabled=False)
        window["submit_answer_button"].update(disabled=False)

        if submitted_answers.get(str(i)):
            window["answer"].update(value=submitted_answers.get(str(i)).get("correct_answer"))
            window["answer_submission"].update(disabled=True)
            window["submit_answer_button"].update(disabled=True)
            window["money_check"].update(value=submitted_answers.get(str(i)).get("money_question"))
            window["question_percent_correct"].update(value=question_object["percent"], font=font)
            window["show/hide"].update(text="Hide Answer")

        if not question_object:
            if event in ("next", "next_key"):
                i -= 1
            elif event in ("previous", "previous_key"):
                i += 1
            elif event == "dropdown":
                i = values["dropdown"]
            continue

        if i == len(data.keys()):
            window["next"].update(disabled=True)
        else:
            window["next"].update(disabled=False)
        if i == 1:
            window["previous"].update(disabled=True)
        else:
            window["previous"].update(disabled=False)

    if event == "submit_answer_button":
        submitted_answer = values["answer_submission"].lower()
        answer = decrypt_answer(question_object)
        window["answer"].update(value=answer, font=("Arial", 16))
        window["show/hide"].update(text="Hide Answer")
        window["question_percent_correct"].update(value=question_object["percent"], font=font)

        answers = re.findall("([^\/,()]+)", answer)
        if len(answers) > 1:
            correct = [combined_correctness(submitted_answer, answer) for answer in answers]
        else:
            correct = [combined_correctness(submitted_answer, answer)]

        if any(correct):
            score+=15

        if values["money_check"]:
            wrong_percent = 100 - question_object["percent"]
            score += wrong_percent

        window["money_check"].update(disabled=True, value=False)
        window["score"].update(value = score)
        window["submit_answer_button"].update(disabled=True)
        submitted_answers[question_object["question_num"]] = {
            "correct_answer": answer,
            "submitted_answer": submitted_answer,
            "money_question": values["money_check"],
            "correct": any(correct)
        }
        pprint(submitted_answers)
