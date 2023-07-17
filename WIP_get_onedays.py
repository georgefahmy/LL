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
        ][0]
        modkos_rating = blurb.split()[ind].replace(".", "").strip()
    else:
        modkos_rating = "None"

    oneday["blurb"] = blurb
    oneday["difficulty_rating"] = modkos_rating.replace(",", "")
    oneday["overall_average"] = round(sum(question_metrics) / len(question_metrics), 2)
    oneday_data = {}
    for j, question in enumerate(questions):
        encrypted_answer, key = encrypt_answer(answers[j])
        oneday_data[str(j + 1)] = {
            "_question": question,
            "answer": encrypted_answer,
            "key": key,
            "percent": question_metrics[j],
            "question_num": str(j + 1),
        }
    oneday["data"] = oneday_data
    return oneday


data = get_full_list_of_onedays()  # one time use? store this data in a json file?
font = "Arial", 16
layout = [
    [
        sg.Frame(
            "OneDay Selection",
            size=(300, 100),
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
                        values=search_onedays(data),
                        key="oneday_selection",
                        font=font,
                        enable_events=True,
                    ),
                ],
            ],
        ),
        sg.Frame(
            "OneDay Info",
            size=(300, 100),
            layout=[
                [sg.Text("", key="oneday_title", font=font)],
                [sg.Text("Difficulty: ", font=font), sg.Text("", key="difficulty", font=font)],
                [
                    sg.Text("Overall Correct Answers: ", font=font),
                    sg.Text("", key="percent_correct", font=font),
                ],
            ],
        ),
        sg.Frame("Question Metrics", size=(300, 100), layout=[[]]),
    ],
    [
        sg.Frame(
            "Blurb",
            expand_x=True,
            size=(300, 150),
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
                        enable_events=True,
                        right_click_menu=["&Right", ["!Lookup Selection"]],
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
    [sg.Frame("Answer", layout=[[]])],
    [sg.Frame("Submission", layout=[[]])],
]
icon_file = WD + "/resources/ll_app_logo.png"
sg.set_options(icon=base64.b64encode(open(str(icon_file), "rb").read()))
window = sg.Window("OneDay Trivia", layout=layout, finalize=True)
filtered_results = search_onedays(data)
oneday = get_oneday_data(get_specific_oneday(data, choice(filtered_results)))
while not oneday:
    oneday = get_oneday_data(get_specific_oneday(data, choice(filtered_results)))

window["oneday_title"].update(value=oneday["title"])
window["difficulty"].update(value=oneday["difficulty_rating"])
window["percent_correct"].update(value=str(oneday["overall_average"]) + "%")
window["blurb_text"].update(value=oneday["blurb"])
window["oneday_selection"].update(value=oneday["title"])
window["question"].update(value=oneday["data"]["1"]["_question"])
window["answer"].update(value="*******")
window["dropdown"].update(value=1, values=[x for x in oneday["data"].keys()])

while True:
    event, values = window.read()

    if event in (None, "Quit", sg.WIN_CLOSED):
        window.close()
        break

    if event:
        print(event, values)

    if event == "oneday_filter_search":
        filtered_results = search_onedays(data, search_word=values["oneday_search"])
        window["oneday_selection"].update(values=filtered_results)
        window["oneday_search"].update(value="")

    if event == "oneday_selection":
        oneday = get_oneday_data(get_specific_oneday(data, values["oneday_selection"]))
        window["oneday_title"].update(value=oneday["title"])
        window["difficulty"].update(value=oneday["difficulty_rating"])
        window["percent_correct"].update(value=str(oneday["overall_average"]) + "%")
        window["blurb_text"].update(value=oneday["blurb"])
        window["question"].update(value=oneday["data"]["1"]["_question"])
        window["answer"].update(value="*******")
        window["dropdown"].update(value=1, values=[x for x in oneday["data"].keys()])
