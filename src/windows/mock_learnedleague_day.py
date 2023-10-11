import datetime
import io
import json
import os
import random
import uuid

import PySimpleGUI as sg
import requests
from dotmap import DotMap
from PIL import Image

from ..constants import DEFAULT_FONT

namespace = uuid.UUID(int=1)


def generate_random_day(mock_day_data, seed=None, threshold=0):
    random_list = []
    points = [3, 2, 2, 1, 1, 0]

    if 0 <= int(threshold) <= 95:
        mock_day_data = DotMap(
            {k: v for k, v in mock_day_data.items() if int(v.percent) > threshold}
        )

    if seed:
        random.seed(
            seed + int(datetime.datetime.today().date().strftime("%s")) + int(threshold)
        )
    else:
        random.seed(
            int(datetime.datetime.today().date().strftime("%s")) + int(threshold)
        )

    while len(random_list) < 6:
        random_list.append(random.choice(list(mock_day_data.keys())))
        random_list = list(set(random_list))

    random.Random(seed).shuffle(sorted(random_list))
    chosen = DotMap()
    for x in random_list:
        chosen[x] = mock_day_data[x]

    match_day = DotMap(questions=chosen)
    match_day.code = "-".join(sorted(list(match_day.questions.keys())))
    match_day.uuid = str(uuid.uuid3(namespace, match_day.code))
    match_day.date = str(datetime.datetime.today().date())
    for i, key in enumerate(
        sorted(match_day.questions.items(), key=lambda item: item[1].percent)
    ):
        match_day.questions[key[0]].assigned_point = points[i]
        match_day.questions[key[0]].index = i
    mock_matches_path = os.path.expanduser("~") + "/.LearnedLeague/mock_matches/"
    if not os.path.isdir(mock_matches_path):
        os.mkdir(mock_matches_path)
    with open(mock_matches_path + match_day.uuid + ".json", "w") as fp:
        json.dump(match_day, fp, indent=4)

    return match_day


def open_mock_day(seed=None, threshold=0):
    datapath = os.path.expanduser("~") + "/.LearnedLeague/all_data.json"
    mock_day_data = DotMap()
    if os.path.isfile(datapath):
        with open(datapath, "r") as fp:
            mock_day_data = DotMap(json.load(fp))

    match_day = generate_random_day(mock_day_data, seed=seed, threshold=threshold)

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
                sg.Checkbox("Random Seed", key="random_seed", font=DEFAULT_FONT),
                sg.Text("Percent  Threshold:", font=DEFAULT_FONT),
                sg.Combo(
                    default_value=0,
                    values=list(range(0, 96, 1)),
                    readonly=True,
                    key="perc_threshold",
                    font=DEFAULT_FONT,
                ),
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
                                            metadata=str(v.clickable_link),
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
                                            disabled_readonly_background_color="orange",
                                        ),
                                        sg.Text(
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
                                        sg.Text(
                                            "% Correct:",
                                            expand_x=False,
                                            size=(8, 1),
                                            justification="r",
                                            background_color="light gray",
                                            font=DEFAULT_FONT,
                                        ),
                                        sg.Text(
                                            "",
                                            expand_x=False,
                                            size=(4, 1),
                                            key=f"percent_correct_{i}",
                                            justification="r",
                                            background_color="light blue",
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
    for i in range(1, 7):
        window[f"Q{i}"].bind("<ButtonPress-1>", "click_here")
        widget = window[f"Q{i}"].Widget
        widget.tag_config(
            "HIGHLIGHT", foreground="blue", font=("Arial", 14, "underline")
        )
        text = window[f"Q{i}"].get()
        if "Click here" in text:
            index = text.index("Click here")
            indexes = (f"1.{index}", f"1.{index+10}")
            widget.tag_add("HIGHLIGHT", indexes[0], indexes[1])
    return window, match_day, seed, threshold, mock_day_data


if __name__ == "__main__":
    datapath = os.path.expanduser("~") + "/.LearnedLeague/all_data.json"
    mock_day_data = DotMap()
    if os.path.isfile(datapath):
        with open(datapath, "r") as fp:
            mock_day_data = DotMap(json.load(fp))
    seed = None
    threshold = 0
    match_day = generate_random_day(mock_day_data, seed=seed, threshold=threshold)
    window, match_day, seed, threshold, mock_day_data = open_mock_day(seed, threshold)

    while True:
        event, values = window.read()
        # If the window is closed, break the loop and close the application
        if event in (None, "Quit", sg.WIN_CLOSED):
            window.close()
            break

        if event == "Submit":
            print([val for key, val in values.items() if "submitted_answer" in key])

            for i, v in enumerate(match_day.questions.values()):
                window[f"assigned_points_{i}"].update(value=v.assigned_point)
                window[f"correct_answer_{i}"].update(value=v.answer)
                window[f"percent_correct_{i}"].update(value=f"{v.percent}%")
                window[f"submitted_answer_{i}"].update(disabled=True)
                window["Submit"].update(disabled=True)

        if event == "Show/Hide Answers":
            for i, v in enumerate(match_day.questions.values()):
                if window[f"correct_answer_{i}"].get():
                    window[f"correct_answer_{i}"].update(value="")
                    window[f"percent_correct_{i}"].update(value="")

                else:
                    window[f"correct_answer_{i}"].update(value=v.answer)
                    window[f"percent_correct_{i}"].update(value=f"{v.percent}%")

        # Open the question item in your browser
        if "click_here" in event:
            q_id = event.split("click_here")[0]
            if window[q_id].metadata:
                img_data = requests.get(window[q_id].metadata).content
                pil_image = Image.open(io.BytesIO(img_data))
                png_bio = io.BytesIO()
                pil_image.save(png_bio, format="PNG")
                png_data = png_bio.getvalue()
                img_window = sg.Window(
                    title="Image",
                    layout=[
                        [
                            sg.Image(
                                data=png_data,
                            )
                        ],
                    ],
                    finalize=True,
                    modal=False,
                )

        if "New" in event:
            if values["random_seed"]:
                seed = random.randint(0, 999)
            else:
                seed = None

            match_day = generate_random_day(
                mock_day_data, seed=seed, threshold=values["perc_threshold"]
            )

            for i, v in enumerate(match_day.questions.values()):
                window[f"Q{i+1}"].update(value=v._question)
                window[f"Q{i+1}"].metadata = v.clickable_link
                window[f"assigned_points_{i}"].update(value="")
                window[f"correct_answer_{i}"].update(value="")
                window[f"percent_correct_{i}"].update(value="")
                window[f"submitted_answer_{i}"].update(disabled=False, value="")
                window["Submit"].update(disabled=False)
                widget = window[f"Q{i+1}"].Widget
                widget.tag_config(
                    "HIGHLIGHT", foreground="blue", font=("Arial", 14, "underline")
                )
                text = window[f"Q{i+1}"].get()
                if "Click here" in text:
                    index = text.index("Click here")
                    indexes = (f"1.{index}", f"1.{index+10}")
                    widget.tag_add("HIGHLIGHT", indexes[0], indexes[1])
