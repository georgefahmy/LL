import PySimpleGUI as sg

layout = [
    [
        sg.Column(
            pad=(0, 0),
            layout=[
                [
                    sg.Frame(
                        "Input",
                        key="input_frame",
                        vertical_alignment="top",
                        element_justification="l",
                        size=(275, 155),
                        layout=[
                            [
                                sg.Text("Season (min 60): ", font=("Arial", 16)),
                                sg.Text(expand_x=True),
                                sg.Combo(
                                    [],
                                    default_value="97",
                                    key="season",
                                    font=("Arial", 16),
                                    readonly=True,
                                    expand_x=True,
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
                                    enable_events=True,
                                ),
                            ],
                            [
                                sg.Button("Retrieve Season", key="retrieve"),
                                sg.Text(expand_x=True),
                                sg.Button("Filter", key="filter", bind_return_key=True),
                            ],
                        ],
                    ),
                ]
            ],
        ),
        sg.Column(layout=[[]], expand_x=True),
        sg.Column(
            pad=(0, 0),
            vertical_alignment="top",
            layout=[
                [
                    sg.Frame(
                        "Information",
                        vertical_alignment="top",
                        size=(275, 155),
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
                                sg.Text(
                                    "",
                                    key="question_number",
                                    font=("Arial", 16),
                                    enable_events=True,
                                ),
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
                    )
                ]
            ],
        ),
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
                        font=("Arial", 24),
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
                            [sg.Text(key="answer", font=("Arial", 16), size=(10, 1), expand_x=True)]
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
                        "Next", key="next", disabled=True, disabled_button_color=("black", "gray")
                    ),
                    sg.Button(
                        "Previous",
                        key="previous",
                        disabled=True,
                        disabled_button_color=("black", "gray"),
                    ),
                ],
            ],
        )
    ],
]
