import PySimpleGUI as sg

from ..constants import DEFAULT_FONT


def open_question_history_window():
    analysis_layout = [
        [
            sg.Text("Username: ", font=("Arial Bold", 14), expand_x=True),
            sg.Input(key="username_history", font=DEFAULT_FONT, expand_x=True),
            sg.Button(
                "Retrieve Q-History", key="get_history_button", font=DEFAULT_FONT
            ),
        ],
        [sg.HorizontalSeparator()],
        [
            sg.Frame(
                title="Question History Search",
                size=(320, 250),
                expand_x=True,
                expand_y=True,
                layout=[
                    [
                        sg.Text("Search Text:", font=DEFAULT_FONT),
                        sg.Input(
                            "",
                            font=DEFAULT_FONT,
                            key="defense_question_search_term",
                            size=(16, 1),
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
                            size=(35, 7),
                            tooltip="Highlight question and right click to open in browswer",
                            right_click_menu=["&Right", ["!Open Question"]],
                        ),
                    ],
                ],
            ),
        ],
    ]

    return sg.Window(
        "Question History",
        layout=analysis_layout,
        finalize=True,
        metadata="question_history_window",
    )
