import requests
import re
import PySimpleGUI as sg

from bs4 import BeautifulSoup as bs, SoupStrainer as ss
from cryptography.fernet import Fernet
from pprint import pprint


BASE_URL = "https://www.learnedleague.com"

key = Fernet.generate_key()
fernet = Fernet(key)


def encode(answer):
    return fernet.encrypt(answer.encode())


def decode(coded_answer):
    return fernet.decrypt(coded_answer).decode()


def get_questions(season_number, min_threshold, max_threshold):
    url = BASE_URL + "/allrundles.php?" + season_number

    min_threshold = int(min_threshold)
    max_threshold = int(max_threshold)

    if max_threshold <= min_threshold:
        max_threshold = min_threshold + 5

    results = [
        link
        for link in bs(requests.get(url).content, "html.parser", parse_only=ss("a"))
        if str(link.decode_contents()).isnumeric()
        and int(str(link.decode_contents())) < max_threshold
        and int(str(link.decode_contents())) > min_threshold
    ]

    question_dict = {}

    for i, link in enumerate(results):
        url = BASE_URL + link["href"]
        soup = bs(requests.get(url).content, "html.parser")

        question_num = "Day " + str(url.split("&")[1]) + " Q" + str(url.split("&")[2])

        question_text = soup.find_all("div", {"class": "indivqQuestion"})[0].text.strip()
        answer_text = soup.find_all("div", {"id": "xyz"})[0].span.text.strip()

        question_dict[i + 1] = {
            "_question": question_text,
            "answer": encode(answer_text),
            "percent": str(link.decode_contents()) + "%",
            "question_num": question_num,
        }

    return question_dict


layout = [
    [
        sg.Frame(
            "Input",
            layout=[
                [
                    sg.Text("Season: ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Input(
                        default_text="97",
                        key="season",
                        font=("Arial", 16),
                        size=(3, 1),
                        justification="right",
                    ),
                ],
                [
                    sg.Text("Min % Correct: ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Input(
                        default_text="0",
                        key="min_%",
                        font=("Arial", 16),
                        size=(3, 1),
                        justification="right",
                    ),
                ],
                [
                    sg.Text("Max % Correct: ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Input(
                        default_text="100",
                        key="max_%",
                        font=("Arial", 16),
                        size=(3, 1),
                        justification="right",
                    ),
                ],
                [
                    sg.Text(expand_x=True),
                    sg.Button("Retrieve Questions", key="retrieve"),
                    sg.Cancel(),
                ],
            ],
        ),
        sg.Frame(
            "Information",
            vertical_alignment="top",
            visible=False,
            key="info_box",
            layout=[
                [
                    sg.Text("Season: ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Text("", key="season_title", font=("Arial", 16)),
                ],
                [
                    sg.Text("Total Number of Questions: ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Text("", key="num_questions", font=("Arial", 16)),
                ],
                [
                    sg.Text("Question: ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Text("", key="question_number", font=("Arial", 16)),
                ],
                [
                    sg.Text("Correct %: ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Text("", key="%_correct", font=("Arial", 16)),
                ],
            ],
        ),
    ],
    [
        sg.Frame(
            "Questions",
            expand_x=True,
            expand_y=True,
            layout=[
                [
                    sg.Multiline(
                        key="question",
                        size=(50, 7),
                        font=("Arial", 16),
                        disabled=True,
                        no_scrollbar=True,
                        expand_x=True,
                        expand_y=True,
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
                    sg.Button("Show Answer", key="show/hide", size=(12, 1), font=("Arial", 12)),
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
                    sg.Button("Next", key="next", disabled=True, disabled_button_color=("black","gray")),
                    sg.Button("Previous", key="previous", disabled=True, disabled_button_color=("black","gray")),
                ],
            ],
        )
    ],
]

window = sg.Window(
    "LearnedLeague",
    layout=layout,
    finalize=True,
    resizable=True,
)
i = 1
while True:
    event, values = window.read()

    if event in (None, "Quit", sg.WIN_CLOSED):
        window.close()
        break

    if event == "cancel":
        window["question"].update(value="")
        window["answer"].update(value="")
        i = 1

    if event == "retrieve":
        if int(values["min_%"]) > int(values["max_%"]):
            values["max_%"] = str(int(values["min_%"]) + 5)
            window["max_%"].update(value=values["max_%"])

        if int(values["season"]) < 60:
            values["season"] = "60"
            window["season"].update(value="60")

        questions = get_questions(values["season"], values["min_%"], values["max_%"])

        if not questions:
            window["question"].update(value="No Questions Available")

        window["dropdown"].update(values=list(questions.keys()), value=1)
        i = 1
        question_object = questions.get(i)
        if not question_object:
            continue
        question = question_object.get("_question")
        answer = question_object.get("answer")
        window["question"].update(value=question)
        window["info_box"].update(visible=True)
        window["season_title"].update(value=values["season"])
        window["num_questions"].update(value=len(list(questions.keys())))
        window["%_correct"].update(value=question_object["percent"])
        window["question_number"].update(value=question_object["question_num"])
        window["answer"].update(value="******")
        window["show/hide"].update(text="Show Answer")
        window["next"].update(disabled=False)

    if event == "show/hide":
        if window["show/hide"].get_text() == "Show Answer":
            try:
                window["show/hide"].update(text="Hide Answer")
                window["answer"].update(value=decode(answer), font=("Arial", 16))
            except:
                continue

        elif window["show/hide"].get_text() == "Hide Answer":
            window["show/hide"].update(text="Show Answer")
            try:
                if answer:
                    window["answer"].update(value="******")
                else:
                    window["answer"].update(value="")
            except:
                continue

    if event == "dropdown":
        i = values["dropdown"]
        window["answer"].update(value="******")
        window["show/hide"].update(text="Show Answer")
        question_object = questions.get(i)
        if not question_object:
            i -= 1
            continue
        question = question_object.get("_question")
        answer = question_object.get("answer")
        window["question"].update(value=question)
        window["%_correct"].update(value=question_object["percent"])
        window["question_number"].update(value=question_object["question_num"])
        if i == len(questions.keys()):
            window["next"].update(disabled=True)
        else:
            window["next"].update(disabled=False)
        if i == 1:
            window["previous"].update(disabled=True)
        else:
            window["previous"].update(disabled=False)

    if event == "next":
        i += 1
        window["answer"].update(value="******")
        window["show/hide"].update(text="Show Answer")
        question_object = questions.get(i)
        if not question_object:
            i -= 1
            continue
        question = question_object.get("_question")
        answer = question_object.get("answer")
        window["question"].update(value=question)
        window["dropdown"].update(value=i)
        window["%_correct"].update(value=question_object["percent"])
        window["question_number"].update(value=question_object["question_num"])
        if i == len(questions.keys()):
            window["next"].update(disabled=True)
        else:
            window["next"].update(disabled=False)
        if i == 1:
            window["previous"].update(disabled=True)
        else:
            window["previous"].update(disabled=False)

    if event == "previous":
        i -= 1
        window["answer"].update(value="******")
        window["show/hide"].update(text="Show Answer")
        question_object = questions.get(i)
        if not question_object:
            i += 1
            continue
        question = question_object.get("_question")
        answer = question_object.get("answer")
        window["question"].update(value=question)
        window["dropdown"].update(value=i)
        window["%_correct"].update(value=question_object["percent"])
        window["question_number"].update(value=question_object["question_num"])

        if i == len(questions.keys()):
            window["next"].update(disabled=True)
        else:
            window["next"].update(disabled=False)
        if i == 1:
            window["previous"].update(disabled=True)
        else:
            window["previous"].update(disabled=False)


# question_dict = get_questions(season_number, min_threshold, max_threshold)
