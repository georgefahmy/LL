import requests
import re
import PySimpleGUI as sg

from bs4 import BeautifulSoup as bs, SoupStrainer as ss
from pprint import pprint
from time import sleep


BASE_URL = "https://www.learnedleague.com"


def get_all_questions(season_number):
    all_questions_dict = {}
    url = BASE_URL + "/match.php?" + str(season_number)
    for i in range(1,26):
        question_url = url + "&" + str(i)
        page = bs(requests.get(question_url).content, "html.parser")

        categories = [
            link.text.strip().split("-")[0].split(".")[-1].strip()
            for link in page.find_all("div", {"class": "ind-Q20 dont-break-out"})
        ]

        percentages = [
            cell.text for cell in page.find_all("tr")[-2].find_all("td",{"class":"ind-Q3"})
        ][2:-1]

        questions = [
            "-".join(link.text.strip().split("-")[1:]).strip()
            for link in page.find_all("div", {"class": "ind-Q20 dont-break-out"})
        ]
        answers = [
            link.text.strip()
            for link in page.find_all("div", {"class": "a-red"})
        ]

        for j, question in enumerate(questions):
            question_num_code = "D"+str(i)+"Q"+str(j+1)
            all_questions_dict[question_num_code] = {
                "_question": question,
                "answer": answers[j],
                "category": categories[j],
                "percent": percentages[j],
                "question_num":question_num_code
            }

    return all_questions_dict

def get_questions(all_questions_dict, min_threshold, max_threshold, category_filter):
    min_threshold = int(min_threshold)
    max_threshold = int(max_threshold)

    if max_threshold <= min_threshold:
        max_threshold = min_threshold + 5

    if category_filter == "ALL":
        filtered_question_ids = [
            question_ids
            for question_ids, question in all_questions_dict.items()
            if int(question["percent"]) >= min_threshold
            and int(question["percent"]) < max_threshold
        ]
    else:
        filtered_question_ids = [
            question_ids
            for question_ids, question in all_questions_dict.items()
            if int(question["percent"]) >= min_threshold
            and int(question["percent"]) < max_threshold
            and question["category"].upper() == category_filter.upper()
        ]

    filtered_questions_dict = {
        i+1: val
        for i, val in enumerate(
            [all_questions_dict[key] for key in filtered_question_ids]
        )
    }

    return filtered_questions_dict

latest_season = bs(requests.get("https://www.learnedleague.com/allrundles.php").content, "html.parser", parse_only=ss("h1")).text.split(":")[0].split("LL")[-1]

available_seasons = [str(season) for season in list(range(60, int(latest_season)+1, 1))]


layout = [
    [
        sg.Column(
        pad=(0,0),
        layout=[[sg.Frame(
            "Input",
            key="input_frame",
            vertical_alignment="top",
            element_justification="l",
            size=(275,155),
            layout=[
                [
                    sg.Text("Season (min 60): ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Combo(
                        available_seasons,
                        default_value="97",
                        key="season",
                        font=("Arial", 16),
                        readonly=True,
                        expand_x=True
                    ),
                ],
                [
                    sg.Text("Min % Correct: ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Input(
                        default_text="0",
                        key="min_%",
                        font=("Arial", 16),
                        size=(5, 1),
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
                        size=(5, 1),
                        justification="right",
                    ),
                ],
                [
                    sg.Text("Category: ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Combo(
                        [],
                        default_value="ALL",
                        key="category_selection",
                        font=("Arial", 16),
                        size=(15, 1),
                        readonly=True,
                        enable_events=True
                    ),
                ],
                [
                    sg.Button("Retrieve Season", key="retrieve"),
                    sg.Text(expand_x=True),
                    sg.Button("Filter", key="filter", bind_return_key=True),
                    sg.Cancel(),
                ],
            ],
        ),]]),
        sg.Column(layout=[[]],expand_x=True),
        sg.Column(
        pad=(0,0),
        vertical_alignment="top",
        layout =
        [[sg.Frame(
            "Information",
            vertical_alignment="top",
            size=(275,155),
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
                    sg.Text("Category: ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Text("", key="question_category", font=("Arial", 16)),
                ],
                [
                    sg.Text("Correct %: ", font=("Arial", 16)),
                    sg.Text(expand_x=True),
                    sg.Text("", key="%_correct", font=("Arial", 16)),
                ],
            ],
        )]])
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
                        size=(60, 7),
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
                            [
                                sg.Text(
                                    key="answer",
                                    font=("Arial", 16),
                                    size=(10, 1),
                                    expand_x=True
                                )
                            ]
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
                    sg.Button(
                        "Next",
                        key="next",
                        disabled=True,
                        disabled_button_color=("black","gray")
                    ),
                    sg.Button(
                        "Previous",
                        key="previous",
                        disabled=True,
                        disabled_button_color=("black","gray")
                    ),
                ],
            ],
        )
    ],
]

window = sg.Window(
    "LearnedLeague",
    layout=layout,
    finalize=True,
    resizable=False,
    element_justification="center",
)
i = 1
while True:
    event, values = window.read()

    if event in (None, "Quit", sg.WIN_CLOSED):
        window.close()
        break

    if event == "Cancel":
        print(window["input_frame"].get_size())
        window["question"].update(value="")
        window["answer"].update(value="")
        i = 1

    if event == "retrieve":
        if values["season"] == window["season_title"].get():
            continue
        window["season_title"].update(value="Loading...")
        window.refresh()

        all_questions_dict = get_all_questions(values["season"])
        categories = ["ALL"] + list(set([q["category"] for q in all_questions_dict.values()]))

        window["season_title"].update(value=values["season"])
        window["category_selection"].update(values=categories, value="ALL")
        window.write_event_value("filter", "")
        window.set_title("LearnedLeague " + values["season"])

    if event in ["filter", "category_selection"]:
        if int(values["min_%"]) > int(values["max_%"]):
            values["max_%"] = str(int(values["min_%"]) + 1)
            window["max_%"].update(value=values["max_%"])

        if int(values["min_%"]) < 0:
            values["min_%"] = str(0)
            window["min_%"].update(value=values["max_%"])

        if int(values["max_%"]) > 100 or int(values["min_%"]) > 100:
            values["min_%"] = str(100)
            values["max_%"] = str(100)
            window["min_%"].update(value=values["min_%"])
            window["max_%"].update(value=values["max_%"])


        questions = get_questions(all_questions_dict, values["min_%"], values["max_%"], values["category_selection"])

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
        window["%_correct"].update(value=str(question_object["percent"]) + "%")
        window["question_number"].update(value=question_object["question_num"])
        window["question_category"].update(value=question_object["category"])
        window["answer"].update(value="******")
        window["show/hide"].update(text="Show Answer")
        window["next"].update(disabled=False)

    if event == "show/hide":
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
        window["%_correct"].update(value=str(question_object["percent"]) + "%")
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
        window["%_correct"].update(value=str(question_object["percent"]) + "%")
        window["question_number"].update(value=question_object["question_num"])
        window["question_category"].update(value=question_object["category"])

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
        window["%_correct"].update(value=str(question_object["percent"]) + "%")
        window["question_number"].update(value=question_object["question_num"])
        window["question_category"].update(value=question_object["category"])

        if i == len(questions.keys()):
            window["next"].update(disabled=True)
        else:
            window["next"].update(disabled=False)
        if i == 1:
            window["previous"].update(disabled=True)
        else:
            window["previous"].update(disabled=False)


# question_dict = get_questions(season_number, min_threshold, max_threshold)
