import json
import os
import random
import uuid
import webbrowser

import PySimpleGUI as sg
from dotmap import DotMap

from logged_in_tools import DEFAULT_FONT

namespace = uuid.UUID(int=1)


def generate_random_day(all_data, seed=None, threshold=0):
    random_list = []
    points = [3, 2, 2, 1, 1, 0]

    if seed:
        random.seed(seed)
    if 0 <= threshold < 95:
        all_data = DotMap(
            {k: v for k, v in all_data.items() if int(v.percent) > threshold}
        )
    while len(random_list) < 6:
        random_list.append(random.choice(list(all_data.keys())))
        random_list = list(set(random_list))
    chosen = DotMap()
    for x in random_list:
        chosen[x] = all_data[x]

    match_day = DotMap(questions=chosen)
    match_day.code = "-".join(list(match_day.questions.keys()))
    match_day.uuid = uuid.uuid3(namespace, match_day.code)
    for i, key in enumerate(
        sorted(match_day.questions.items(), key=lambda item: item[1].percent)
    ):
        match_day.questions[key[0]].assigned_point = points[i]
        match_day.questions[key[0]].index = i

    return match_day


def open_mock_day():
    datapath = os.path.expanduser("~") + "/.LearnedLeague/all_data.json"
    all_data = DotMap()
    if os.path.isfile(datapath):
        with open(datapath, "r") as fp:
            all_data = DotMap(json.load(fp))

    seed = None
    threshold = 0
    match_day = generate_random_day(all_data, seed=seed, threshold=threshold)

    # TODO create a folder (if not exist) that stores answers for questions/days and generate metrics.
    # TODO experiment - Do this with a database? make it online accessible for online competitions?
    # TODO future - expand available questions to include all questions in oneday and mini league sources

    sg.theme("reddit")
    window = sg.Window(
        "Mock Match Day - 6 Random Questions",
        layout=[
            [
                sg.Text(
                    "Practice Time!",
                    font=DEFAULT_FONT,
                ),
                sg.Text(expand_x=True),
                sg.Button("New Questions"),
            ],
            [
                sg.Column(
                    vertical_scroll_only=True,
                    expand_x=True,
                    expand_y=True,
                    layout=[
                        [
                            sg.Frame(
                                title="",
                                expand_x=True,
                                expand_y=True,
                                background_color="light gray",
                                key="",
                                layout=(
                                    [
                                        sg.Frame(
                                            "",
                                            layout=[
                                                [
                                                    sg.Text(
                                                        f"Q{i+1}:",
                                                        font=DEFAULT_FONT,
                                                        background_color="light gray",
                                                        key="",
                                                    ),
                                                ],
                                            ],
                                            vertical_alignment="t",
                                            background_color="light gray",
                                            relief=None,
                                            border_width=0,
                                            pad=0,
                                            key="",
                                        ),
                                        sg.Multiline(
                                            f"{v._question}",
                                            background_color="light gray",
                                            disabled=True,
                                            no_scrollbar=True,
                                            justification="l",
                                            expand_x=True,
                                            expand_y=True,
                                            border_width=0,
                                            font=DEFAULT_FONT,
                                            key=f"Q{i+1}",
                                            size=(None, 4),
                                        ),
                                    ],
                                    [
                                        sg.Input(
                                            "",
                                            expand_x=True,
                                            justification="l",
                                            background_color="white",
                                            border_width=1,
                                            key=f"submitted_answer_{i}",
                                            font=DEFAULT_FONT,
                                            use_readonly_for_disable=True,
                                        ),
                                        sg.Input(
                                            "",
                                            expand_x=False,
                                            size=(2, 1),
                                            justification="c",
                                            border_width=1,
                                            background_color="light gray",
                                            key=f"assigned_points_{i}",
                                            font=DEFAULT_FONT,
                                        ),
                                    ],
                                    [
                                        sg.Text(
                                            "Correct Answer:",
                                            expand_x=False,
                                            justification="l",
                                            background_color="light gray",
                                            font=DEFAULT_FONT,
                                        ),
                                        sg.Text(
                                            "",
                                            expand_x=True,
                                            key=f"correct_answer_{i}",
                                            justification="r",
                                            background_color="light green",
                                            font=DEFAULT_FONT,
                                        ),
                                    ],
                                ),
                            )
                        ]
                        for i, v in enumerate(match_day.questions.values())
                    ],
                )
            ],
            [sg.Button("Submit"), sg.Button("Show/Hide Answers")],
        ],
        size=(900, 900),
        resizable=True,
        finalize=True,
        metadata="mock_day",
    )
    return window


if __name__ == "__main__":
    datapath = os.path.expanduser("~") + "/.LearnedLeague/all_data.json"
    all_data = DotMap()
    if os.path.isfile(datapath):
        with open(datapath, "r") as fp:
            all_data = DotMap(json.load(fp))
    seed = None
    threshold = 0
    match_day = generate_random_day(all_data, seed=seed, threshold=threshold)
    window = open_mock_day()

    points = [q.assigned_point for q in match_day.questions.values()]
    answers = [q.answer for q in match_day.questions.values()]
    [window[f"Q{i+1}"].bind("<ButtonPress-1>", "click_here") for i in range(0, 6)]
    while True:
        event, values = window.read()
        # If the window is closed, break the loop and close the application
        if event in (None, "Quit", sg.WIN_CLOSED):
            window.close()
            break

        if event == "Submit":
            print([val for key, val in values.items() if "submitted_answer" in key])

            [
                window[f"assigned_points_{i}"].update(value=v.assigned_point)
                for i, v in enumerate(match_day.questions.values())
            ]
            [
                window[f"correct_answer_{i}"].update(value=v.answer)
                for i, v in enumerate(match_day.questions.values())
            ]
            [
                window[f"submitted_answer_{i}"].update(disabled=True)
                for i, v in enumerate(match_day.questions.values())
                if not window[f"submitted_answer_{i}"].get()
            ]

        if event == "Show/Hide Answers":
            [
                window[f"correct_answer_{i}"].update(value=v.answer)
                for i, v in enumerate(match_day.questions.values())
                if not window[f"correct_answer_{i}"].get()
            ]
            [
                window[f"correct_answer_{i}"].update(value="")
                for i, v in enumerate(match_day.questions.values())
                if window[f"correct_answer_{i}"].get()
            ]

        # Open the question item in your browser
        if "click_here" in event:
            q_id = event.split("click_here")[0]
            url = window[q_id].metadata
            print(url)
            if url:
                webbrowser.open(url)

        if "New" in event:
            match_day = generate_random_day(all_data, seed=seed, threshold=threshold)
            [
                window[f"Q{i+1}"].update(value=v._question)
                for i, v in enumerate(match_day.questions.values())
            ]
            [
                window[f"assigned_points_{i}"].update(value="")
                for i, v in enumerate(match_day.questions.values())
            ]
            [
                window[f"correct_answer_{i}"].update(value="")
                for i, v in enumerate(match_day.questions.values())
            ]
            [
                window[f"submitted_answer_{i}"].update(disabled=False)
                for i, v in enumerate(match_day.questions.values())
            ]
