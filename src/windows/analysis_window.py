import PySimpleGUI as sg
from dotmap import DotMap

from ..constants import AVAIABLE_FIELDS, DEFAULT_FONT, VALID_OPERATORS


def open_analysis_window():
    analysis_layout = [
        [
            sg.Text("Season: ", font=("Arial Bold", 14), expand_x=True),
            sg.Combo(
                list(range(60, 100)),
                font=DEFAULT_FONT,
                key="season_selection",
                size=(10, 1),
                enable_events=True,
            ),
        ],
        [sg.HorizontalSeparator()],
        [
            sg.Text("Complete Stats Analysis", font=("Arial Bold", 16), expand_x=True),
        ],
        [
            sg.Text("Field: ", font=("Arial Bold", 14), expand_x=True),
            sg.Combo(
                AVAIABLE_FIELDS,
                font=DEFAULT_FONT,
                key="field",
                size=(10, 1),
            ),
        ],
        [
            sg.Text("Filter Operator: ", font=("Arial Bold", 14), expand_x=True),
            sg.Combo(
                VALID_OPERATORS,
                font=DEFAULT_FONT,
                key="operator",
                size=(10, 1),
            ),
        ],
        [
            sg.Text("Value: ", font=("Arial Bold", 14), expand_x=True),
            sg.Input(
                font=DEFAULT_FONT,
                key="overall_field_value",
                size=(10, 1),
            ),
        ],
        [
            sg.Button("Filter", key="overall_filter_button"),
        ],
        [sg.HorizontalSeparator()],
        [
            sg.Text(
                "Specific User Stats Analysis", font=("Arial Bold", 16), expand_x=True
            ),
        ],
        [
            sg.Text("User: ", font=("Arial Bold", 14), expand_x=True),
            sg.Combo(
                [],
                font=DEFAULT_FONT,
                key="user",
                size=(10, 1),
            ),
        ],
        [
            sg.Text("Mode: ", font=("Arial Bold", 14), expand_x=True),
            sg.Combo(
                ["invquant", "quant"],
                font=DEFAULT_FONT,
                key="mode",
                size=(10, 1),
            ),
        ],
        [
            sg.Text("Field: ", font=("Arial Bold", 14), expand_x=True),
            sg.Combo(
                AVAIABLE_FIELDS,
                font=DEFAULT_FONT,
                key="user_field",
                size=(10, 1),
            ),
        ],
        [
            sg.Text("Value: ", font=("Arial Bold", 14), expand_x=True),
            sg.Input(
                font=DEFAULT_FONT,
                key="user_field_value",
                size=(10, 1),
            ),
        ],
        [
            sg.Button("Filter", key="user_filter_button"),
        ],
    ]

    return sg.Window(
        "Data Analysis",
        layout=analysis_layout,
        finalize=True,
        metadata="analysis_window",
    )


def stats_filter(field, value, operator="in", user_stats=DotMap()):
    if not {True for u in user_stats.values() if field in u.toDict().keys()}:
        return user_stats

    if operator not in VALID_OPERATORS:
        print("Invalid Operator")
        return user_stats

    if value.isdigit():
        value = float(value)

    if operator == ">=":
        print("Greater than or Equal to operator")
        return DotMap({k: v for k, v in user_stats.items() if v[field] >= value})
    elif operator == ">":
        print("Greater than operator")
        return DotMap({k: v for k, v in user_stats.items() if v[field] > value})
    elif operator == "<=":
        print("Less than or Equal to operator")
        return DotMap({k: v for k, v in user_stats.items() if v[field] <= value})
    elif operator == "<":
        print("Less than operator")
        return DotMap({k: v for k, v in user_stats.items() if v[field] < value})
    elif operator == "==":
        print("Equals operator")
        return DotMap({k: v for k, v in user_stats.items() if v[field] == value})
    elif operator == "in":
        print("In operator")
        return DotMap({k: v for k, v in user_stats.items() if value in v[field]})
    elif operator == "not in":
        print("Not In operator")
        return DotMap({k: v for k, v in user_stats.items() if value not in v[field]})
    elif operator == "startswith":
        print("Startswith")
        return DotMap(
            {k: v for k, v in user_stats.items() if v[field].startswith(value)}
        )
    elif operator == "endswith":
        print("Endswith")
        return DotMap({k: v for k, v in user_stats.items() if v[field].endswith(value)})
    else:
        return user_stats


def calc_pct(user, field, user_stats, df, value=None, mode="invquant"):
    if mode == "invquant":
        value = user_stats[user][field]
        return (df[field] < value).mean()
    elif mode == "quant":
        if 0 <= value <= 1:
            return df[field].quantile(value)
        else:
            raise ValueError("percentiles should all be in the interval [0, 1]")
