import io
import json
import os
import re

import PySimpleGUI as sg
import requests
from dotmap import DotMap
from PIL import Image

try:
    from ..constants import DEFAULT_FONT
except ImportError:
    DEFAULT_FONT = ("Arial", 14)


def get_specific_question(season, day, question):
    key = f"S{season}D{day}Q{question}"
    dmap = DotMap(all_data)
    return dmap[key]


def open_single_question(question_data, location=None, size=None, correct=None):
    qcode = f"S{question_data.season}{question_data.question_num}"
    sg.theme("reddit")
    if not size:
        size = (550, 144)
    if not location:
        screen_size = sg.Window.get_screen_size()
        center = (int(screen_size[0] / 2), int(screen_size[1] / 2))
        location = (center[0] - size[0] / 2, (center[1] - size[1] / 2) + 300)
    window = sg.Window(
        f"Question {qcode}",
        layout=[
            [
                sg.Frame(
                    title="",
                    expand_x=True,
                    expand_y=True,
                    background_color="light gray",
                    layout=(
                        [
                            sg.Multiline(
                                f"{question_data._question}",
                                background_color="light gray",
                                disabled=True,
                                no_scrollbar=True,
                                justification="l",
                                expand_x=True,
                                expand_y=True,
                                border_width=0,
                                font=DEFAULT_FONT,
                                key="Q",
                                size=(None, 4),
                                metadata=str(question_data.clickable_link),
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
                                f"({correct})",
                                expand_x=True,
                                key="correct_answer",
                                justification="c",
                                background_color=(
                                    "light green" if correct == "Correct" else "#FF474C"
                                ),
                                font=DEFAULT_FONT,
                                pad=0,
                            ),
                            sg.Text(
                                question_data.answer,
                                expand_x=True,
                                key="correct_answer",
                                justification="r",
                                background_color="light green",
                                font=DEFAULT_FONT,
                                pad=0,
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
                                question_data.percent,
                                expand_x=False,
                                size=(4, 1),
                                key="percent_correct",
                                justification="r",
                                background_color="light blue",
                                font=DEFAULT_FONT,
                            ),
                        ],
                    ),
                )
            ],
        ],
        size=size,
        location=location,
        resizable=True,
        finalize=True,
        metadata=f"single_quesiton_window_{qcode}",
    )

    window["Q"].bind("<ButtonPress-1>", "click_here")
    widget = window["Q"].Widget
    widget.tag_config("HIGHLIGHT", foreground="blue", font=("Arial", 14, "underline"))
    text = window["Q"].get()
    if "Click here" in text:
        index = text.index("Click here")
        indexes = (f"1.{index}", f"1.{index + 10}")
        widget.tag_add("HIGHLIGHT", indexes[0], indexes[1])
    return window


if __name__ == "__main__":
    datapath = os.path.expanduser("~") + "/.LearnedLeague/all_data.json"
    all_data = DotMap()
    if os.path.isfile(datapath):
        with open(datapath, "r") as fp:
            all_data = DotMap(json.load(fp))

    selected_text = "S74D17Q4"
    pattern = "S([0-9]+)D([0-9]+)Q([1-6])"
    match = re.match(pattern, selected_text)
    season, day, question_num = match.groups()
    window = open_single_question(get_specific_question(season, day, question_num))
    while True:
        event, values = window.read()
        # If the window is closed, break the loop and close the application
        if event in (None, "Quit", sg.WIN_CLOSED):
            window.close()
            break

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
