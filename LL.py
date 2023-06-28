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
        BASE_URL + link["href"]
        for link in bs(requests.get(url).content, "html.parser", parse_only=ss("a"))
        if str(link.decode_contents()).isnumeric()
        and int(str(link.decode_contents())) < max_threshold
        and int(str(link.decode_contents())) > min_threshold
    ]
    question_dict = {}

    for i, question in enumerate(results):
        soup = bs(requests.get(question).content, "html.parser")
        question_text = soup.find_all("div", {"class": "indivqQuestion"})[0].text.strip()
        answer_text = soup.find_all("div", {"id": "xyz"})[0].span.text.strip()
        question_dict[i+1] = {"_question": question_text, "answer": encode(answer_text)}

    return question_dict

layout = [
    [
        sg.Frame("Input",
            layout=[
                [
                    sg.Text("Season: ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Input(default_text="97", key="season", font=("Arial", 16), size=(3, 1), justification="right")
                ],
                [
                    sg.Text("Min % Correct: ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Input(default_text="0", key="min_%", font=("Arial", 16), size=(3, 1), justification="right")
                ],
                [
                    sg.Text("Max % Correct: ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Input(default_text="100", key="max_%", font=("Arial", 16), size=(3, 1), justification="right")
                ],
                [
                    sg.Text(expand_x=True),
                    sg.Button("Retrieve Questions", key="retrieve"),
                    sg.Cancel()
                ]
            ]
        ),
        sg.Frame("Information",
            vertical_alignment="top",
            visible=False,
            key="info_box",
            layout=[
                [
                    sg.Text("Season: ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Text("",key="season_title", font=("Arial", 16))
                ],
                [
                    sg.Text("Number of Questions: ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Text("",key="num_questions", font=("Arial", 16))
                ],
            ]
        ),
    ],
    [
        sg.Frame("Questions",
            layout=[
                [
                    sg.Multiline(
                        key="question",
                        size=(50, 7),
                        font=("Arial", 16),
                        disabled=True,
                        no_scrollbar=True
                    )
                ],
                [
                    sg.Frame("Answer",
                        expand_x=True,
                        layout=[
                            [
                                sg.Text(key="answer", font=("Arial", 16), size=(10, 1), expand_x=True)
                            ]
                        ]
                    )
                ],
                [
                    sg.Button("Show", key="show/hide", size=(6,1), font=("Arial", 12)),
                    sg.Text("", expand_x=True),
                    sg.Combo(
                        values = [],
                        default_value="1",
                        key="dropdown",
                        size=(3,1),
                        font=("Arial", 16),
                        readonly=True,
                        enable_events=True
                    ),
                    sg.Button("Next", key="next"),
                    sg.Button("Previous", key="previous")
                ]
            ]
        )
    ]
]

window = sg.Window("LL",layout=layout, finalize=True, resizable=True, )
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
        if int(values["season"]) < 60:
            values["season"] = "60"
            window["season"].update(value="60")

        questions = get_questions(values["season"], values["min_%"], values["max_%"])

        if not questions:
            window["question"].update(value="No Questions Available")

        window["dropdown"].update(values = list(questions.keys()), value=1)
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
        window["answer"].update(value="******")
        window["show/hide"].update(text="Show")

    if event== "show/hide":
        if window["show/hide"].get_text() == "Show":
            try:
                window["show/hide"].update(text="Hide")
                window["answer"].update(value=decode(answer), font = ("Arial", 16))
            except:
                continue

        elif window["show/hide"].get_text() == "Hide":
            window["show/hide"].update(text="Show")
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
        window["show/hide"].update(text="Show")
        question_object = questions.get(i)
        if not question_object:
            i-=1
            continue
        question = question_object.get("_question")
        answer = question_object.get("answer")
        window["question"].update(value=question)

    if event=="next":
        i+=1
        window["answer"].update(value="******")
        window["show/hide"].update(text="Show")
        question_object = questions.get(i)
        if not question_object:
            i-=1
            continue
        question = question_object.get("_question")
        answer = question_object.get("answer")
        window["question"].update(value=question)
        window["dropdown"].update(value=i)

    if event == "previous":
        i-=1
        window["answer"].update(value="******")
        window["show/hide"].update(text="Show")
        question_object = questions.get(i)
        if not question_object:
            i+=1
            continue
        question = question_object.get("_question")
        answer = question_object.get("answer")
        window["question"].update(value=question)
        window["dropdown"].update(value=i)


# question_dict = get_questions(season_number, min_threshold, max_threshold)
