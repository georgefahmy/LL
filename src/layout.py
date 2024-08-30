import PySimpleGUI as sg

from .constants import DEFAULT_FONT

sg.theme("Reddit")

menu_bar_layout = [
    [
        "&File",
        [
            "LearnedLeague.com",
            "One Day Specials",
            "Mini Leagues",
            "!Player Tracker",
            "!Defense Tactics",
            "!Match Analysis",
            "Login",
            "!Logout",
        ],
    ],
    ["Help", ["!About", "!How To", "!Feedback"]],
]

main_layout = [
    [
        sg.Frame(
            "Input",
            key="input_frame",
            vertical_alignment="top",
            element_justification="l",
            size=(275, 175),
            expand_x=True,
            layout=[
                [
                    sg.Text(expand_x=True),
                    sg.Button("Filter", key="filter"),
                ],
                [
                    sg.Text("Search: ", font=("Arial", 14)),
                    sg.Input(
                        "",
                        key="search_criteria",
                        font=("Arial", 14),
                        expand_x=True,
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Season (min 60): ", font=("Arial", 14)),
                    sg.Text(expand_x=True),
                    sg.Combo(
                        [],
                        default_value="97",
                        key="season",
                        font=("Arial", 14),
                        readonly=True,
                        enable_events=True,
                        expand_x=True,
                    ),
                ],
                [
                    sg.Text("Min % Correct: ", font=("Arial", 14)),
                    sg.Text(expand_x=True),
                    sg.Input(
                        default_text="0",
                        key="min_%",
                        font=("Arial", 14),
                        size=(5, 1),
                        justification="right",
                    ),
                ],
                [
                    sg.Text("Max % Correct: ", font=("Arial", 14)),
                    sg.Text(expand_x=True),
                    sg.Input(
                        default_text="100",
                        key="max_%",
                        font=("Arial", 14),
                        size=(5, 1),
                        justification="right",
                    ),
                ],
                [
                    sg.Text("Category: ", font=("Arial", 14)),
                    sg.Text(expand_x=True),
                    sg.Combo(
                        [],
                        default_value="ALL",
                        key="category_selection",
                        font=("Arial", 14),
                        size=(15, 1),
                        readonly=True,
                        enable_events=True,
                    ),
                ],
            ],
        ),
        sg.Frame(
            "Rundle Metrics",
            vertical_alignment="top",
            size=(275, 175),
            key="season_info",
            expand_x=True,
            tooltip=(
                "Learned League has 5 Rundles (A, B, C, D, E and R).\n"
                + "Rundle A has the top players, and Rundle R is for "
                + "Rookies playing in their first season."
            ),
            layout=[
                [
                    sg.Text("Rundle A % Correct: ", font=("Arial", 14)),
                    sg.Text(expand_x=True),
                    sg.Text("", key="rundle_A", font=("Arial", 14)),
                ],
                [
                    sg.Text("Rundle B % Correct: ", font=("Arial", 14)),
                    sg.Text(expand_x=True),
                    sg.Text("", key="rundle_B", font=("Arial", 14)),
                ],
                [
                    sg.Text("Rundle C % Correct: ", font=("Arial", 14)),
                    sg.Text(expand_x=True),
                    sg.Text("", key="rundle_C", font=("Arial", 14)),
                ],
                [
                    sg.Text("Rundle D % Correct: ", font=("Arial", 14)),
                    sg.Text(expand_x=True),
                    sg.Text("", key="rundle_D", font=("Arial", 14)),
                ],
                [
                    sg.Text("Rundle E % Correct: ", font=("Arial", 14)),
                    sg.Text(expand_x=True),
                    sg.Text("", key="rundle_E", font=("Arial", 14)),
                ],
                [
                    sg.Text("Rundle R % Correct: ", font=("Arial", 14)),
                    sg.Text(expand_x=True),
                    sg.Text("", key="rundle_R", font=("Arial", 14)),
                ],
            ],
        ),
        sg.Frame(
            "Question Metrics",
            vertical_alignment="top",
            size=(275, 175),
            expand_x=True,
            key="info_box",
            layout=[
                [
                    sg.Text("Date: ", font=("Arial", 14)),
                    sg.Text(expand_x=True),
                    sg.Text(
                        "",
                        key="date",
                        font=("Arial", 14),
                    ),
                ],
                [
                    sg.Text("Season: ", font=("Arial", 14)),
                    sg.Text(expand_x=True),
                    sg.Text(
                        "",
                        key="season_number",
                        font=("Arial", 14),
                    ),
                ],
                [
                    sg.Text("Question: ", font=("Arial", 14)),
                    sg.Text(expand_x=True),
                    sg.Text(
                        "",
                        key="question_number",
                        font=("Arial", 14),
                        enable_events=True,
                    ),
                ],
                [
                    sg.Text("Category: ", font=("Arial", 14)),
                    sg.Text(expand_x=True),
                    sg.Text("", key="question_category", font=("Arial", 14)),
                ],
                [
                    sg.Text(
                        "% Correct: ",
                        font=("Arial", 14),
                        tooltip="Percentage of people who got the answer correct",
                    ),
                    sg.Text(
                        expand_x=True,
                        tooltip="Percentage of people who got the answer correct",
                    ),
                    sg.Text(
                        "",
                        key="%_correct",
                        font=("Arial", 14),
                        tooltip="Percentage of people who got the answer correct",
                    ),
                ],
                [
                    sg.Text(
                        "Defense Value: ",
                        font=("Arial", 14),
                        tooltip="Values 0 - 3 with 3 being considered "
                        + "hardest and 0 considered easiest",
                    ),
                    sg.Text(
                        expand_x=True,
                        tooltip="Values 0 - 3 with 3 being considered "
                        + "hardest and 0 considered easiest",
                    ),
                    sg.Text(
                        "",
                        key="defense",
                        font=("Arial", 14),
                        tooltip="Values 0 - 3 with 3 being considered "
                        + "hardest and 0 considered easiest",
                    ),
                ],
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
                        size=(60, 5),
                        font=("Arial", 22),
                        disabled=True,
                        no_scrollbar=True,
                        expand_x=True,
                        expand_y=True,
                        enable_events=True,
                        right_click_menu=["&Right", ["!Lookup Selection"]],
                    )
                ],
                [
                    sg.Button(
                        "Show Answer",
                        key="show/hide",
                        size=(12, 1),
                        font=("Arial", 12),
                        tooltip="Reveal the Answer - (cmd-s)",
                    ),
                    sg.Text(
                        key="answer",
                        font=("Arial", 14),
                        size=(10, 1),
                        expand_x=True,
                    ),
                ],
                [
                    sg.Text(
                        "Total Questions: ",
                        font=("Arial", 14),
                        tooltip="Questions available with the current filters.",
                    ),
                    sg.Text("", key="num_questions", font=("Arial", 14), expand_x=True),
                    sg.Button(
                        "Random Q",
                        key="random_choice",
                        size=(9, 1),
                        font=("Arial", 12),
                        tooltip="Pick a random question - (cmd-r)",
                    ),
                    sg.Combo(
                        values=[],
                        default_value="1",
                        key="dropdown",
                        size=(4, 1),
                        font=("Arial", 14),
                        readonly=True,
                        enable_events=True,
                    ),
                    sg.Button(
                        "Previous",
                        key="previous",
                        disabled=True,
                        disabled_button_color=("black", "gray"),
                        tooltip="Go to the previous question - (cmd-p)",
                    ),
                    sg.Button(
                        "Next",
                        key="next",
                        disabled=True,
                        disabled_button_color=("black", "gray"),
                        tooltip="Go to the next question - (cmd-n)",
                    ),
                ],
                [
                    sg.Text(
                        "Answer: ",
                        font=("Arial", 14),
                    ),
                    sg.Input(
                        "",
                        key="answer_submission",
                        font=("Arial", 14),
                        expand_x=True,
                        use_readonly_for_disable=True,
                    ),
                    sg.Button(
                        "Submit Answer",
                        key="submit_answer_button",
                        disabled_button_color=("black", "gray"),
                        bind_return_key=True,
                    ),
                    sg.Checkbox(
                        "Ans Override",
                        key="correct_override",
                        disabled=True,
                        enable_events=True,
                        tooltip=(
                            "Automated answer checking may be incorrect.\n"
                            + "Use this checkbox to override an incorrect answer "
                            + "assessment \n(both right and wrong answers)."
                        ),
                    ),
                ],
            ],
        )
    ],
]

super_layout = [
    [sg.Menu(menu_bar_layout, font=DEFAULT_FONT, key="-MENU-")],
    [
        sg.Frame(
            "Main",
            expand_x=True,
            layout=[
                [
                    sg.Button(
                        "OneDay Specials",
                        key="onedays_button",
                        tooltip="OneDay trivia (opens new window)",
                    ),
                    sg.Button(
                        "Mini Leagues",
                        key="minileague_button",
                        tooltip="Mini League trivia (opens new window)",
                    ),
                    sg.Button(
                        "Mock Match Day",
                        key="mock_day",
                        tooltip="Mini League trivia (opens new window)",
                    ),
                    sg.Button(
                        "Stats",
                        key="stats_button",
                        tooltip="Open the Statistics Window to compare player stats",
                        disabled=True,
                        disabled_button_color=("black", "gray"),
                    ),
                    sg.Button(
                        "Defense",
                        key="defense_button",
                        tooltip="Open the Defense Tactics window",
                        disabled=True,
                        disabled_button_color=("black", "gray"),
                    ),
                    sg.Button(
                        "Luck Analysis",
                        key="analysis_button",
                        tooltip="Open the Match Analysis window",
                        disabled=True,
                        disabled_button_color=("black", "gray"),
                    ),
                    sg.Button(
                        "Question History",
                        key="question_history_button",
                        tooltip="Open a Window for the question history of a user",
                        disabled=True,
                        disabled_button_color=("black", "gray"),
                    ),
                    sg.Text(expand_x=True),
                    sg.Button(
                        "Open LL",
                        key="open_ll",
                        tooltip="Click this button to open the LearnedLeague.com wbsite",
                    ),
                    sg.Button(
                        "Login",
                        key="login_button",
                        size=(7, 1),
                        tooltip="Login to see details from your personal data",
                    ),
                ],
            ],
        )
    ],
    [
        sg.Frame(
            title="Practice",
            layout=main_layout,
            expand_x=True,
            expand_y=True,
        )
    ],
]
