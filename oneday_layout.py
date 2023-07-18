import PySimpleGUI as sg

font = "Arial", 16
layout = [
    [
        sg.Frame(
            "OneDay Selection",
            size=(325, 110),
            layout=[
                [
                    sg.Text("Search:", font=font),
                    sg.Input("", key="oneday_search", font=font, size=(14, 1), expand_x=True),
                    sg.Button("Search", font=font, key="oneday_filter_search"),
                ],
                [
                    sg.Text("OneDay:", font=font, tooltip="Choose a OneDay to load"),
                    sg.Combo(
                        values=[],
                        key="oneday_selection",
                        font=font,
                        size=(40, 1),
                        expand_x=True,
                        readonly=True,
                        enable_events=True,
                        tooltip="Choose a OneDay to load",
                    ),
                ],
                [
                    sg.Button("Show Description", key="show_hide_blurb"),
                    sg.Text(expand_x=True),
                    sg.Button("Random", key="random_oneday"),
                ],
            ],
        ),
        sg.Frame(
            "OneDay Info",
            size=(325, 110),
            layout=[
                [sg.Text("", key="oneday_title", font=font)],
                [
                    sg.Text(
                        "Difficulty: ",
                        font=font,
                        enable_events=True,
                        key="difficulty_tooltip",
                        tooltip="https://www.learnedleague.com/images/misc/ModKos.png?t=1649",
                        metadata="https://www.learnedleague.com/images/misc/ModKos.png?t=1649",
                    ),
                    sg.Text("", key="difficulty", font=font, expand_x=True),
                    sg.Text("Date:", font=font),
                    sg.Text("", font=font, key="oneday_date"),
                ],
                [
                    sg.Text("Overall Correct Rate: ", font=font),
                    sg.Text("", key="percent_correct", font=font),
                ],
            ],
        ),
        sg.Frame(
            "Question Metrics",
            size=(325, 110),
            layout=[
                [sg.Text("Your Current Score:", font=font), sg.Text("", key="score", font=font)],
                [sg.HorizontalSeparator()],
                [
                    sg.Text(
                        "CA%:",
                        font=font,
                        tooltip="Correct Answer Percentage (all players)",
                    ),
                    sg.Text(
                        "Submit answer to see",
                        key="question_percent_correct",
                        font=("Arial Italic", 10),
                        tooltip="Correct Answer Percentage (all players)",
                    ),
                ],
            ],
        ),
    ],
    [
        sg.Frame(
            "Blurb",
            expand_x=True,
            key="blurb_frame",
            size=(300, 1),
            layout=[
                [
                    sg.Multiline(
                        "",
                        expand_x=True,
                        expand_y=True,
                        disabled=True,
                        no_scrollbar=True,
                        key="blurb_text",
                        font=("Arial", 14),
                    )
                ],
            ],
        )
    ],
    [
        sg.Frame(
            "Question",
            size=(300, 300),
            expand_x=True,
            layout=[
                [
                    sg.Multiline(
                        key="question",
                        font=("Arial", 24),
                        disabled=True,
                        no_scrollbar=True,
                        expand_x=True,
                        expand_y=True,
                        enable_events=True,
                        right_click_menu=["&Right", ["!Lookup Selection"]],
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
                    sg.Checkbox(
                        "Money Question",
                        key="money_check",
                        font=font,
                        tooltip="If correct - get points equal to % of people who got the question wrong",
                        pad=((5, 0), (5, 5)),
                    ),
                    sg.Text("(", font=font, pad=0),
                    sg.Text(str(5), font=font, key="num_of_money_questions_left", pad=0),
                    sg.Text(")", font=font, pad=0),
                    sg.Button(
                        "Show Answer",
                        key="show/hide",
                        size=(12, 1),
                        font=("Arial", 12),
                        tooltip="Reveal the Answer - (s)",
                        disabled_button_color=("black", "gray"),
                    ),
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
                        "Previous",
                        key="previous",
                        disabled=True,
                        disabled_button_color=("black", "gray"),
                    ),
                    sg.Button(
                        "Next",
                        key="next",
                        disabled=True,
                        disabled_button_color=("black", "gray"),
                    ),
                ],
            ],
        )
    ],
    [
        sg.Frame(
            "Submission",
            expand_x=True,
            layout=[
                [
                    sg.Text("Answer: ", font=("Arial", 16)),
                    sg.Input("", key="answer_submission", font=("Arial", 16), expand_x=True),
                    sg.Button(
                        "Submit Answer",
                        key="submit_answer_button",
                        disabled_button_color=("black", "gray"),
                        bind_return_key=True,
                    ),
                ],
            ],
        )
    ],
]
