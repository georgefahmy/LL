import base64
import datetime
import json
import os
import re
import sys
import webbrowser
from random import choice, randint
from textwrap import wrap

import pandas as pd
import PySimpleGUI as sg
import wikipedia
from dotmap import DotMap
from PyDictionary import PyDictionary

from src.answer_correctness import combined_correctness
from src.check_for_updates import check_for_update
from src.constants import ALL_DATA_BASE_URL, DEFAULT_FONT
from src.layout import super_layout
from src.logged_in_tools import (
    display_category_metrics,
    display_todays_questions,
    login,
)
from src.radar_chart import radar_similarity
from src.url_tools import get_image_data, get_new_data, get_season_and_day
from src.userdata import UserData, load
from src.windows.analysis_window import calc_pct, open_analysis_window, stats_filter
from src.windows.defense_window import open_defense_window
from src.windows.minileagues import (
    get_mini_data,
    get_specific_minileague,
    load_questions,
    minileague,
    q_num_finder,
)
from src.windows.mock_learnedleague_day import generate_random_day, open_mock_day
from src.windows.onedays import (
    get_oneday_data,
    get_specific_oneday,
    oneday_main,
    search_onedays,
)
from src.windows.single_question_popup import open_single_question
from src.windows.statistics_window import (
    add_stats_row,
    open_stats_window,
    remove_all_rows,
    remove_stats_row,
    sort,
)

print(sg.get_versions())

BASE_URL = "https://www.learnedleague.com"

WD = os.getcwd()
USER_DATA_DIR = os.path.expanduser("~") + "/.LearnedLeague/user_data/"


if restart := check_for_update():
    restart = False
    os.execv(sys.executable, ["python"] + sys.argv)


def filter_questions(all_data, min_t, max_t, cat_filt, seas_filt, search_criteria=None):
    """_summary_

    Args:
        all_data (dict): Unfiltered full data dictionary
        min_t (int): Minimum % correct
        max_t (int): Maximum % correct
        cat_filt (str): Limit questions to specific category
        seas_filt (str): Limit questions to specific season
        search_criteria (str, optional): Keyword to search for in the questions. Defaults to None.

    Returns:
        final_filtered_questions_dict: dictionary of the filtered questions
    """
    min_t = int(min_t)
    max_t = int(max_t)

    if max_t <= min_t:
        max_t = min_t + 5

    if cat_filt == "ALL":
        filtered_questions_dict = {
            question_ids: question
            for question_ids, question in all_data.items()
            if int(question["percent"]) >= min_t and int(question["percent"]) < max_t
        }
    else:
        filtered_questions_dict = {
            question_ids: question
            for question_ids, question in all_data.items()
            if int(question["percent"]) >= min_t
            and int(question["percent"]) < max_t
            and question["category"].upper() == cat_filt.upper()
        }

    if seas_filt != "ALL":
        filtered_questions_dict = {
            question_ids: question
            for question_ids, question in filtered_questions_dict.items()
            if question["season"] == seas_filt
        }

    if search_criteria:
        filtered_questions_dict = {
            question_ids: question
            for question_ids, question in filtered_questions_dict.items()
            if search_criteria.lower() in question["_question"].lower()
        }

    return {
        i + 1: val
        for i, val in enumerate(
            filtered_questions_dict[key] for key in filtered_questions_dict
        )
    }


def update_question(questions, window, i):
    """Update the question window with the question information provided

    Args:
        questions (dict): Full list of questions (filtered or unfiltered)
        window (obj): The Window object
        i (int): the question number

    Returns:
        dict: the question object that gets returned for access later
    """
    question_object = questions.get(i)
    if not question_object:
        return
    question = question_object.get("_question")

    window["question"].update(value=question)
    window["question"].metadata = question_object.get("clickable_link")
    window["num_questions"].update(value=len(list(questions.keys())))
    window["%_correct"].update(value=str(question_object["percent"]) + "%")
    window["season_number"].update(value=question_object["season"])
    window["question_number"].update(value=question_object["question_num"])
    window["question_number"].set_tooltip("Click to Open: " + question_object["url"])
    window["question_number"].metadata = question_object["url"]
    window["question_category"].update(value=question_object["category"])
    window["defense"].update(value=question_object["defense"])
    window["answer"].update(value="******")
    window["show/hide"].update(text="Show Answer")
    window["next"].update(disabled=False)
    window["dropdown"].update(value=i)
    window["date"].update(value=question_object["date"])

    window["rundle_A"].update(value=question_object["A"] + "%")
    window["rundle_B"].update(value=question_object["B"] + "%")
    window["rundle_C"].update(value=question_object["C"] + "%")
    window["rundle_D"].update(value=question_object["D"] + "%")
    window["rundle_E"].update(value=question_object["E"] + "%")
    window["rundle_R"].update(value=question_object["R"] + "%")
    widget = window["question"].Widget
    widget.tag_config("HIGHLIGHT", foreground="blue", font=("Arial", 22, "underline"))
    text = window["question"].get()
    if "Click here" in text:
        index = text.index("Click here")
        indexes = (f"1.{index}", f"1.{index+10}")
        widget.tag_add("HIGHLIGHT", indexes[0], indexes[1])
    window.refresh()

    return question_object


def setup_window(window, questions):
    window["dropdown"].update(values=list(questions.keys()))
    window.bind("<Command-s>", "show_key")
    window.bind("<Command-r>", "random_key")
    window.bind("<Command-n>", "next_key")
    window.bind("<Command-p>", "previous_key")
    window["question"].bind("<ButtonPress-2>", "press")
    window["question"].bind("<ButtonPress-1>", "click_here")
    window["answer_submission"].bind("<Return>", "_submit_answer_button")
    window["category_selection"].update(
        values=["ALL"] + sorted(list({q["category"] for q in all_data.values()})),
        value="ALL",
    )
    window["season"].update(
        values=["ALL"] + sorted(list({q["season"] for q in all_data.values()})),
        value="ALL",
    )
    window["next"].update(disabled=False)
    window["previous"].update(disabled=False)
    return window


def get_specific_question(all_data, season, day, question):
    key = f"S{season}D{day.zfill(2)}Q{question}"
    dmap = DotMap(all_data)
    return dmap[key]


latest_season, current_day = get_season_and_day()

available_seasons = [str(season) for season in list(range(60, int(latest_season) + 1))]

datapath = os.path.expanduser("~") + "/.LearnedLeague/all_data.json"
all_data = {}
if os.path.isfile(datapath):
    with open(datapath, "r") as fp:
        all_data = json.load(fp)

season_in_data = sorted(
    list({val.split("D")[0].strip("S") for val in list(all_data.keys())})
)

missing_seasons = sorted(
    list(set(available_seasons).symmetric_difference(set(season_in_data)))
)

for season in available_seasons:
    season_questions = sum(season in key for key in all_data.keys())
    if season_questions < (current_day * 6) and current_day > 0:
        missing_seasons += [season]

if len(missing_seasons) > 0 and current_day > 0:
    all_data = get_new_data(season)

sess = None
values = None
logged_in = False
reverse = True
score = 0
num_of_money_questions_left = 5
submitted_answers = {}

icon_file = WD + "/resources/ll_app_logo.png"
sg.theme("Reddit")
sg.set_options(icon=base64.b64encode(open(str(icon_file), "rb").read()))
window = sg.Window(
    "Learned League Practice Tool",
    layout=super_layout,
    finalize=True,
    resizable=True,
    element_justification="center",
    return_keyboard_events=True,
    relative_location=(0, -200),
    metadata="main_window",
)

questions = filter_questions(
    all_data, min_t=0, max_t=101, cat_filt="ALL", seas_filt="ALL"
)
i = min(max(2, choice(list(questions.keys()))), len(list(questions.keys())) - 1)
question_object = update_question(questions, window, i)
main_window = setup_window(window, questions)

(
    oneday_window,
    minileague_window,
    stats_window,
    defense_window,
    mock_day_window,
    analysis_window,
) = (None, None, None, None, None, None)

open_windows = {
    "main_window": window.metadata,
    "oneday_window": oneday_window,
    "minileague_window": minileague_window,
    "stats_window": stats_window,
    "defense_window": defense_window,
    "mock_day_window": mock_day_window,
    "analysis_window": analysis_window,
    "category_metrics_window": None,
    "similarity_chart_window": None,
    "todays_question_window": None,
    "single_quesiton_window": None,
}

while True:
    window, event, values = sg.read_all_windows()
    # If the window is closed, break the loop and close the application
    if event in (None, "Quit", sg.WIN_CLOSED):
        open_windows[window.metadata] = None
        window.close()
        if window == main_window:
            if sess:
                sess.close()
            break

    if event:
        # print(window.metadata, event)

        if window.metadata == "main_window":
            # Login to the LL website with provided credentials. This will expand the interface
            # to include significantly more data and capabilities
            if event in ["login_button", "Login", "Logout"]:
                user_data = None
                if window["login_button"].get_text() == "Login":
                    sess = login()
                    if not sess:
                        continue
                    username = sess.headers.get("profile")
                    user_data = load(username=username, sess=sess)
                    menu_bar_layout = [
                        [
                            "&File",
                            [
                                "LearnedLeague.com",
                                "One Day Specials",
                                "Mini Leagues",
                                "Player Tracker",
                                "Defense Tactics",
                                "Match Analysis",
                                "!Login",
                                "Logout",
                            ],
                        ],
                        ["Help", ["!About", "!How To", "!Feedback"]],
                    ]

                    window["-MENU-"].update(menu_definition=menu_bar_layout)

                    if user_data.ok:
                        logged_in = True
                        logged_in_user = user_data.username
                        window["login_button"].update(text="Logout")
                        window["stats_button"].update(disabled=False)
                        window["defense_button"].update(disabled=False)
                        # TODO change to False to enable analysis once analysis window is sufficiently good
                        window["analysis_button"].update(disabled=True)
                        combo_values = sorted(
                            list(
                                set(
                                    [
                                        UserData.format_username(name.split(".")[0])
                                        for name in os.listdir(USER_DATA_DIR)
                                    ]
                                    + [
                                        UserData.format_username(name)
                                        for name in user_data.opponents
                                    ]
                                )
                            )
                        )

                        window_width, window_height = window.size
                        screen_width, screen_height = window.get_screen_size()
                        x = (screen_width - window_width) / 2
                        y = (screen_height - window_height) / 2 - 200
                        window.move(int(x), int(y))
                        window.refresh()

                elif window["login_button"].get_text() == "Logout":
                    login(logout=True)
                    sess.close()
                    window.close()
                    break

            # Open the One Day Specials Interface
            if event in ["onedays_button", "One Days Specials"]:
                if open_windows["oneday_window"]:
                    continue
                (
                    oneday_window,
                    data,
                    oneday,
                    list_of_onedays,
                    oneday_filtered_results,
                ) = oneday_main()
                open_windows[oneday_window.metadata] = oneday_window.metadata
            # Open the MiniLeague interface
            if event in ["minileague_button", "Mini Leagues"]:
                if open_windows["minileague_window"]:
                    continue
                (
                    minileague_window,
                    data,
                    minileague_filtered_results,
                    specific_mini,
                ) = minileague()
                open_windows[minileague_window.metadata] = minileague_window.metadata

            if event in ["mock_day", "Mock Match day"]:
                if open_windows["mock_day_window"]:
                    continue
                (
                    mock_day_window,
                    match_day,
                    seed,
                    threshold,
                    mock_day_data,
                ) = open_mock_day()
                open_windows[mock_day_window.metadata] = mock_day_window.metadata

            # Open the LL homepage
            if event in ["open_ll", "LearnedLeague.com"]:
                webbrowser.open("https://www.learnedleague.com")

            # Open the Statistics interface
            if event in ["stats_button", "Player Tracker"]:
                if not open_windows["stats_window"]:
                    stats_window = open_stats_window()
                    open_windows[stats_window.metadata] = stats_window.metadata
                stats_window["available_users"].update(
                    values=combo_values, value=user_data.formatted_username
                )

            if event in ["defense_button", "Defense Tactics"]:
                if open_windows["defense_window"]:
                    continue
                defense_window = open_defense_window()
                open_windows[defense_window.metadata] = defense_window.metadata
                defense_window["output_questions"].bind("<ButtonPress-2>", "press")
                defense_window["output_questions"].bind(
                    "<Double-Button-1>", "_double_click"
                )

                defense_window["player_1"].update(
                    values=user_data.opponents,
                    value=user_data.formatted_username,
                )
                defense_window["opponent"].update(
                    values=user_data.opponents,
                    value=user_data.opponents[
                        min(len(user_data.opponents) - 1, current_day)
                    ],
                )

            if event == "analysis_button":
                if open_windows["analysis_window"]:
                    continue
                analysis_window = open_analysis_window()
                open_windows[analysis_window.metadata] = analysis_window.metadata

                analysis_window["season_selection"].update(
                    values=available_seasons,
                    value=latest_season,
                )
                analysis_window["user"].update(
                    values=user_data.opponents,
                    value=user_data.formatted_username,
                )

                player_stats_url = ALL_DATA_BASE_URL.format(latest_season)
                file = (
                    os.path.expanduser("~")
                    + "/.LearnedLeague/"
                    + f"LL{latest_season}_Leaguewide.csv"
                )
                if not os.path.isfile(file):
                    with open(file, "wb+") as out_file:
                        sess = login()
                        content = sess.get(player_stats_url, stream=True).content
                        out_file.write(content)

                raw = pd.read_csv(file, encoding="latin1")
                raw.columns = [x.lower() for x in raw.columns]

                match_day = raw.matchday.iloc[0]

                if match_day < current_day:
                    with open(file, "wb+") as out_file:
                        sess = login()
                        content = sess.get(player_stats_url, stream=True).content
                        out_file.write(content)

                user_stats = DotMap(raw.set_index("player").to_dict(orient="index"))
                df = pd.DataFrame().from_dict(user_stats.toDict(), orient="index")

            # Trigger the right click menu for searching text within a question
            if event == "questionpress":
                question_widget = window["question"].Widget
                selection_ranges = question_widget.tag_ranges(sg.tk.SEL)
                if selection_ranges:
                    window["question"].set_right_click_menu(
                        ["&Right", ["Lookup Selection"]]
                    )
                    selected_text = question_widget.get(*selection_ranges)
                else:
                    window["question"].set_right_click_menu(
                        ["&Right", ["!Lookup Selection"]]
                    )
                    continue

            # Use the Dictionary library to display the definition of the selection in a popup window
            if event == "Lookup Selection":
                if len(selected_text.split()) == 1:
                    # selected text is a single word, so just do a lookup
                    try:
                        definition = PyDictionary().meaning(selected_text)

                        result = (
                            selected_text
                            + "\n"
                            + "\n".join(
                                [
                                    key + ": " + ", ".join(value)
                                    for key, value in definition.items()
                                ]
                            )
                        )
                        print(result)
                        sg.popup_ok(
                            result, title="Dictionary Result", font=("Arial", 16)
                        )
                        continue
                    except Exception:
                        result = "No results available - Try another search."
                else:
                    try:
                        result = wikipedia.summary(
                            selected_text, sentences=2, auto_suggest=True, redirect=True
                        )
                    except Exception:
                        result = "No results available - Try another search."

                    sg.popup_ok(result, title="Wiki Summary", font=("Arial", 16))

            # Filter the questions to a specific season
            if event == "season":
                window.write_event_value("filter", "")
                question_object = update_question(questions, window, i)
                answer = question_object.get("answer")

            # Choose a random question to display
            if event in ("random_choice", "random_key"):
                if (
                    window.find_element_with_focus()
                    and window.find_element_with_focus().Key
                    in (
                        "search_criteria",
                        "answer_submission",
                    )
                ):
                    continue
                i = choice(list(questions.keys()))
                question_object = update_question(questions, window, i)
                answer = question_object.get("answer")
                window["answer_submission"].update(value="", disabled=False)
                window["submit_answer_button"].update(disabled=False)
                window["correct_override"].update(disabled=True)
                if i == len(questions.keys()):
                    window["next"].update(disabled=True)
                else:
                    window["next"].update(disabled=False)
                if i == 1:
                    window["previous"].update(disabled=True)
                else:
                    window["previous"].update(disabled=False)

            # If the category dropdown is changed from ALL, or the filter button is pressed
            # display the new questions
            if event in ["filter", "category_selection"]:
                if int(values["min_%"]) > int(values["max_%"]):
                    values["max_%"] = str(int(values["min_%"]) + 1)
                    window["max_%"].update(value=values["max_%"])

                if int(values["min_%"]) < 0:
                    values["min_%"] = str(0)
                    window["min_%"].update(value=values["max_%"])

                if int(values["max_%"]) > 100 or int(values["min_%"]) > 100:
                    values["min_%"] = str(100)
                    values["max_%"] = str(100)
                    window["min_%"].update(value=values["min_%"])
                    window["max_%"].update(value=values["max_%"])

                questions = filter_questions(
                    all_data,
                    values["min_%"],
                    values["max_%"],
                    values["category_selection"],
                    values["season"],
                    values["search_criteria"],
                )

                if not questions:
                    window["question"].update(value="No Questions Available")

                window["dropdown"].update(values=list(questions.keys()), value=1)
                i = 1

                question_object = update_question(questions, window, i)
                window["previous"].update(disabled=True)
                window["search_criteria"].update(value="")
                window["answer_submission"].update(value="", disabled=False)
                window["submit_answer_button"].update(disabled=False)
                window["correct_override"].update(disabled=True)
                window["filter"].set_focus()

                if len(questions.keys()) == 1:
                    window["next"].update(disabled=True)
                    window["previous"].update(disabled=True)

            # Display or hide the answer for the currently displayed question
            if event in ("show/hide", "show_key"):
                if (
                    window.find_element_with_focus()
                    and window.find_element_with_focus().Key
                    in (
                        "search_criteria",
                        "answer_submission",
                    )
                ):
                    continue

                answer = question_object["answer"]
                if not values["answer_submission"].lower():
                    window["answer_submission"].Widget.configure(
                        readonlybackground="gray"
                    )
                window["answer_submission"].update(disabled=True)
                window["submit_answer_button"].update(disabled=True)
                window["correct_override"].update(disabled=True)

                if window["show/hide"].get_text() == "Show Answer":
                    try:
                        window["show/hide"].update(text="Hide Answer")

                        window["answer"].update(value=answer, font=("Arial", 16))
                    except Exception:
                        continue

                elif window["show/hide"].get_text() == "Hide Answer":
                    window["show/hide"].update(text="Show Answer")
                    try:
                        if answer:
                            window["answer"].update(value="******")
                        else:
                            window["answer"].update(value="")
                    except Exception:
                        continue

            # if the next or previous or a specific question is selected, display that question
            # and its information and hide the answer.
            if event in ["next", "previous", "dropdown", "next_key", "previous_key"]:
                if (
                    window.find_element_with_focus()
                    and window.find_element_with_focus().Key
                    in (
                        "search_criteria",
                        "answer_submission",
                    )
                ):
                    continue

                if event in ("next", "next_key"):
                    if event == "next_key" and i == len(questions.keys()):
                        continue
                    i += 1

                elif event in ("previous", "previous_key"):
                    if event == "previous_key" and i == 1:
                        continue
                    i -= 1

                elif event == "dropdown":
                    i = values["dropdown"]

                question_object = update_question(questions, window, i)
                answer = question_object.get("answer")
                window["answer_submission"].update(value="", disabled=False)
                window["submit_answer_button"].update(disabled=False)
                window["correct_override"].update(disabled=True)

                if not question_object:
                    if event in ("next", "next_key"):
                        i -= 1
                    elif event in ("previous", "previous_key"):
                        i += 1
                    elif event == "dropdown":
                        i = values["dropdown"]
                    continue

                if i == len(questions.keys()):
                    window["next"].update(disabled=True)
                else:
                    window["next"].update(disabled=False)
                if i == 1:
                    window["previous"].update(disabled=True)
                else:
                    window["previous"].update(disabled=False)

            # Check the submitted answer against the correct answer for the specific question
            if "submit_answer_button" in event:
                if not values.get("answer_submission"):
                    continue

                submitted_answer = values["answer_submission"].lower()
                answer = question_object["answer"]
                window["answer"].update(value=answer, font=("Arial", 16))
                window["answer_submission"].update(disabled=True)
                window["submit_answer_button"].update(disabled=True)
                window["show/hide"].update(text="Hide Answer")

                answers = re.findall("([^/,()]+)", answer)
                if len(answers) > 1:
                    correct = [
                        combined_correctness(submitted_answer, answer.strip(), True)
                        for answer in answers
                    ]
                else:
                    correct = [combined_correctness(submitted_answer, answer.strip())]

                if any(correct):
                    right_answer = True
                    window["answer_submission"].Widget.configure(
                        readonlybackground="light green"
                    )

                else:
                    right_answer = False
                    window["answer_submission"].Widget.configure(
                        readonlybackground="red"
                    )

                window["question"].set_focus()
                window["correct_override"].update(disabled=False)

                # track answers in all_data.json
                past_answers = question_object.get("answers") or []
                data_code = (
                    "S" + question_object["season"] + question_object["question_num"]
                )
                answer_dict = {
                    "answer": submitted_answer,
                    "date": datetime.datetime.now().isoformat(),
                    "correct": right_answer,
                    "override": values["correct_override"],
                }
                past_answers.append(answer_dict)
                all_data[data_code]["answers"] = past_answers
                if not os.path.isdir(os.path.expanduser("~") + "/.LearnedLeague"):
                    os.mkdir(os.path.expanduser("~") + "/.LearnedLeague")
                with open(
                    os.path.expanduser("~") + "/.LearnedLeague/all_data.json", "w+"
                ) as fp:
                    json.dump(all_data, fp, sort_keys=True, indent=4)
                correct = []

            # If the checking algorithm is wrong, the check box can be used to overwrite the 'correctness'
            # of the answer being submitted
            if "correct_override" in event:
                if right_answer:
                    right_answer = False
                    window["answer_submission"].Widget.configure(
                        readonlybackground="red"
                    )
                else:
                    right_answer = True
                    window["answer_submission"].Widget.configure(
                        readonlybackground="light green"
                    )

                answer_dict = {
                    "answer": submitted_answer,
                    "date": datetime.datetime.now().isoformat(),
                    "correct": right_answer,
                    "override": values["correct_override"],
                }
                past_answers = question_object.get("answers")
                del past_answers[-1]
                past_answers.append(answer_dict)
                all_data[data_code]["answers"] = past_answers
                if not os.path.isdir(os.path.expanduser("~") + "/.LearnedLeague"):
                    os.mkdir(os.path.expanduser("~") + "/.LearnedLeague")

                with open(
                    os.path.expanduser("~") + "/.LearnedLeague/all_data.json", "w+"
                ) as fp:
                    json.dump(all_data, fp, sort_keys=True, indent=4)

            # if the question number is clicked, open the link
            if event == "question_number":
                webbrowser.open(window["question_number"].metadata)

            # Open the question item in your browser
            if "click_here" in event and window["question"].metadata:
                png_data = get_image_data(window["question"].metadata)
                img_window = sg.Window(
                    title="Image",
                    layout=[[sg.Image(data=png_data)]],
                    finalize=True,
                    modal=False,
                    metadata="img_window",
                )
                open_windows[img_window.metadata] = img_window.metadata

        if window.metadata == "minileague_window":
            if "Escape" in event:
                window["question_1"].set_focus()

            if "press" in event:
                i = int(event.split("_")[-1].split("press")[0])

                question_widget = window[f"question_{i}"].Widget
                selection_ranges = question_widget.tag_ranges(sg.tk.SEL)
                if selection_ranges:
                    window[f"question_{i}"].set_right_click_menu(
                        ["&Right", ["Lookup Selection"]]
                    )
                    selected_text = question_widget.get(*selection_ranges)
                else:
                    window[f"question_{i}"].set_right_click_menu(
                        ["&Right", ["!Lookup Selection"]]
                    )
                    continue

            if event == "Lookup Selection":
                if len(selected_text.split()) == 1:
                    # selected text is a single word, so just do a lookup
                    try:
                        definition = PyDictionary().meaning(selected_text)

                        result = (
                            selected_text
                            + "\n"
                            + "\n".join(
                                [
                                    key + ": " + ", ".join(value)
                                    for key, value in definition.items()
                                ]
                            )
                        )
                        print(result)
                        sg.popup_ok(
                            result, title="Dictionary Result", font=("Arial", 16)
                        )
                        continue
                    except Exception:
                        result = "No results available - Try another search."
                else:
                    try:
                        result = wikipedia.summary(
                            selected_text, sentences=2, auto_suggest=True, redirect=True
                        )
                    except:
                        result = "No results available - Try another search."

                    sg.popup_ok(result, title="Wiki Summary", font=("Arial", 16))

            if event == "random_mini_league":
                specific_mini = get_specific_minileague(
                    data, choice(minileague_filtered_results)
                )
                specific_mini = load_questions(specific_mini, window)

            if event in ("mini_league_selection", "full_reset"):
                if specific_mini.title != values["mini_league_selection"]:
                    window["pbar_spacer"].update(visible=False)
                    window["full_reset"].update(visible=False)
                    window["pbar_status"].update(visible=True)
                    window["pbar"].update(visible=True, current_count=0)
                    window["pbar_spacer"].update(visible=True)
                    window["full_reset"].update(visible=True)
                    window.refresh()
                    specific_mini = get_specific_minileague(
                        data, values["mini_league_selection"]
                    )

                    window["mini_league_title"].update(value=specific_mini.title)
                    window["mini_league_date"].update(value=specific_mini.date)
                    window["mini_league_selection"].update(value=specific_mini.title)
                    window["number_of_players"].update(
                        value=specific_mini.number_of_players
                    )
                    specific_mini = get_mini_data(specific_mini, window)
                    window["percent_correct"].update(
                        value=str(specific_mini.overall_correct) + "%"
                    )

                specific_mini = load_questions(specific_mini, window)

            if "show/hide" in event:
                if window.find_element_with_focus().Key in ("answer_submission"):
                    continue

                i = event.split("_")[-1]

                question_object = q_num_finder(specific_mini.data.match_days, i)
                answer = question_object.answer

                window[f"answer_submission_{i}"].update(disabled=True)
                window[f"submit_answer_button_{i}"].update(disabled=True)
                window[f"correct_override_{i}"].update(disabled=True)
                window[f"question_percent_correct_{i}"].update(
                    value=question_object["%_correct"] + "%", font=DEFAULT_FONT
                )

                if window[f"show/hide_{i}"].get_text() == "Show Answer":
                    try:
                        window[f"show/hide_{i}"].update(text="Hide Answer")

                        window[f"answer_{i}"].update(value=answer, font=("Arial", 16))
                    except:
                        continue

                elif window[f"show/hide_{i}"].get_text() == "Hide Answer":
                    window[f"show/hide_{i}"].update(text="Show Answer")
                    try:
                        if answer:
                            window[f"answer_{i}"].update(value="******")
                        else:
                            window[f"answer_{i}"].update(value="")
                    except:
                        continue

            if "submit_answer_button" in event:
                i = event.split("_")[-1]
                if not values[f"answer_submission_{i}"]:
                    print("it got here")
                    print(event, values.get(f"answer_submission_{i}"))
                    continue

                submitted_answer = values[f"answer_submission_{i}"].lower()
                question_object = q_num_finder(specific_mini.data.match_days, i)
                answer = question_object.answer
                window[f"answer_{i}"].update(value=answer, font=("Arial", 16))
                window[f"answer_submission_{i}"].update(disabled=True)
                window[f"submit_answer_button_{i}"].update(disabled=True)
                window[f"show/hide_{i}"].update(text="Show Answer", disabled=True)
                window[f"question_percent_correct_{i}"].update(
                    value=question_object["%_correct"] + "%", font=DEFAULT_FONT
                )

                answers = re.findall("([^/,()]+)", answer)
                if len(answers) > 1:
                    correct = [
                        combined_correctness(submitted_answer, answer.strip(), True)
                        for answer in answers
                    ]
                else:
                    correct = [combined_correctness(submitted_answer, answer.strip())]

                if any(correct):
                    right_answer = True
                    window[f"answer_submission_{i}"].Widget.configure(
                        readonlybackground="light green"
                    )
                    specific_mini.data.score += 1
                else:
                    right_answer = False
                    window[f"answer_submission_{i}"].Widget.configure(
                        readonlybackground="red"
                    )

                window[f"question_{i}"].set_focus()
                window[f"correct_override_{i}"].update(disabled=False)
                window["score"].update(value=specific_mini.data.score)

            if "correct_override" in event:
                if right_answer:
                    right_answer = False
                    specific_mini.data.score -= 1
                    window[f"answer_submission_{i}"].Widget.configure(
                        readonlybackground="red"
                    )
                else:
                    right_answer = True
                    window[f"answer_submission_{i}"].Widget.configure(
                        readonlybackground="light green"
                    )
                    specific_mini.data.score += 1

                window["score"].update(value=specific_mini.data.score)

        if window.metadata == "mock_day":
            if event == "Submit":
                print([val for key, val in values.items() if "submitted_answer" in key])

                for i, v in enumerate(match_day.questions.values()):
                    window[f"assigned_points_{i}"].update(value=v.assigned_point)
                    window[f"correct_answer_{i}"].update(value=v.answer)
                    window[f"percent_correct_{i}"].update(value=f"{v.percent}%")
                    window[f"submitted_answer_{i}"].update(disabled=True)
                    window["Submit"].update(disabled=True)

            if event == "Show/Hide Answers":
                for i, v in enumerate(match_day.questions.values()):
                    if window[f"correct_answer_{i}"].get():
                        window[f"correct_answer_{i}"].update(value="")
                        window[f"percent_correct_{i}"].update(value="")

                    else:
                        window[f"correct_answer_{i}"].update(value=v.answer)
                        window[f"percent_correct_{i}"].update(value=f"{v.percent}%")

            # Open the question item in your browser
            if "click_here" in event:
                q_id = event.split("click_here")[0]
                if window[q_id].metadata:
                    png_data = get_image_data(window[q_id].metadata)
                    img_window = sg.Window(
                        title="Image",
                        layout=[
                            [
                                sg.Image(
                                    data=png_data,
                                )
                            ],
                        ],
                        finalize=True,
                        modal=False,
                    )

            if "New" in event:
                if values["random_seed"]:
                    seed = randint(0, 999)
                else:
                    seed = None

                match_day = generate_random_day(
                    mock_day_data, seed=seed, threshold=values["perc_threshold"]
                )

                for i, v in enumerate(match_day.questions.values()):
                    window[f"Q{i+1}"].update(value=v._question)
                    window[f"Q{i+1}"].metadata = v.clickable_link
                    window[f"assigned_points_{i}"].update(value="")
                    window[f"correct_answer_{i}"].update(value="")
                    window[f"percent_correct_{i}"].update(value="")
                    window[f"submitted_answer_{i}"].update(disabled=False, value="")
                    window["Submit"].update(disabled=False)
                    widget = window[f"Q{i+1}"].Widget
                    widget.tag_config(
                        "HIGHLIGHT", foreground="blue", font=("Arial", 14, "underline")
                    )
                    text = window[f"Q{i+1}"].get()
                    if "Click here" in text:
                        index = text.index("Click here")
                        indexes = (f"1.{index}", f"1.{index+10}")
                        widget.tag_add("HIGHLIGHT", indexes[0], indexes[1])

        if window.metadata == "oneday_window":
            if "Escape" in event:
                window["question_1"].set_focus()

            if "press" in event:
                i = int(event.split("_")[-1].split("press")[0])

                question_widget = window[f"question_{i}"].Widget
                selection_ranges = question_widget.tag_ranges(sg.tk.SEL)
                if selection_ranges:
                    window[f"question_{i}"].set_right_click_menu(
                        ["&Right", ["Lookup Selection"]]
                    )
                    selected_text = question_widget.get(*selection_ranges)
                else:
                    window[f"question_{i}"].set_right_click_menu(
                        ["&Right", ["!Lookup Selection"]]
                    )
                    continue

            if event == "Lookup Selection":
                if len(selected_text.split()) == 1:
                    # selected text is a single word, so just do a lookup
                    try:
                        definition = PyDictionary().meaning(selected_text)

                        result = (
                            selected_text
                            + "\n"
                            + "\n".join(
                                [
                                    key + ": " + ", ".join(value)
                                    for key, value in definition.items()
                                ]
                            )
                        )
                        print(result)
                        sg.popup_ok(
                            result, title="Dictionary Result", font=("Arial", 16)
                        )
                        continue
                    except:
                        result = "No results available - Try another search."
                else:
                    try:
                        result = wikipedia.summary(
                            selected_text, sentences=2, auto_suggest=True, redirect=True
                        )
                    except:
                        result = "No results available - Try another search."

                    sg.popup_ok(result, title="Wiki Summary", font=("Arial", 16))

            if event == "show_hide_blurb":
                size = window["blurb_frame"].get_size()
                if size[1] == 150:
                    window["blurb_frame"].set_size((300, 1))
                    window["show_hide_blurb"].update(text="Show Description")
                else:
                    window["blurb_frame"].set_size((size[0], 150))
                    window["show_hide_blurb"].update(text="Hide Description")

            if event == "random_oneday":
                oneday = get_oneday_data(
                    get_specific_oneday(
                        list_of_onedays, choice(oneday_filtered_results)
                    )
                )
                data = oneday["data"]
                score = 0
                num_of_money_questions_left = 5
                submitted_answers = {}
                window["oneday_title"].update(value=oneday["title"])
                window["difficulty"].update(value=oneday["difficulty_rating"])
                window["percent_correct"].update(
                    value=str(oneday["overall_average"]) + "%"
                )
                window["blurb_text"].update(value=oneday["blurb"])
                window["oneday_date"].update(value=oneday["date"])
                window["oneday_selection"].update(value=oneday["title"])
                window["90th_percent"].update(value=oneday["90th_percentile"])
                window["50th_percent"].update(value=oneday["50th_percentile"])
                window["10th_percent"].update(value=oneday["10th_percentile"])
                window["number_of_players"].update(value=oneday["number_of_players"])
                window["score"].update(value=score)
                window["num_of_money_questions_left"].update(
                    value=num_of_money_questions_left
                )
                for i in data.keys():
                    question_object = data[i]
                    window[f"question_{i}"].update(value=question_object["_question"])
                    window[f"answer_{i}"].update(value="*******")
                    window[f"money_check_{i}"].update(disabled=False, value=False)
                    window[f"show/hide_{i}"].update(text="Show Answer", disabled=False)
                    window[f"answer_submission_{i}"].update(
                        value="", disabled=False, background_color="white"
                    )
                    window[f"answer_submission_{i}"].bind(
                        "<Return>", f"_submit_answer_button_{i}"
                    )
                    window[f"submit_answer_button_{i}"].update(disabled=False)
                    window[f"question_percent_correct_{i}"].update(
                        value="Submit answer to see", font=("Arial Italic", 10)
                    )

                window.refresh()
                window["questions_column"].contents_changed()

            if event == "oneday_filter_search":
                oneday_filtered_results = search_onedays(
                    list_of_onedays, search_word=values["oneday_search"]
                ) or [""]
                window["oneday_search"].update(value="")
                if not oneday_filtered_results[0]:
                    oneday_filtered_results = search_onedays(list_of_onedays)
                    sg.popup_error(
                        "WARNING - No Results",
                        font=("Arial", 16),
                        auto_close=True,
                        auto_close_duration=5,
                    )
                    continue
                window["oneday_selection"].update(
                    value=oneday_filtered_results[0], values=oneday_filtered_results
                )
                oneday = get_oneday_data(
                    get_specific_oneday(list_of_onedays, oneday_filtered_results[0])
                )
                data = oneday["data"]
                i = 1
                score = 0
                num_of_money_questions_left = 5
                submitted_answers = {}
                window["oneday_title"].update(value=oneday["title"])
                window["difficulty"].update(value=oneday["difficulty_rating"])
                window["percent_correct"].update(
                    value=str(oneday["overall_average"]) + "%"
                )
                window["blurb_text"].update(value=oneday["blurb"])
                window["oneday_date"].update(value=oneday["date"])
                window["oneday_selection"].update(value=oneday["title"])
                window["90th_percent"].update(value=oneday["90th_percentile"])
                window["50th_percent"].update(value=oneday["50th_percentile"])
                window["10th_percent"].update(value=oneday["10th_percentile"])
                window["number_of_players"].update(value=oneday["number_of_players"])
                window["score"].update(value=score)
                window["num_of_money_questions_left"].update(
                    value=num_of_money_questions_left
                )
                for i in data.keys():
                    question_object = data[i]
                    window[f"question_{i}"].update(value=question_object["_question"])
                    window[f"answer_{i}"].update(value="*******")
                    window[f"money_check_{i}"].update(disabled=False, value=False)
                    window[f"show/hide_{i}"].update(text="Show Answer", disabled=False)
                    window[f"answer_submission_{i}"].update(
                        value="", disabled=False, background_color="white"
                    )
                    window[f"answer_submission_{i}"].bind(
                        "<Return>", f"_submit_answer_button_{i}"
                    )
                    window[f"submit_answer_button_{i}"].update(disabled=False)
                    window[f"question_percent_correct_{i}"].update(
                        value="Submit answer to see", font=("Arial Italic", 10)
                    )

                window.refresh()
                window["questions_column"].contents_changed()

            if event in ("oneday_selection", "full_reset"):
                oneday = get_oneday_data(
                    get_specific_oneday(list_of_onedays, values["oneday_selection"])
                )
                data = oneday["data"]
                i = 1
                score = 0
                num_of_money_questions_left = 5
                submitted_answers = {}
                window["oneday_title"].update(value=oneday["title"])
                window["difficulty"].update(value=oneday["difficulty_rating"])
                window["percent_correct"].update(
                    value=str(oneday["overall_average"]) + "%"
                )
                window["blurb_text"].update(value=oneday["blurb"])
                window["oneday_date"].update(value=oneday["date"])
                window["oneday_selection"].update(value=oneday["title"])
                window["90th_percent"].update(value=oneday["90th_percentile"])
                window["50th_percent"].update(value=oneday["50th_percentile"])
                window["10th_percent"].update(value=oneday["10th_percentile"])
                window["number_of_players"].update(value=oneday["number_of_players"])
                window["score"].update(value=score)
                window["num_of_money_questions_left"].update(
                    value=num_of_money_questions_left
                )

                for i in data.keys():
                    question_object = data[i]
                    height = len(wrap(question_object["_question"], 100)) + 1
                    window[f"question_{i}"].update(value=question_object["_question"])

                    window[f"answer_{i}"].update(value="*******")
                    window[f"money_check_{i}"].update(disabled=False, value=False)
                    window[f"show/hide_{i}"].update(text="Show Answer", disabled=False)
                    window[f"answer_submission_{i}"].update(
                        value="", disabled=False, background_color="white"
                    )
                    window[f"answer_submission_{i}"].bind(
                        "<Return>", f"_submit_answer_button_{i}"
                    )
                    window[f"submit_answer_button_{i}"].update(disabled=False)
                    window[f"question_percent_correct_{i}"].update(
                        value="Submit answer to see", font=("Arial Italic", 10)
                    )

                window.refresh()
                window["questions_column"].contents_changed()

            if "show/hide" in event:
                if window.find_element_with_focus().Key in (
                    "oneday_search",
                    "answer_submission",
                ):
                    continue

                i = event.split("_")[-1]
                question_object = data[i]
                answer = question_object["answer"]

                if not values[f"answer_submission_{i}"]:
                    confirm, _ = sg.Window(
                        "Confirm",
                        element_justification="c",
                        layout=[
                            [
                                sg.Text(
                                    "You have not submitted an answer.",
                                    font=("Arial", 14),
                                )
                            ],
                            [
                                sg.Text(
                                    "Do you want to continue? (and forfeit your guess)",
                                    font=("Arial", 14),
                                )
                            ],
                            [
                                sg.Yes(s=12),
                                sg.No(s=12),
                            ],
                        ],
                        disable_close=False,
                        force_toplevel=True,
                    ).read(close=True)

                if confirm == "Yes":
                    window[f"answer_submission_{i}"].update(disabled=True)
                    window[f"submit_answer_button_{i}"].update(disabled=True)
                    window[f"money_check_{i}"].update(disabled=True)
                    window[f"show/hide_{i}"].update(disabled=True)
                    window[f"question_percent_correct_{i}"].update(
                        value=question_object["percent"], font=DEFAULT_FONT
                    )
                    submitted_answers[question_object["question_num"]] = {
                        "correct_answer": answer,
                        "submitted_answer": "NONE",
                        "money_question": False,
                        "correct": False,
                    }
                    oneday["data"][question_object["question_num"]][
                        "submitted_answer"
                    ] = {
                        "submitted_answer": "NONE",
                        "money_question": False,
                        "correct": False,
                        "override": False,
                    }
                else:
                    continue

                if window[f"show/hide_{i}"].get_text() == "Show Answer":
                    try:
                        window[f"show/hide_{i}"].update(text="Hide Answer")

                        window[f"answer_{i}"].update(value=answer, font=("Arial", 16))
                    except:
                        continue

                elif window[f"show/hide_{i}"].get_text() == "Hide Answer":
                    window[f"show/hide_{i}"].update(text="Show Answer")
                    try:
                        if answer:
                            window[f"answer_{i}"].update(value="*******")
                        else:
                            window[f"answer_{i}"].update(value="")
                    except:
                        continue

            if "correct_override" in event:
                i = event.split("_")[-1]
                question_object = data[i]
                submitted_answer = submitted_answers[question_object["question_num"]]
                if submitted_answer["correct"]:
                    score -= 15
                    if submitted_answer["money_question"]:
                        wrong_percent = 100 - question_object["percent"]
                        score -= wrong_percent
                    submitted_answers[question_object["question_num"]][
                        "correct"
                    ] = False
                    oneday["data"][question_object["question_num"]]["submitted_answer"][
                        "correct"
                    ] = False
                    oneday["data"][question_object["question_num"]]["submitted_answer"][
                        "override"
                    ] = values[f"correct_override_{i}"]
                    window[f"answer_submission_{i}"].Widget.configure(
                        readonlybackground="red"
                    )
                else:
                    window[f"answer_submission_{i}"].Widget.configure(
                        readonlybackground="light green"
                    )
                    score += 15

                    if values[f"money_check_{i}"]:
                        wrong_percent = 100 - question_object["percent"]
                        score += wrong_percent
                    submitted_answers[question_object["question_num"]]["correct"] = True
                    oneday["data"][question_object["question_num"]]["submitted_answer"][
                        "correct"
                    ] = True
                    oneday["data"][question_object["question_num"]]["submitted_answer"][
                        "override"
                    ] = values[f"correct_override_{i}"]

                window["score"].update(value=score)
                if len(submitted_answers) == 12:
                    percentile_info = oneday["all_percentile"]
                    final_percentile = list(percentile_info.keys())[
                        list(percentile_info.values()).index(
                            min(
                                list(percentile_info.values()),
                                key=lambda x: abs(int(x) - score),
                            )
                        )
                    ]
                    if not os.path.isdir(
                        os.path.expanduser("~") + "/.LearnedLeague/onedays/"
                    ):
                        os.mkdir(os.path.expanduser("~") + "/.LearnedLeague/onedays")

                    with open(
                        os.path.expanduser("~")
                        + f"/.LearnedLeague/onedays/{re.sub(' ','_', oneday['title'])}"
                        + ".json",
                        "w",
                    ) as fp:
                        json.dump(oneday, fp, sort_keys=True, indent=4)

            if "submit_answer_button" in event:
                i = event.split("_")[-1]
                question_object = data[i]

                if not values[f"answer_submission_{i}"]:
                    continue

                submitted_answer = values[f"answer_submission_{i}"].lower()
                answer = question_object["answer"]
                window[f"answer_{i}"].update(value=answer, font=("Arial", 16))
                window[f"question_percent_correct_{i}"].update(
                    value=question_object["percent"], font=DEFAULT_FONT
                )

                answers = re.findall("([^/,()]+)", answer)
                if len(answers) > 1:
                    correct = [
                        combined_correctness(submitted_answer, answer.strip(), True)
                        for answer in answers
                    ]
                else:
                    correct = [combined_correctness(submitted_answer, answer.strip())]

                if any(correct):
                    window[f"answer_submission_{i}"].Widget.configure(
                        readonlybackground="light green"
                    )
                    score += 15

                    if values[f"money_check_{i}"]:
                        wrong_percent = 100 - question_object["percent"]
                        score += wrong_percent
                else:
                    window[f"answer_submission_{i}"].Widget.configure(
                        readonlybackground="red"
                    )

                if values[f"money_check_{i}"]:
                    num_of_money_questions_left -= 1
                    window["num_of_money_questions_left"].update(
                        value=num_of_money_questions_left
                    )

                window["score"].update(value=score)
                window[f"answer_submission_{i}"].unbind("<Return>")
                window[f"answer_submission_{i}"].update(disabled=True)
                window[f"submit_answer_button_{i}"].update(disabled=True)
                window[f"money_check_{i}"].update(disabled=True)
                window[f"correct_override_{i}"].update(disabled=False)
                window[f"show/hide_{i}"].update(disabled=True)

                submitted_answers[question_object["question_num"]] = {
                    "correct_answer": answer,
                    "submitted_answer": submitted_answer,
                    "money_question": values[f"money_check_{i}"],
                    "correct": any(correct),
                }
                oneday["data"][question_object["question_num"]]["submitted_answer"] = {
                    "submitted_answer": submitted_answer,
                    "money_question": values[f"money_check_{i}"],
                    "correct": any(correct),
                    "override": values[f"correct_override_{i}"],
                }

                window[f"question_{i}"].set_focus()

                if num_of_money_questions_left == 0:
                    [
                        window[f"money_check_{i}"].update(disabled=True)
                        for i in range(1, 13)
                    ]

                if len(submitted_answers) == 12:
                    percentile_info = oneday["all_percentile"]
                    if not percentile_info:
                        final_percentile = "NONE"
                    else:
                        final_percentile = list(percentile_info.keys())[
                            list(percentile_info.values()).index(
                                min(
                                    list(percentile_info.values()),
                                    key=lambda x: abs(int(x) - score),
                                )
                            )
                        ]

                    sg.popup_ok(
                        f"Final Score: {score} pts\nFinal percentile: {final_percentile}%",
                        title="Final Score",
                        font=DEFAULT_FONT,
                    )
                    oneday["submission_date"] = (datetime.datetime.now().isoformat(),)

                    if not os.path.isdir(
                        os.path.expanduser("~") + "/.LearnedLeague/onedays/"
                    ):
                        os.mkdir(os.path.expanduser("~") + "/.LearnedLeague/onedays/")

                    with open(
                        os.path.expanduser("~")
                        + f"/.LearnedLeague/onedays/{re.sub(' ','_', oneday['title'])}"
                        + ".json",
                        "w",
                    ) as fp:
                        json.dump(oneday, fp, sort_keys=True, indent=4)

            if event == "difficulty_tooltip":
                webbrowser.open(window["difficulty_tooltip"].metadata)

        if window.metadata == "stats_window":
            # clicking in the table provides different events
            if "+CLICKED+" in event:
                # print(event[-1])
                row, column = event[-1]

                if row is None:
                    continue

                if row == -1:
                    if not window["stats_table"].get():
                        continue

                    table_values, reverse = sort(
                        window["stats_table"].get(), column, not reverse
                    )
                    current_season = window["stats_table"].get()[0][1]
                    remove_all_rows(window)
                    window["stats_table"].update(values=table_values)

                    continue

                if window["stats_table"].get():
                    if column == 0:
                        username = window["stats_table"].get()[row][column]
                        clicked_user = load(username, sess=sess)
                        url = BASE_URL + f"/profiles.php?{clicked_user.profile_id}"
                        webbrowser.open(url)

                    if window["stats_table"].get()[row][column] == "X":
                        username = window["stats_table"].get()[row][0]
                        del window["stats_table"].metadata[username]
                        table_values = remove_stats_row(window, row)

            # Clear the stats table complete
            if event == "clear_all_stats":
                remove_all_rows(window)

            # Load all available players (opponents + past searched players)
            if event == "load_all":
                for user in combo_values:
                    if window["stats_table"].metadata:
                        if user in window["stats_table"].metadata.keys():
                            user = window["stats_table"].metadata[username]
                        else:
                            searched_user_data = load(user, sess=sess)
                    else:
                        searched_user_data = load(user, sess=sess)
                    table_values = add_stats_row(searched_user_data, window)
                    window.refresh()

            # load favorites into stats window
            if event == "load_favorites":
                fav_file = os.path.expanduser("~") + "/.LearnedLeague/favorites.json"
                if not os.path.isfile(fav_file):
                    with open(fav_file, "w") as fp:
                        json.dump(["FahmyG"], fp, indent=4)

                with open(fav_file, "r") as fp:
                    favorites = json.load(fp)
                    for user in favorites:
                        if window["stats_table"].metadata:
                            if user in window["stats_table"].metadata.keys():
                                user = window["stats_table"].metadata[username]
                            else:
                                searched_user_data = load(user, sess=sess)
                        else:
                            searched_user_data = load(user, sess=sess)
                        table_values = add_stats_row(searched_user_data, window)
                        window.refresh()

            # Switch between all-time stats and current (or latest) season
            if "latest_season_switch" in event:
                if not window["stats_table"].get():
                    continue

                table_values = window["stats_table"].get()
                current_season = window["stats_table"].get()[0][1]

                if current_season == "Total":
                    current_season = "current_season"
                    window["latest_season_switch"].update(text="Total")
                else:
                    current_season = "total"
                    window["latest_season_switch"].update(text="Latest Season")

                remove_all_rows(window)
                for username in window["stats_table"].metadata.keys():
                    clicked_user = window["stats_table"].metadata[username]

                    table_values = add_stats_row(
                        clicked_user, window, season=current_season
                    )

            # Search for players via their username and return their stats (and save their data)
            if (
                event in ["player_search_button", "return_key"]
                and values["player_search"]
            ):
                if not logged_in:
                    continue
                max_stats = len(
                    [
                        key
                        for key in list(window.AllKeysDict.keys())
                        if "row_name_" in str(key)
                    ]
                )
                if f"row_name_{values['player_search']}" in window.AllKeysDict:
                    window["player_search"].update(value="")
                    continue

                searched_user_data = load(window["player_search"].get(), sess=sess)
                if (
                    searched_user_data.formatted_username
                    not in window["available_users"].get()
                ):
                    combo_values.append(searched_user_data.formatted_username)
                    combo_values = sorted(list(set(combo_values)))
                    window["available_users"].update(
                        values=combo_values, value=searched_user_data.formatted_username
                    )

                if max_stats >= 3:
                    continue

                if not searched_user_data.get("stats"):
                    window["player_search"].update(value="")
                    sg.popup_auto_close(
                        "Player Not Found.", no_titlebar=True, modal=False
                    )
                    window["player_search"].set_focus()
                    continue

                window["player_search"].update(value="")
                add_stats_row(searched_user_data, window)
                # window.move_to_center()

            # Select a user from the dropdown and display their stats
            if event == "available_users":
                if not logged_in:
                    continue

                searched_user_data = load(window["available_users"].get(), sess=sess)
                table_values = add_stats_row(searched_user_data, window)
                # window.move_to_center()

            # Display the selected users category metrics. Depending on which button is pressed
            # the appropriate user will be displayed
            if "category_button" in event or event == "Category Metrics":
                if not logged_in:
                    continue
                if values["stats_table"]:
                    row = values["stats_table"][0]
                    opponent = table_values[row][0]
                else:
                    opponent = window["available_users"].get()
                display_category_metrics(load(opponent, sess=sess))

        if window.metadata == "defense_window":
            # Submit the category selections and compare against the opponent's metrics for
            # suggested point assignment
            if event == "submit_defense":
                if not logged_in:
                    continue

                if "player_1" not in locals():
                    player_1 = load(values.get("player_1"), sess=sess)
                else:
                    if values.get("player_1").lower() != player_1.username:
                        player_1 = load(values.get("player_1"), sess=sess)
                if "player_2" not in locals():
                    player_2 = load(values.get("opponent"), sess=sess)
                else:
                    if values.get("opponent").lower() != player_2.username:
                        player_2 = load(values.get("opponent"), sess=sess)

                if not player_1.profile_id.isnumeric():
                    sg.popup_auto_close(
                        "Player Not Found.", no_titlebar=True, modal=False
                    )
                    continue

                if not player_2.profile_id.isnumeric():
                    sg.popup_auto_close(
                        "Player Not Found.", no_titlebar=True, modal=False
                    )
                    continue

                question_categories = [
                    values.get(key) for key in values.keys() if "strat" in key
                ]

                if not all(question_categories):
                    continue

                raw_scores = [3, 2, 2, 1, 1, 0]
                percents = DotMap(
                    {
                        f"question_{i+1}": {
                            "percent": (
                                player_2.category_metrics.get(key).percent
                                if player_2.category_metrics.get(key)
                                else 0
                            )
                        }
                        for i, key in enumerate(question_categories)
                    }
                )
                sorted_percents = sorted(
                    percents.keys(),
                    key=lambda x: (percents[x]["percent"]),
                    reverse=False,
                )
                for i, key in enumerate(sorted_percents):
                    percents[key]["score"] = raw_scores[i]

                [
                    window[f"defense_suggestion_{i+1}"].update(
                        value=percents[key].score
                    )
                    for i, key in enumerate(list(percents.keys()))
                ]
                [
                    window[f"suggestion_percent_{i+1}"].update(
                        value=f"{percents[key].percent*100:0.1f}%"
                    )
                    for i, key in enumerate(list(percents.keys()))
                ]

            # Clear the categories and points from the window
            if event == "defense_clear":
                [
                    window[f"defense_suggestion_{i}"].update(value="")
                    for i in range(1, 7)
                ]
                [
                    window[f"suggestion_percent_{i}"].update(value="")
                    for i in range(1, 7)
                ]
                [window[f"defense_strat_{i}"].update(value="") for i in range(1, 7)]

            # Open a popup window to display the current match day's questions
            if event == "todays_questions":
                if open_windows["todays_question_window"]:
                    continue

                question_window = display_todays_questions(
                    latest_season,
                    min(len(user_data.opponents) - 1, current_day) + 1,
                    values["display_todays_answers"],
                )
                open_windows[question_window.metadata] = question_window.metadata
                if question_window.metadata == "continue":
                    continue

                screen_width, _ = window.GetScreenDimensions()
                _, q_current_loc_y = question_window.current_location()
                _, d_current_loc_y = window.current_location()

                q_window_width, _ = question_window.size

                q_new_loc_x = (screen_width / 2) - q_window_width - 10
                d_new_loc_x = (screen_width / 2) + 10

                window.move(int(d_new_loc_x), int(d_current_loc_y))
                question_window.move(int(q_new_loc_x), int(q_current_loc_y))

            # Search through the opponents quesiton history for key words and display
            # whether they got the question right or wrong
            if event == "search_questions_button":
                if not logged_in:
                    continue

                if "player_1" not in locals():
                    player_1 = load(values.get("player_1"), sess=sess)
                else:
                    if values.get("player_1").lower() != player_1.username:
                        player_1 = load(values.get("player_1"), sess=sess)

                if "player_2" not in locals():
                    player_2 = load(values.get("opponent"), sess=sess)
                else:
                    if values.get("opponent").lower() != player_2.username:
                        player_2 = load(values.get("opponent"), sess=sess)

                if not player_1.profile_id.isnumeric():
                    sg.popup_auto_close(
                        "Player Not Found.", no_titlebar=True, modal=False
                    )
                    continue

                if not player_2.profile_id.isnumeric():
                    sg.popup_auto_close(
                        "Player Not Found.", no_titlebar=True, modal=False
                    )
                    continue

                search_term = values["defense_question_search_term"]
                filtered_dict = DotMap(
                    {
                        k: v
                        for k, v in player_2.question_history.iteritems()
                        if search_term.lower() in v.question.lower()
                    }
                )
                total_filtered_questions = len(list(filtered_dict.keys()))
                total_filtered_correct = len(
                    [key for key, value in filtered_dict.items() if value.correct]
                )
                # filtered_dict.pprint(pformat="json")
                result = "\n".join(
                    [
                        f"{key} - {filtered_dict[key].question_category}"
                        + f" - : {'Correct' if filtered_dict[key].correct else 'Incorrect'}"
                        for key in sorted(list(filtered_dict.keys()), reverse=True)
                    ]
                )
                window["filtered_metrics"].update(
                    value=f"Total Correct: {total_filtered_correct}/{total_filtered_questions}"
                )
                window["output_questions"].update(value=result)

            # Clicking a question number in the history box can open the question
            if (
                event == "output_questionspress"
                or event == "output_questions_double_click"
            ):
                if open_windows["single_quesiton_window"]:
                    continue
                history_widget = window["output_questions"].Widget
                history_selection_ranges = history_widget.tag_ranges(sg.tk.SEL)
                if history_selection_ranges:
                    pattern = "S([0-9]+)D([0-9]+)Q([1-6])"
                    selected_text = history_widget.get(*history_selection_ranges)
                    selected_text = [
                        val.split(" - ")[0] for val in selected_text.split("\n")
                    ]
                    for val in selected_text:
                        match = re.match(pattern, val)
                        if match:
                            if event == "output_questionspress":
                                window["output_questions"].set_right_click_menu(
                                    ["&Right", ["Open Question", "Open Multiple"]]
                                )
                            elif event == "output_questions_double_click":
                                season, day, question_num = match.groups()
                                qd = get_specific_question(
                                    all_data, season, day, question_num
                                )
                                single_question_window = open_single_question(qd)
                                # open_windows["single_quesiton_window"] = (
                                #     single_question_window.metadata
                                # )
                else:
                    window["output_questions"].set_right_click_menu(
                        ["&Right", ["!Open Question", "!Open Multiple"]]
                    )
                    continue

            if event == "Open Multiple":
                pattern = "S([0-9]+)D([0-9]+)Q([1-6])"
                i = 0
                j = 0
                for val in selected_text:
                    match = re.match(pattern, val)
                    if j == 6 and i == 2:
                        continue
                    if match:
                        size = int(screen_width / 3) - 50, int(screen_height / 6) - 50
                        location = (80 + i * (size[0] + 30), 80 + j * (size[1] + 30))
                        season, day, question_num = match.groups()
                        qd = get_specific_question(all_data, season, day, question_num)
                        single_question_window = open_single_question(
                            qd,
                            location,
                            size,
                        )
                        i += 1
                        if i == 3:
                            j += 1
                            i = 0

            # Open the question link in a web browser
            if event == "Open Question":
                pattern = "S([0-9]+)D([0-9]+)Q([1-6])"
                match = re.match(pattern, selected_text[0])
                if match:
                    season, day, question_num = match.groups()
                    url = f"https://www.learnedleague.com/question.php?{season}&{day}&{question_num}"
                    webbrowser.open(url)

            # Calculate the HUN similarity between the two players (player 1 and opponent)
            if event in ["calc_hun", "Calculate HUN"]:
                if not logged_in:
                    continue

                if "player_1" not in locals():
                    player_1 = load(values.get("player_1"), sess=sess)
                else:
                    if values.get("player_1").lower() != player_1.username:
                        player_1 = load(values.get("player_1"), sess=sess)
                if "player_2" not in locals():
                    player_2 = load(values.get("opponent"), sess=sess)
                else:
                    if values.get("opponent").lower() != player_2.username:
                        player_2 = load(values.get("opponent"), sess=sess)

                if not player_1.profile_id.isnumeric():
                    sg.popup_auto_close(
                        "Player Not Found.", no_titlebar=True, modal=False
                    )
                    continue

                if not player_2.profile_id.isnumeric():
                    sg.popup_auto_close(
                        "Player Not Found.", no_titlebar=True, modal=False
                    )
                    continue

                player_1.calc_hun(player_2)

                hun_score = player_1.hun.get(player_2.username)

                window["hun_score"].update(value=round(hun_score, 3))

            # Open a plotly web chart showing the similarity in metrics between the two players
            if event in ["similarity_chart", "Show Similarity"]:
                if not logged_in:
                    continue

                if "player_1" not in locals():
                    player_1 = load(values.get("player_1"), sess=sess)
                else:
                    if values.get("player_1").lower() != player_1.username:
                        player_1 = load(values.get("player_1"), sess=sess)
                if "player_2" not in locals():
                    player_2 = load(values.get("opponent"), sess=sess)
                else:
                    if values.get("opponent").lower() != player_2.username:
                        player_2 = load(values.get("opponent"), sess=sess)

                if not player_1.profile_id.isnumeric():
                    sg.popup_auto_close(
                        "Player Not Found.", no_titlebar=True, modal=False
                    )
                    continue

                if not player_2.profile_id.isnumeric():
                    sg.popup_auto_close(
                        "Player Not Found.", no_titlebar=True, modal=False
                    )
                    continue

                if open_windows["similarity_chart_window"]:
                    continue

                plot_window = radar_similarity(player_1, player_2)
                open_windows[plot_window.metadata] = plot_window.metadata

                screen_width, _ = window.GetScreenDimensions()
                _, q_current_loc_y = plot_window.current_location()
                _, d_current_loc_y = window.current_location()

                q_window_width, _ = plot_window.size

                q_new_loc_x = (screen_width / 2) - q_window_width + 160
                d_new_loc_x = (screen_width / 2) + 180

                window.move(int(d_new_loc_x), int(d_current_loc_y))
                plot_window.move(int(q_new_loc_x), int(q_current_loc_y))

            # Show the selected opponent's category metrics
            if "category_button" in event or event == "Category Metrics":
                if not logged_in:
                    continue
                opponent = window["opponent"].get()
                if open_windows["category_metrics_window"]:
                    continue

                cat_metrics = display_category_metrics(load(opponent, sess=sess))
                open_windows[cat_metrics.metadata] = cat_metrics.metadata

        if window.metadata == "analysis_window":
            if event == "season_selection":
                player_stats_url = ALL_DATA_BASE_URL.format(values["season_selection"])
                file = (
                    os.path.expanduser("~")
                    + "/.LearnedLeague/"
                    + f"LL{values['season_selection']}_Leaguewide.csv"
                )
                if not os.path.isfile(file):
                    with open(file, "wb+") as out_file:
                        sess = login()
                        content = sess.get(player_stats_url, stream=True).content
                        out_file.write(content)

                raw = pd.read_csv(file, encoding="latin1", low_memory=False)
                raw.columns = [x.lower() for x in raw.columns]

                match_day = raw.matchday.iloc[0]

                if match_day < current_day:
                    with open(file, "wb+") as out_file:
                        sess = login()
                        content = sess.get(player_stats_url, stream=True).content
                        out_file.write(content)

                user_stats = DotMap(raw.set_index("player").to_dict(orient="index"))
                df = pd.DataFrame().from_dict(user_stats.toDict(), orient="index")

            if event == "overall_filter_button":
                filtered_user_stats = stats_filter(
                    values["field"],
                    values["overall_field_value"],
                    operator=values["operator"],
                    user_stats=user_stats,
                )
                print(len(filtered_user_stats))

            if event == "user_filter_button":

                def is_float(string):
                    try:
                        float(string)
                        return True
                    except ValueError:
                        return False

                user_field_val = (
                    float(values["user_field_value"])
                    if is_float(values["user_field_value"])
                    else None
                )
                if not (0 < user_field_val <= 1):
                    continue

                if not user_field_val and values["mode"] == "quant":
                    continue

                res = calc_pct(
                    values["user"],
                    values["user_field"],
                    user_stats,
                    df,
                    value=user_field_val,
                    mode=values["mode"],
                )
                print(res)
