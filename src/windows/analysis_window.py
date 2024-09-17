import PySimpleGUI as sg

from ..constants import DEFAULT_FONT, LUCK_FIELDS


def open_analysis_window(season=102):
    analysis_layout = [
        [
            sg.Text("Season: ", font=("Arial Bold", 14), expand_x=True),
            sg.Combo(
                list(range(60, season + 1)),
                default_value=season,
                font=DEFAULT_FONT,
                key="season_selection",
                size=(10, 1),
                enable_events=True,
                readonly=True,
            ),
        ],
        [sg.HorizontalSeparator()],
        [
            sg.Text("Username: ", font=("Arial Bold", 14), expand_x=True),
            sg.Text(expand_x=True),
            sg.Button(
                "Load Favorites", key="luck_load_favorites", font=sg.DEFAULT_FONT
            ),
            sg.Button(
                "Save Favorites", key="save_luck_favorites", font=sg.DEFAULT_FONT
            ),
        ],
        [
            sg.Input(key="single_user", font=DEFAULT_FONT, expand_x=True),
            sg.Button("Clear", key="luck_username_clear", font=sg.DEFAULT_FONT),
        ],
        [
            sg.Listbox(
                [],
                font=DEFAULT_FONT,
                key="user",
                size=(15, 10),
                select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE,
                no_scrollbar=True,
            ),
        ],
        [sg.HorizontalSeparator()],
        [sg.Text("Opt. Fields: ", font=("Arial Bold", 14), expand_x=True)],
        [
            sg.Listbox(
                LUCK_FIELDS,
                font=DEFAULT_FONT,
                key="field_selection",
                size=(15, 10),
                enable_events=True,
                select_mode=sg.LISTBOX_SELECT_MODE_MULTIPLE,
                no_scrollbar=True,
            ),
        ],
        [
            sg.Checkbox(
                "Display Rundle",
                font=("Arial Bold", 14),
                default=False,
                key="rundle_flag",
            ),
        ],
        [sg.HorizontalSeparator()],
        [
            sg.Button(
                button_text="Submit",
                key="submit_luck",
                font=sg.DEFAULT_FONT,
            )
        ],
    ]

    return sg.Window(
        "Data Analysis",
        layout=analysis_layout,
        finalize=True,
        metadata="analysis_window",
    )
