import os

import PySimpleGUI as sg

from logged_in_tools import CATEGORIES, DEFAULT_FONT

BASE_URL = "https://www.learnedleague.com"
WD = os.getcwd()
MODKOS = "https://www.learnedleague.com/images/misc/ModKos.png?t=1649"


def open_defense_window():
    defense_layout = [
        [
            sg.Text("You: ", font=("Arial Bold", 14), expand_x=True),
            sg.Combo(
                [],
                font=DEFAULT_FONT,
                key="player_1",
                size=(10, 1),
            ),
        ],
        [
            sg.Text("Opponent: ", font=("Arial Bold", 14), expand_x=True),
            sg.Combo(
                [],
                font=DEFAULT_FONT,
                key="opponent",
                size=(10, 1),
            ),
        ],
        [sg.HorizontalSeparator()],
        [
            sg.Text("HUN Similarity:", font=DEFAULT_FONT),
            sg.Text("", key="hun_score", font=DEFAULT_FONT),
        ],
        [
            sg.Button("Calculate HUN", key="calc_hun"),
            sg.Button("Show Similarity", key="similarity_chart"),
            sg.Button("Category Metrics", key="category_button_defense"),
            sg.Button("Today's Questions", key="todays_questions"),
            sg.Checkbox(
                "Display Submitted Answers", default=False, key="display_todays_answers"
            ),
        ],
        [sg.HorizontalSeparator()],
        [
            sg.Frame(
                title="Defense Strategy",
                expand_x=True,
                vertical_alignment="t",
                layout=[
                    [
                        sg.Text("Defense Strategy", font=DEFAULT_FONT),
                        sg.Text(expand_x=True),
                        sg.Text("Suggested Points", font=DEFAULT_FONT),
                    ],
                    [
                        sg.Column(
                            layout=[
                                [
                                    sg.Text(f"Q{i}:", font=DEFAULT_FONT),
                                    sg.Combo(
                                        CATEGORIES,
                                        key=f"defense_strat_{i}",
                                        font=DEFAULT_FONT,
                                        readonly=True,
                                        auto_size_text=True,
                                    ),
                                    sg.Text(key=f"space{i}", expand_x=True),
                                    sg.Text(
                                        "",
                                        key=f"defense_suggestion_{i}",
                                        font=DEFAULT_FONT,
                                        justification="r",
                                    ),
                                ]
                                for i in range(1, 7)
                            ],
                        )
                    ],
                    [
                        sg.Button("Submit", key="submit_defense"),
                        sg.Button("Clear", key="defense_clear"),
                    ],
                ],
            ),
            sg.Frame(
                title="Question History Search",
                expand_x=True,
                expand_y=True,
                layout=[
                    [
                        sg.Text("Search Text:", font=DEFAULT_FONT),
                        sg.Input(
                            "",
                            font=DEFAULT_FONT,
                            key="defense_question_search_term",
                            size=(15, 1),
                            expand_x=True,
                        ),
                        sg.Button("Search", key="search_questions_button"),
                    ],
                    [
                        sg.Text("", key="filtered_metrics", font=DEFAULT_FONT),
                    ],
                    [
                        sg.Multiline(
                            "",
                            font=DEFAULT_FONT,
                            key="output_questions",
                            expand_y=True,
                            expand_x=True,
                            disabled=True,
                            size=(25, 5),
                            tooltip="Highlight question and right click to open in browswer",
                            right_click_menu=["&Right", ["!Open Question"]],
                        ),
                    ],
                ],
            ),
        ],
    ]
    return sg.Window(
        "Defense Tactics",
        layout=defense_layout,
        finalize=True,
        return_keyboard_events=True,
        metadata="defense_window",
    )
