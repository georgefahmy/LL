import os

import PySimpleGUI as sg
from dotmap import DotMap

from logged_in_tools import DEFAULT_FONT, STATS_DEFINITION

BASE_URL = "https://www.learnedleague.com"
WD = os.getcwd()
MODKOS = "https://www.learnedleague.com/images/misc/ModKos.png?t=1649"


def Sort(sub_li, col, reverse=True):
    if col in [0, 1, 19, 20]:
        table_values = sorted(sub_li, key=lambda x: x[col], reverse=reverse)
    else:
        table_values = sorted(sub_li, key=lambda x: float(x[col]), reverse=reverse)
    return table_values, reverse


def add_stats_row(user_data, window, season="total"):
    current_values = window["stats_table"].get()
    loaded_stats = window["stats_table"].metadata
    if not loaded_stats:
        loaded_stats = DotMap()
    loaded_stats[user_data.formatted_username] = DotMap(
        {"formatted_username": user_data.formatted_username, "stats": user_data.stats}
    )
    window["stats_table"].metadata = loaded_stats
    if user_data.formatted_username in [row[0] for row in current_values]:
        return
    table_values = [
        [user_data.formatted_username]
        + [user_data.stats[season].get(key) for key in list(STATS_DEFINITION)]
        + ["X"]
    ]
    if current_values:
        table_values = current_values + table_values
    window["stats_table"].update(values=table_values)
    return table_values


def remove_stats_row(window, row):
    current_values = window["stats_table"].get()
    del current_values[row]

    window["stats_table"].update(values=current_values)
    return current_values


def remove_all_rows(window):
    window["stats_table"].update(values=[])
    return []


def open_stats_window():
    stats_layout = [
        [
            sg.Text(
                "Player Search:",
                font=("Arial", 14),
                justification="r",
            ),
            sg.Input(
                "",
                key="player_search",
                font=("Arial", 14),
                size=(15, 15),
                use_readonly_for_disable=True,
                enable_events=True,
            ),
            sg.Button(
                "Search",
                key="player_search_button",
                size=(10, 1),
            ),
            sg.Combo(
                [],
                key="available_users",
                readonly=True,
                enable_events=True,
                font=DEFAULT_FONT,
                size=(10, 1),
            ),
            sg.Button("Category Metrics", size=(16, 1), key="category_button_stats"),
            sg.Button("Latest Season", size=(14, 1), key="latest_season_switch"),
            sg.Text(expand_x=True),
            sg.Button("Clear All", size=(14, 1), key="clear_all_stats"),
            sg.Button("Load All", size=(14, 1), key="load_all"),
        ],
        [
            sg.Table(
                values=[],
                headings=[
                    key
                    for key in ["Username"] + list(STATS_DEFINITION.keys()) + ["Remove"]
                ],
                alternating_row_color="light gray",
                header_font=("Arial Bold", 14),
                font=DEFAULT_FONT,
                enable_events=True,
                enable_click_events=True,
                num_rows=20,
                expand_x=True,
                expand_y=True,
                auto_size_columns=False,
                col_widths=[
                    min(len(key) + 2, 10)
                    for key in ["Username"] + list(STATS_DEFINITION.keys()) + ["Remove"]
                ],
                max_col_width=15,
                justification="c",
                vertical_scroll_only=True,
                hide_vertical_scroll=True,
                select_mode="browse",
                key="stats_table",
            )
        ],
    ]

    return sg.Window(
        "Statistics - Player Tracker",
        layout=stats_layout,
        finalize=True,
        return_keyboard_events=True,
        metadata="stats_window",
        resizable=True,
    )
