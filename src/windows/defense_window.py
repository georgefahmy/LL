import PySimpleGUI as sg

from ..constants import CATEGORIES, DEFAULT_FONT


def open_defense_window():
    defense_layout = [
        [
            sg.Text("You: ", font=("Arial Bold", 14), expand_x=True),
            sg.Button(
                "Load Opponents", key="load_user_for_defense", font=sg.DEFAULT_FONT
            ),
            sg.Combo(
                [],
                font=DEFAULT_FONT,
                key="player_1",
                size=(10, 1),
                enable_events=True,
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
            sg.Button("Calculate HUN", key="calc_hun", font=sg.DEFAULT_FONT),
            sg.Button("Show Similarity", key="similarity_chart", font=sg.DEFAULT_FONT),
            sg.Button(
                "Category Metrics", key="category_button_defense", font=sg.DEFAULT_FONT
            ),
            sg.Button(
                "Today's Questions", key="todays_questions", font=sg.DEFAULT_FONT
            ),
            sg.Checkbox(
                "Display Submitted Answers", default=False, key="display_todays_answers"
            ),
        ],
        [sg.HorizontalSeparator()],
        [
            sg.Frame(
                title="Defense Strategy",
                size=(320, 250),
                expand_x=True,
                vertical_alignment="t",
                layout=[
                    [
                        sg.Text("Defense Strategy", font=DEFAULT_FONT),
                        sg.Text(expand_x=True),
                        sg.Text("Rec. Pts", font=DEFAULT_FONT),
                        sg.Text("% Corr", font=DEFAULT_FONT),
                    ],
                    [
                        sg.Column(
                            expand_x=True,
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
                                        justification="c",
                                    ),
                                    sg.Text(
                                        "",
                                        key=f"suggestion_percent_{i}",
                                        font=DEFAULT_FONT,
                                        justification="r",
                                    ),
                                ]
                                for i in range(1, 7)
                            ],
                        )
                    ],
                    [
                        sg.Button("Submit", key="submit_defense", font=sg.DEFAULT_FONT),
                        sg.Button("Clear", key="defense_clear", font=sg.DEFAULT_FONT),
                    ],
                ],
            ),
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
                        sg.Button(
                            "Search",
                            key="search_questions_button",
                            bind_return_key=True,
                            font=sg.DEFAULT_FONT,
                        ),
                    ],
                    [
                        sg.Text("", key="filtered_metrics", font=DEFAULT_FONT),
                        sg.Text("", expand_x=True),
                        sg.Button(
                            "Close All Questions",
                            key="close_all_question_popups_button",
                            font=sg.DEFAULT_FONT,
                        ),
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
