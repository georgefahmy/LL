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
                        size=(275, 185),
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
                                    enable_events=True,
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
                                sg.Text(expand_x=True),
                                sg.Button("Filter", key="filter", bind_return_key=True),
                            ],
                        ],
                    ),
                ]
            ],
        ),
        sg.Column(
            pad=(0, 0),
            vertical_alignment="top",
            layout=[
                [
                    sg.Frame(
                        "Rundle Metrics",
                        vertical_alignment="top",
                        size=(275, 185),
                        key="season_info",
                        expand_x=True,
                        layout=[
                            [
                                sg.Text("Rundle A: ", font=("Arial", 16)),
                                sg.Text(expand_x=True),
                                sg.Text("", key="rundle_A", font=("Arial", 16)),
                            ],
                            [
                                sg.Text("Rundle B: ", font=("Arial", 16)),
                                sg.Text(expand_x=True),
                                sg.Text("", key="rundle_B", font=("Arial", 16)),
                            ],
                            [
                                sg.Text("Rundle C: ", font=("Arial", 16)),
                                sg.Text(expand_x=True),
                                sg.Text("", key="rundle_C", font=("Arial", 16)),
                            ],
                            [
                                sg.Text("Rundle D: ", font=("Arial", 16)),
                                sg.Text(expand_x=True),
                                sg.Text("", key="rundle_D", font=("Arial", 16)),
                            ],
                            [
                                sg.Text("Rundle E: ", font=("Arial", 16)),
                                sg.Text(expand_x=True),
                                sg.Text("", key="rundle_E", font=("Arial", 16)),
                            ],
                            [
                                sg.Text("Rundle R: ", font=("Arial", 16)),
                                sg.Text(expand_x=True),
                                sg.Text("", key="rundle_R", font=("Arial", 16)),
                            ],
                        ],
                    )
                ]
            ],
            expand_x=True,
        ),
        sg.Column(
            pad=(0, 0),
            vertical_alignment="top",
            layout=[
                [
                    sg.Frame(
                        "Question Metrics",
                        vertical_alignment="top",
                        size=(275, 185),
                        key="info_box",
                        layout=[
                            [
                                sg.Text(
                                    "",
                                    key="date",
                                    font=("Arial", 16),
                                ),
                            ],
                            [
                                sg.Text("Season: ", font=("Arial", 16)),
                                sg.Text(expand_x=True),
                                sg.Text(
                                    "",
                                    key="season_number",
                                    font=("Arial", 16),
                                ),
                            ],
                            [
                                sg.Text("Question: ", font=("Arial", 16)),
                                sg.Text(expand_x=True),
                                sg.Text(
                                    "",
                                    key="question_number",
                                    font=("Arial", 16),
                                ),
                            ],
                            [
                                sg.Text("Category: ", font=("Arial", 16)),
                                sg.Text(expand_x=True),
                                sg.Text("", key="question_category", font=("Arial", 16)),
                            ],
                            [
                                sg.Text(
                                    "Correct %: ",
                                    font=("Arial", 16),
                                    tooltip="Percentage of people who got the answer correct",
                                ),
                                sg.Text(
                                    expand_x=True,
                                    tooltip="Percentage of people who got the answer correct",
                                ),
                                sg.Text(
                                    "",
                                    key="%_correct",
                                    font=("Arial", 16),
                                    tooltip="Percentage of people who got the answer correct",
                                ),
                            ],
                            [
                                sg.Text(
                                    "Defense Value: ",
                                    font=("Arial", 16),
                                    tooltip="Values 0 - 3 with 3 being considered hardest and 0 considered easiest",
                                ),
                                sg.Text(
                                    expand_x=True,
                                    tooltip="Values 0 - 3 with 3 being considered hardest and 0 considered easiest",
                                ),
                                sg.Text(
                                    "",
                                    key="defense",
                                    font=("Arial", 16),
                                    tooltip="Values 0 - 3 with 3 being considered hardest and 0 considered easiest",
                                ),
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
                    sg.Text("Total Questions: ", font=("Arial", 16)),
                    sg.Text("", key="num_questions", font=("Arial", 16)),
                    sg.Text("", expand_x=True),
                    sg.Button("Random Q", key="random_choice", size=(12, 1), font=("Arial", 12)),
                    sg.Combo(
                        values=[],
                        default_value="1",
                        key="dropdown",
                        size=(4, 1),
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
