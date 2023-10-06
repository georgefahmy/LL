import json
import os
import random
import uuid

import PySimpleGUI as sg
from dotmap import DotMap

from logged_in_tools import DEFAULT_FONT

namespace = uuid.UUID(int=1)


def generate_random_day(all_data, seed=None, threshold=0):
    random_list = []
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
    return DotMap(questions=chosen)


datapath = os.path.expanduser("~") + "/.LearnedLeague/all_data.json"
all_data = DotMap()
if os.path.isfile(datapath):
    with open(datapath, "r") as fp:
        all_data = DotMap(json.load(fp))

points = [0, 1, 1, 2, 2, 3]
seed = None
threshold = 0
match_day = generate_random_day(all_data, seed=seed, threshold=threshold)
match_day.pprint(pformat="json")

match_day.code = "-".join(list(match_day.questions.keys()))
match_day.uuid = uuid.uuid3(namespace, match_day.code)


for i, key in enumerate(
    sorted(match_day.questions.items(), key=lambda item: item[1].percent)
):
    match_day.questions[key[0]].assigned_point = points[i]
    match_day.questions[key[0]].index = i


# TODO build layout similar to LL interface with above questions as input
# TODO make it so the questions are selected at the start of the day and don't change?
# TODO dont worry about metrics part
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
        ],
        [
            sg.Column(
                vertical_scroll_only=True,
                expand_x=True,
                expand_y=True,
                layout=[
                    [
                        sg.Frame(
                            title=q,
                            expand_x=True,
                            expand_y=True,
                            background_color="light gray",
                            layout=(
                                [
                                    sg.Frame(
                                        "",
                                        layout=[
                                            [
                                                sg.Text(
                                                    f"Q{v.index+1}:",
                                                    font=DEFAULT_FONT,
                                                    background_color="light gray",
                                                ),
                                            ],
                                        ],
                                        vertical_alignment="t",
                                        background_color="light gray",
                                        relief=None,
                                        border_width=0,
                                        pad=0,
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
                                    ),
                                ],
                                [
                                    sg.Input(
                                        "",
                                        expand_x=True,
                                        justification="l",
                                        background_color="white",
                                        border_width=1,
                                        key=f"submitted_answer_{v.index}",
                                        font=DEFAULT_FONT,
                                    ),
                                    sg.Input(
                                        "",
                                        expand_x=False,
                                        size=(2, 1),
                                        justification="c",
                                        border_width=1,
                                        background_color="light gray",
                                        key=f"assigned_points_{v.index}",
                                        font=DEFAULT_FONT,
                                    ),
                                ],
                                [
                                    sg.Text(
                                        background_color="light gray", expand_x=True
                                    ),
                                    sg.Text(
                                        "Correct Answer:",
                                        expand_x=False,
                                        justification="r",
                                        background_color="light gray",
                                        font=DEFAULT_FONT,
                                    ),
                                    sg.Text(
                                        "",
                                        expand_x=True,
                                        key=f"correct_answer_{v.index}",
                                        justification="r",
                                        background_color="light green",
                                        font=DEFAULT_FONT,
                                    ),
                                ],
                            ),
                        )
                    ]
                    for q, v in match_day.questions.items()
                ],
            )
        ],
        [sg.Button("Submit")],
    ],
    size=(650, 850),
    resizable=True,
    finalize=True,
    metadata="mock_day",
)
while True:
    event, values = window.read()
    # If the window is closed, break the loop and close the application
    if event in (None, "Quit", sg.WIN_CLOSED):
        window.close()
        break

    if event == "Submit":
        continue
