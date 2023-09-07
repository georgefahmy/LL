import base64
import datetime
import json
import os
import re
import sys
import webbrowser
from random import choice

import PySimpleGUI as sg
import requests
import wikipedia
from bs4 import BeautifulSoup as bs
from bs4 import SoupStrainer as ss
from dotmap import DotMap
from plotly.graph_objects import Figure, Scatterpolar
from PyDictionary import PyDictionary

from answer_correctness import combined_correctness
from check_for_updates import check_for_update
from layout import layout
from logged_in_tools import (
    DEFAULT_FONT,
    STATS_DEFINITION,
    calc_hun_score,
    display_category_metrics,
    get_question_history,
    get_user_stats,
    load_user_data,
    login,
)
from minileagues import minileague
from onedays import oneday_main

BASE_URL = "https://www.learnedleague.com"

WD = os.getcwd()
USER_DATA_DIR = os.path.expanduser("~") + "/.LearnedLeague/user_data/"

restart = check_for_update()
if restart:
    restart = False
    os.execv(sys.executable, ["python"] + sys.argv)


def get_new_data(season_number):
    """Get the latest data from the season number provided

    Args:
        season_number (int): Season number

    Returns:
        all_data: Data structure of all questions and answers (and metrics)
    """
    try:
        with open(os.path.expanduser("~") + "/.LearnedLeague/all_data.json", "r") as fp:
            all_data = json.load(fp)
    except Exception:
        all_data = {}

    url = BASE_URL + "/match.php?" + str(season_number)
    for i in range(1, 26):
        question_url = url + "&" + str(i)
        page = bs(requests.get(question_url).content, "html.parser")

        if not page.find_all("tr"):
            continue

        categories = [
            link.text.strip().split("-")[0].split(".")[-1].strip()
            for link in page.find_all("div", {"class": "ind-Q20 dont-break-out"})
        ]

        percentages = [
            cell.text
            for cell in page.find_all("tr")[-2].find_all("td", {"class": "ind-Q3"})
        ][2:-1]

        question_defense = [
            cell.text
            for cell in page.find_all("tr")[-1].find_all("td", {"class": "ind-Q3"})
        ][2:-1]

        question_clickable_links = [
            clickable_link.find_all("a")
            for clickable_link in [
                link
                for link in page.find_all("div", {"class": "ind-Q20 dont-break-out"})
                if not link.span.clear()
            ]
        ]

        questions = [
            "-".join(link.text.strip().split("-")[1:]).strip()
            for link in page.find_all("div", {"class": "ind-Q20 dont-break-out"})
        ]
        answers = [
            link.text.strip() for link in page.find_all("div", {"class": "a-red"})
        ]
        date = page.find_all("h1", {"class": "matchday"})[0].text.strip().split(":")[0]

        rundles = [
            row.find_all("td", {"class": "ind-Q3"}) for row in page.find_all("tr")[1:8]
        ]

        for j, question in enumerate(questions):
            question_num_code = "D" + str(i).zfill(2) + "Q" + str(j + 1)
            combined_season_num_code = "S" + season_number + question_num_code
            question_url = (
                BASE_URL
                + "/question.php?"
                + str(season_number)
                + "&"
                + str(i)
                + "&"
                + str(j + 1)
            )

            if len(question_clickable_links[j]) == 1:
                clickable_link = question_clickable_links[j][0].get("href")
                clickable_link = BASE_URL + str(clickable_link)
            else:
                clickable_link = ""

            answer = answers[j]

            all_data[combined_season_num_code] = {
                "_question": question,
                "answer": answer,
                "season": season_number,
                "date": date,
                "category": categories[j],
                "percent": percentages[j],
                "question_num": question_num_code,
                "defense": question_defense[j],
                "url": question_url,
                "clickable_link": str(clickable_link),
                "A": [cell.text for cell in rundles[0]][2:-1][j],
                "B": [cell.text for cell in rundles[1]][2:-1][j],
                "C": [cell.text for cell in rundles[2]][2:-1][j],
                "D": [cell.text for cell in rundles[3]][2:-1][j],
                "E": [cell.text for cell in rundles[4]][2:-1][j],
                "R": [cell.text for cell in rundles[5]][2:-1][j],
            }

    with open(os.path.expanduser("~") + "/.LearnedLeague/all_data.json", "w+") as fp:
        json.dump(all_data, fp, sort_keys=True, indent=4)

    return all_data


def filter_questions(
    all_data,
    min_threshold,
    max_threshold,
    category_filter,
    season_filter,
    search_criteria=None,
):
    """_summary_

    Args:
        all_data (dict): Unfiltered full data dictionary
        min_threshold (int): Minimum % correct
        max_threshold (int): Maximum % correct
        category_filter (str): Limit questions to specific category
        season_filter (str): Limit questions to specific season
        search_criteria (str, optional): Keyword to search for in the questions. Defaults to None.

    Returns:
        final_filtered_questions_dict: dictionary of the filtered questions
    """
    min_threshold = int(min_threshold)
    max_threshold = int(max_threshold)

    if max_threshold <= min_threshold:
        max_threshold = min_threshold + 5

    if category_filter == "ALL":
        filtered_questions_dict = {
            question_ids: question
            for question_ids, question in all_data.items()
            if int(question["percent"]) >= min_threshold
            and int(question["percent"]) < max_threshold
        }
    else:
        filtered_questions_dict = {
            question_ids: question
            for question_ids, question in all_data.items()
            if int(question["percent"]) >= min_threshold
            and int(question["percent"]) < max_threshold
            and question["category"].upper() == category_filter.upper()
        }

    if season_filter != "ALL":
        filtered_questions_dict = {
            question_ids: question
            for question_ids, question in filtered_questions_dict.items()
            if question["season"] == season_filter
        }

    if search_criteria:
        filtered_questions_dict = {
            question_ids: question
            for question_ids, question in filtered_questions_dict.items()
            if search_criteria.lower() in question["_question"].lower()
        }

    final_filtered_questions_dict = {
        i + 1: val
        for i, val in enumerate(
            [filtered_questions_dict[key] for key in filtered_questions_dict.keys()]
        )
    }

    return final_filtered_questions_dict


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
    if question_object.get("clickable_link"):
        window["question"].set_tooltip(
            "Click to Open: " + question_object.get("clickable_link")
        )
        window["question"].TooltipObject.timeout = 10
    else:
        window["question"].set_tooltip("")
        window["question"].TooltipObject.timeout = 1000000
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
    window.refresh()

    return question_object


def add_stats_row(user_data, logged_in_user):
    hun_score = user_data.hun.get(logged_in_user) or 1
    row = sg.Frame(
        title="",
        layout=[
            [
                sg.Column(
                    layout=[
                        [
                            sg.Text(
                                user_data.username,
                                font=("Arial Bold", 14),
                                justification="c",
                                expand_x=True,
                            ),
                            sg.Text(expand_x=True),
                            sg.Text(
                                round(hun_score, 3),
                                font=DEFAULT_FONT,
                                justification="c",
                                expand_x=True,
                            ),
                        ],
                    ],
                    expand_x=True,
                    size=(150, 30),
                ),
                sg.Column(
                    layout=[
                        [
                            # Overall Stats across all seasons
                            sg.Text(
                                user_data.stats.total.get(key),
                                font=DEFAULT_FONT,
                                size=(5, 1),
                                justification="c",
                                tooltip=STATS_DEFINITION.get(key),
                            )
                            for key in list(user_data.stats.total.keys())
                            if key not in ["Rundle"]
                        ],
                        [sg.HorizontalSeparator()],
                        [
                            # Current Season stats
                            sg.Text(
                                user_data.stats.current_season.get(key),
                                font=DEFAULT_FONT,
                                size=(5, 1),
                                justification="c",
                                tooltip=STATS_DEFINITION.get(key),
                            )
                            for key in list(user_data.stats.current_season.keys())
                            if key not in ["Rundle"]
                        ],
                    ]
                ),
                sg.Column(
                    layout=[
                        [
                            sg.Button(
                                "Remove",
                                key=f"remove_{user_data.username}",
                            )
                        ]
                    ]
                ),
            ],
        ],
        key=f"row_name_{user_data.username}",
    )
    return [[row]]


try:
    latest_season = (
        bs(
            requests.get("https://www.learnedleague.com/allrundles.php").content,
            "html.parser",
            parse_only=ss("h1"),
        )
        .text.split(":")[0]
        .split("LL")[-1]
    )
except Exception:
    latest_season = 98

available_seasons = [
    str(season) for season in list(range(60, int(latest_season) + 1, 1))
]


datapath = os.path.expanduser("~") + "/.LearnedLeague/all_data.json"
if os.path.isfile(datapath):
    with open(datapath, "r") as fp:
        all_data = json.load(fp)
else:
    all_data = {}

season_in_data = sorted(
    list(set([val.split("D")[0].strip("S") for val in list(all_data.keys())]))
)
missing_seasons = sorted(
    list(set(available_seasons).symmetric_difference(set(season_in_data)))
)

current_day = int(
    bs(
        requests.get("https://www.learnedleague.com/allrundles.php").content,
        "html.parser",
        parse_only=ss("h3"),
    ).h3.text.split()[-1]
)

total_players = sum(
    [
        int(row.find_all("td")[1].text)
        for row in (
            bs(
                requests.get("https://www.learnedleague.com/allrundles.php").content,
                "html.parser",
                parse_only=ss("table"),
            )
            .find_all("table")[2]
            .find_all("tr")[1:]
        )
    ]
)

for season in available_seasons:
    season_questions = 0
    for key in all_data.keys():
        if season in key:
            season_questions += 1
    if season_questions < (current_day * 6) and True:
        missing_seasons += [season]

if len(missing_seasons) > 0:
    icon_file = WD + "/resources/ll_app_logo.png"
    sg.set_options(icon=base64.b64encode(open(str(icon_file), "rb").read()))
    max_length = len(missing_seasons)
    loading_window = sg.Window(
        "Loading New Seasons",
        [
            [
                sg.ProgressBar(
                    max_length,
                    orientation="h",
                    expand_x=True,
                    size=(20, 20),
                    key="-PBAR-",
                )
            ],
            [
                sg.Text(
                    "",
                    key="-OUT-",
                    enable_events=True,
                    font=("Arial", 16),
                    justification="center",
                    expand_x=True,
                )
            ],
        ],
        disable_close=False,
        size=(300, 100),
    )
    while True:
        event, values = loading_window.read(timeout=1)

        if event == "Cancel":
            loading_window["-PBAR-"].update(max=max_length)

        if event == sg.WIN_CLOSED or event == "Exit":
            break

        for season in missing_seasons:
            loading_window["-OUT-"].update("Loading New Season: " + str(season))
            all_data = get_new_data(season)
            loading_window["-PBAR-"].update(
                current_count=missing_seasons.index(season) + 1
            )

        loading_window.close()


icon_file = WD + "/resources/ll_app_logo.png"
sg.theme("Reddit")
sg.set_options(icon=base64.b64encode(open(str(icon_file), "rb").read()))
window = sg.Window(
    "Learned League Practice Tool",
    layout=layout,
    finalize=True,
    resizable=False,
    element_justification="center",
    return_keyboard_events=True,
)

categories = ["ALL"] + sorted(list(set([q["category"] for q in all_data.values()])))
seasons = ["ALL"] + sorted(list(set([q["season"] for q in all_data.values()])))

# window["season_title"].update(value=seasons[0])
window["category_selection"].update(values=categories, value="ALL")
window["season"].update(values=seasons, value="ALL")

questions = filter_questions(all_data, 0, 100, "ALL", "ALL")
window["dropdown"].update(values=list(questions.keys()))

window.bind("<Command-s>", "show_key")
window.bind("<Command-r>", "random_key")
window.bind("<Command-n>", "next_key")
window.bind("<Command-p>", "previous_key")
window["question"].bind("<ButtonPress-2>", "press")
window["question"].bind("<ButtonPress-1>", "click_here")
window["answer_submission"].bind("<Return>", "_submit_answer_button")
sess = None
values = None
i = choice(list(questions.keys()))
question_object = update_question(questions, window, i)
if i > 1:
    window["previous"].update(disabled=False)

if i < len(list(questions.keys())):
    window["next"].update(disabled=False)

while True:
    event, values = window.read()

    # If the window is closed, break the loop and close the application
    if event in (None, "Quit", sg.WIN_CLOSED):
        if sess:
            sess.close()
        window.close()
        break

    if "Escape" in event:
        if (
            window.find_element_with_focus()
            and window.find_element_with_focus().Key == "search_criteria"
        ):
            window["search_criteria"].update(value="")
            window["filter"].set_focus()

    if event == "questionpress":
        question_widget = window["question"].Widget
        selection_ranges = question_widget.tag_ranges(sg.tk.SEL)
        if selection_ranges:
            window["question"].set_right_click_menu(["&Right", ["Lookup Selection"]])
            selected_text = question_widget.get(*selection_ranges)
        else:
            window["question"].set_right_click_menu(["&Right", ["!Lookup Selection"]])
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
                sg.popup_ok(result, title="Dictionary Result", font=("Arial", 16))
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

    if event == "season":
        window.write_event_value("filter", "")
        question_object = update_question(questions, window, i)
        answer = question_object.get("answer")

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

    # if the category dropdown is changed from ALL, or the filter button is pressed
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

    # display or hide the answer for the currently displayed question
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
            window["answer_submission"].Widget.configure(readonlybackground="gray")
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

    if "submit_answer_button" in event:
        if not values["answer_submission"]:
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
            window["answer_submission"].Widget.configure(readonlybackground="red")

        window["question"].set_focus()
        window["correct_override"].update(disabled=False)

        # track answers in all_data.json
        past_answers = question_object.get("answers") or []
        data_code = "S" + question_object["season"] + question_object["question_num"]
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

    if "correct_override" in event:
        if right_answer:
            right_answer = False
            window["answer_submission"].Widget.configure(readonlybackground="red")
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

    if event == "onedays_button":
        window.hide()
        unhide = oneday_main()
        window.un_hide()

    if event == "minileague_button":
        window.hide()
        unhide = minileague()
        window.un_hide()

    # if the question number is clicked, open the link
    if event == "question_number":
        webbrowser.open(window["question_number"].metadata)

    if "click_here" in event:
        webbrowser.open(window["question"].metadata)

    if event == "login_button":
        user_data = None
        season_day = f"S{latest_season}D{current_day}Q6"
        if window["login_button"].get_text() == "Login":
            sess = login()
            if not sess:
                continue

            if USER_DATA_DIR + f"{sess.headers.get('profile')}.json":
                with open(USER_DATA_DIR + f"{sess.headers.get('profile')}.json") as fp:
                    user_data = DotMap(json.load(fp))

            user_data = get_question_history(sess, user_data=user_data)
            user_data = get_user_stats(sess, user_data=user_data)
            if user_data.ok:
                window["login_button"].update(text="Logout")
                window["stats_button"].update(disabled=False)
                window["defense_button"].update(disabled=False)
                logged_in_user = user_data.username

        elif window["login_button"].get_text() == "Logout":
            login(logout=True)
            window["login_button"].update(text="Login")
            window["stats_button"].update(disabled=True)
            window["defense_button"].update(disabled=True)
            sess.close()

    if event == "stats_button":
        available_players = [name.split(".")[0] for name in os.listdir(USER_DATA_DIR)]
        if user_data.get("stats"):
            combo_values = sorted(available_players)
            stats_layout = [
                [
                    sg.Combo(
                        combo_values,
                        default_value=user_data.username,
                        key="available_users",
                        readonly=True,
                        enable_events=True,
                    ),
                    sg.Button("Category Metrics", size=(16, 1), key="category_button"),
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
                ],
                [
                    [
                        sg.Column(
                            layout=[
                                [
                                    sg.Text(
                                        "User",
                                        font=("Arial Bold", 14),
                                        justification="c",
                                        expand_x=True,
                                    ),
                                    sg.Text(expand_x=True),
                                    sg.Text(
                                        "HUN",
                                        font=("Arial Bold", 14),
                                        justification="r",
                                        tooltip="HUN Similarity Score",
                                    ),
                                ],
                            ],
                            element_justification="c",
                            size=(150, 30),
                        ),
                        sg.Column(
                            layout=[
                                [
                                    sg.Text(
                                        key,
                                        font=("Arial Bold", 14),
                                        size=(5, 1),
                                        tooltip=STATS_DEFINITION.get(key),
                                        justification="r",
                                    )
                                    for key in list(user_data.stats.total.keys())
                                    if key not in ["Rundle"]
                                ],
                            ],
                            element_justification="c",
                        ),
                    ],
                    [
                        sg.Column(
                            add_stats_row(user_data, logged_in_user),
                            key="stats_column",
                        )
                    ],
                ],
            ]

            stats_window = sg.Window(
                "Learned League User Stats",
                stats_layout,
                finalize=True,
                return_keyboard_events=True,
            )
            stats_window.bind("<Return>", "return_key")

            while True:
                stat_event, stat_values = stats_window.read()

                if stat_event and False:
                    print(stat_event, stat_values)

                if stat_event in (None, "Quit", sg.WIN_CLOSED):
                    stats_window.close()
                    break

                if (
                    stat_event in ["player_search_button", "return_key"]
                    and stat_values["player_search"]
                ):
                    if (
                        f"row_name_{stat_values['player_search']}"
                        in stats_window.AllKeysDict
                    ):
                        stats_window["player_search"].update(value="")
                        continue

                    searched_user_data = load_user_data(
                        stats_window["player_search"].get(), current_day=season_day
                    )

                    if not searched_user_data.get("stats"):
                        stats_window["player_search"].update(value="")
                        sg.popup_auto_close(
                            "Player Not Found.", no_titlebar=True, modal=False
                        )
                        stats_window["player_search"].set_focus()
                        continue

                    stats_window["player_search"].update(value="")
                    stats_window.extend_layout(
                        stats_window["stats_column"],
                        add_stats_row(searched_user_data, logged_in_user),
                    )
                    combo_values.append(searched_user_data.username)
                    stats_window["available_users"].update(
                        values=combo_values, value=combo_values[0]
                    )

                if stat_event == "available_users":
                    if (
                        f"row_name_{stats_window['available_users'].get()}"
                        in stats_window.AllKeysDict
                    ):
                        continue

                    searched_user_data = load_user_data(
                        stats_window["available_users"].get(), current_day=season_day
                    )
                    stats_window.extend_layout(
                        stats_window["stats_column"],
                        add_stats_row(searched_user_data, logged_in_user),
                    )

                if "category_button" in stat_event:
                    display_category_metrics(
                        load_user_data(
                            stats_window["available_users"].get(),
                            current_day=season_day,
                        )
                    )

                if "remove_" in stat_event:
                    row = re.sub("[0-9]+", "", f"row_name_{stat_event.split('_')[-1]}")
                    stats_window[row].update(visible=False)
                    stats_window[row].Widget.master.pack_forget()
                    stats_window["stats_column"].Widget.update()
                    stats_window.AllKeysDict.pop(row)

    if "defense_button" in event:
        page = bs(
            sess.get(
                f"https://learnedleague.com/profiles.php?{user_data.username}"
            ).content,
            "html.parser",
            parse_only=ss("table"),
        )

        opponents = [
            val.img.get("title")
            for val in page.find(
                "table", {"summary": "Data table for LL results"}
            ).find_all("tr")[1:]
        ]
        category_values = list(user_data.category_metrics.keys())
        defense_window = sg.Window(
            "Head to Head Defense Strategy",
            layout=[
                [
                    sg.Text("Opponent: ", font=("Arial Bold", 16), expand_x=True),
                    sg.Combo(
                        opponents,
                        default_value=opponents[current_day],
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
                [sg.Button("Show Similarity", key="similarity_chart")],
                [sg.HorizontalSeparator()],
                [
                    sg.Frame(
                        title="Defense Strategy",
                        expand_x=True,
                        layout=[
                            [
                                sg.Text("Defense Strategy", font=DEFAULT_FONT),
                                sg.Text(expand_x=True),
                                sg.Text("Suggested Points", font=DEFAULT_FONT),
                            ],
                            [
                                sg.Column(
                                    layout=[
                                        [
                                            sg.Text(
                                                f"Question {i}:", font=DEFAULT_FONT
                                            ),
                                            sg.Combo(
                                                category_values,
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
                                                justification="r",
                                            ),
                                        ]
                                        for i in range(1, 7)
                                    ]
                                )
                            ],
                            [
                                sg.Button("Submit", key="submit_defense"),
                                sg.Button("Clear", key="defense_clear"),
                            ],
                        ],
                    )
                ],
                [
                    sg.Frame(
                        title="Question History Search",
                        expand_x=True,
                        expand_y=True,
                        layout=[
                            [
                                sg.Text("Search Text:", font=DEFAULT_FONT),
                                sg.Input(
                                    "",
                                    font=DEFAULT_FONT,
                                    key="defense_question_search_term",
                                    size=(15, 1),
                                    expand_x=True,
                                ),
                                sg.Button("Search", key="search_questions_button"),
                            ],
                            [
                                sg.Text("Output:", font=DEFAULT_FONT),
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
                                    size=(25, 5),
                                ),
                            ],
                        ],
                    )
                ],
            ],
            finalize=True,
            size=(375, 500),
            resizable=True,
        )
        player_1 = user_data
        while True:
            defense_event, defense_values = defense_window.read()
            if defense_event in (None, "Quit", sg.WIN_CLOSED):
                defense_window.close()
                break

            if defense_event == "submit_defense":
                player_2 = load_user_data(
                    defense_values.get("opponent"), current_day=season_day
                )

                player_1, player_2 = calc_hun_score(
                    player_1,
                    player_2,
                    save=True,
                )
                hun_score = player_1.hun.get(player_2.username)
                defense_window["hun_score"].update(value=round(hun_score, 3))

                question_categories = [
                    defense_values.get(key)
                    for key in defense_values.keys()
                    if "strat" in key
                ]

                if not all(question_categories):
                    continue

                raw_scores = [3, 2, 2, 1, 1, 0]
                percents = DotMap(
                    {
                        f"question_{i+1}": {
                            "percent": player_2.category_metrics.get(key).percent
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
                    defense_window[f"defense_suggestion_{i+1}"].update(
                        value=percents[key].score
                    )
                    for i, key in enumerate(list(percents.keys()))
                ]

            if defense_event == "defense_clear":
                [
                    defense_window[f"defense_suggestion_{i}"].update(value="")
                    for i in range(1, 7)
                ]
                [
                    defense_window[f"defense_strat_{i}"].update(value="")
                    for i in range(1, 7)
                ]

            if defense_event == "search_questions_button":
                player_2 = load_user_data(
                    defense_values.get("opponent"), current_day=season_day
                )

                search_term = defense_values["defense_question_search_term"]
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
                        f"key: {key} - {filtered_dict[key].question_category}"
                        + f" - Correct: {filtered_dict[key].correct}"
                        for key in sorted(list(filtered_dict.keys()), reverse=True)
                    ]
                )
                defense_window["filtered_metrics"].update(
                    value=f"Total Correct: {total_filtered_correct}/{total_filtered_questions}"
                )
                defense_window["output_questions"].update(value=result)

            if defense_event == "similarity_chart":
                player_2 = load_user_data(
                    defense_values.get("opponent"), current_day=season_day
                )
                player_1, player_2 = calc_hun_score(
                    player_1,
                    player_2,
                    save=True,
                )
                hun_score = player_1.hun.get(player_2.username)
                defense_window["hun_score"].update(value=round(hun_score, 3))

                fig = Figure()
                config = {
                    "toImageButtonOptions": {
                        "format": "png",
                        "filename": f"{player_1.username}_{player_2.username}_similarity",
                    },
                }
                fig.add_trace(
                    Scatterpolar(
                        r=[
                            category.percent
                            for category in player_1.category_metrics.values()
                        ],
                        theta=[
                            category for category in player_1.category_metrics.keys()
                        ],
                        fill="toself",
                        name=player_1.username,
                    )
                )
                fig.add_trace(
                    Scatterpolar(
                        r=[
                            category.percent
                            for category in player_2.category_metrics.values()
                        ],
                        theta=[
                            category for category in player_2.category_metrics.keys()
                        ],
                        fill="toself",
                        name=player_2.username,
                    )
                )
                fig.update_layout(
                    title_text="Learned League Similarity",
                    polar=dict(
                        radialaxis=dict(visible=True, range=[0, 1]),
                    ),
                    showlegend=True,
                )

                fig.show(config=config)
