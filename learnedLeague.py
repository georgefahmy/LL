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
from layout import super_layout
from logged_in_tools import (
    DEFAULT_FONT,
    STATS_DEFINITION,
    display_category_metrics,
    login,
)
from minileagues import minileague
from onedays import oneday_main
from userdata import load

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
    hun_score = (
        f"HUN: {round(user_data.hun.get(logged_in_user), 3)}"
        if user_data.hun.get(logged_in_user)
        else "HUN: --"
    )
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
                                hun_score,
                                font=DEFAULT_FONT,
                                justification="c",
                                expand_x=True,
                            ),
                        ],
                    ],
                    justification="l",
                    element_justification="l",
                    expand_x=True,
                    size=(160, 30),
                ),
                sg.Column(
                    expand_x=True,
                    layout=[
                        [
                            sg.Text(
                                key,
                                font=("Arial Bold", 14),
                                size=(5, 1),
                                tooltip=STATS_DEFINITION.get(key),
                                justification="c",
                            )
                            for key in list(STATS_DEFINITION.keys())
                            if key not in ["Rundle"]
                        ],
                        [sg.HorizontalSeparator()],
                        [
                            # Overall Stats across all seasons
                            sg.Text(
                                user_data.stats.total.get(key),
                                font=DEFAULT_FONT,
                                size=(5, 1),
                                justification="c",
                                tooltip=STATS_DEFINITION.get(key),
                            )
                            for key in list(STATS_DEFINITION)
                            if key not in ["Rundle"]
                        ],
                        [
                            # Current Season stats
                            sg.Text(
                                user_data.stats.current_season.get(key),
                                font=DEFAULT_FONT,
                                size=(5, 1),
                                justification="c",
                                tooltip=STATS_DEFINITION.get(key),
                            )
                            for key in list(STATS_DEFINITION)
                            if key not in ["Rundle"]
                        ],
                    ],
                ),
                sg.Column(
                    layout=[
                        [
                            sg.Button(
                                "Remove",
                                key=f"remove_{user_data.username}",
                            )
                        ]
                    ],
                ),
            ],
        ],
        expand_x=True,
        key=re.sub("[0-9]+", "", f"row_name_{user_data.username}"),
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

season_day = f"S{latest_season}D{current_day}Q6"

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
    layout=super_layout,
    finalize=True,
    resizable=True,
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
logged_in = False
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

    # Clear search box via esc key
    if "Escape" in event:
        if (
            window.find_element_with_focus()
            and window.find_element_with_focus().Key == "search_criteria"
        ):
            window["search_criteria"].update(value="")
            window["filter"].set_focus()

    # Trigger the right click menu for searching text within a question
    if event == "questionpress":
        question_widget = window["question"].Widget
        selection_ranges = question_widget.tag_ranges(sg.tk.SEL)
        if selection_ranges:
            window["question"].set_right_click_menu(["&Right", ["Lookup Selection"]])
            selected_text = question_widget.get(*selection_ranges)
        else:
            window["question"].set_right_click_menu(["&Right", ["!Lookup Selection"]])
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

    # Check the submitted answer against the correct answer for the specific question
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

    # If the checking algorithm is wrong, the check box can be used to overwrite the 'correctness'
    # of the answer being submitted
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

    # Open the One Day Specials Interface (and hide the main interface)
    if event == "onedays_button":
        window.hide()
        unhide = oneday_main()
        window.un_hide()

    # Open the MiniLeague interface (and hide the main interface)
    if event == "minileague_button":
        window.hide()
        unhide = minileague()
        window.un_hide()

    # if the question number is clicked, open the link
    if event == "question_number":
        webbrowser.open(window["question_number"].metadata)

    # Open the question item in your browser
    if "click_here" in event:
        webbrowser.open(window["question"].metadata)

    # Open the LL homepage
    if event == "open_ll":
        webbrowser.open("https://www.learnedleague.com")

    # Login to the LL website with provided credentials. This will expand the interface
    # to include significantly more data and capabilities
    if event == "login_button":
        user_data = None
        if window["login_button"].get_text() == "Login":
            sess = login()
            if not sess:
                continue
            username = sess.headers.get("profile")
            user_data = load(username=username, sess=sess)

            if user_data.ok:
                logged_in = True
                logged_in_user = user_data.username
                window["login_button"].update(text="Logout")
                window["defense_frame"].update(visible=True)
                window["stats_frame"].update(visible=True)
                combo_values = sorted(
                    [name.split(".")[0] for name in os.listdir(USER_DATA_DIR)]
                )
                window["available_users"].update(
                    values=combo_values,
                    value=user_data.username,
                )
                window.extend_layout(
                    window["stats_column"],
                    add_stats_row(user_data, logged_in_user),
                )
                window.move_to_center()
                max_stats = 1

                window["player_1"].update(
                    values=user_data.opponents, value=user_data.username
                )
                window["opponent"].update(
                    values=user_data.opponents, value=user_data.opponents[current_day]
                )

        elif window["login_button"].get_text() == "Logout":
            login(logout=True)
            sess.close()
            window.close()
            break

    # Search for players via their username and return their stats (and save their data)
    if event in ["player_search_button", "return_key"] and values["player_search"]:
        if not logged_in:
            continue
        max_stats = len(
            [key for key in list(window.AllKeysDict.keys()) if "row_name_" in str(key)]
        )
        if f"row_name_{values['player_search']}" in window.AllKeysDict:
            window["player_search"].update(value="")
            continue

        searched_user_data = load(window["player_search"].get(), sess=sess)
        if searched_user_data.username not in window["available_users"].get():
            combo_values.append(searched_user_data.username)
            combo_values = list(set(combo_values))
            window["available_users"].update(values=combo_values, value=combo_values[0])

        if max_stats >= 3:
            continue

        if not searched_user_data.get("stats"):
            window["player_search"].update(value="")
            sg.popup_auto_close("Player Not Found.", no_titlebar=True, modal=False)
            window["player_search"].set_focus()
            continue

        window["player_search"].update(value="")
        window.extend_layout(
            window["stats_column"],
            add_stats_row(searched_user_data, logged_in_user),
        )
        window.move_to_center()

    # Select a user from the dropdown and display their stats
    if event == "available_users":
        if not logged_in:
            continue
        max_stats = len(
            [key for key in list(window.AllKeysDict.keys()) if "row_name_" in str(key)]
        )
        if f"row_name_{window['available_users'].get()}" in window.AllKeysDict:
            continue

        if max_stats >= 3:
            continue

        searched_user_data = load(window["available_users"].get(), sess=sess)
        window.extend_layout(
            window["stats_column"],
            add_stats_row(searched_user_data, logged_in_user),
        )
        window.move_to_center()

    # Display the selected users category metrics. Depending on which button is pressed
    # the appropriate user will be displayed
    if "category_button" in event:
        if not logged_in:
            continue
        if "defense" in event:
            opponent = window["opponent"].get()
        else:
            opponent = window["available_users"].get()
        display_category_metrics(load(opponent, sess=sess))

    # Remove the statistics row from the interface
    if "remove_" in event:
        if not logged_in:
            continue
        row = re.sub("[0-9]+", "", f"row_name_{event.split('_')[-1]}")
        window[row].update(visible=False)
        window[row].Widget.master.pack_forget()
        window["stats_column"].Widget.update()
        window.AllKeysDict.pop(row)
        max_stats = len(
            [key for key in list(window.AllKeysDict.keys()) if "row_name_" in str(key)]
        )

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

        player_1.calc_hun(player_2)

        if player_2.username not in window["available_users"].get():
            combo_values.append(player_2.username)
            combo_values = list(set(combo_values))
            window["available_users"].update(values=combo_values, value=combo_values[0])

        hun_score = player_1.hun.get(player_2.username)
        window["hun_score"].update(value=round(hun_score, 3))

        question_categories = [
            values.get(key) for key in values.keys() if "strat" in key
        ]

        if not all(question_categories):
            continue

        raw_scores = [3, 2, 2, 1, 1, 0]
        percents = DotMap(
            {
                f"question_{i+1}": {
                    "percent": player_2.category_metrics.get(key).percent
                    if player_2.category_metrics.get(key)
                    else 0
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
            window[f"defense_suggestion_{i+1}"].update(value=percents[key].score)
            for i, key in enumerate(list(percents.keys()))
        ]

    # Clear the categories and points from the window
    if event == "defense_clear":
        [window[f"defense_suggestion_{i}"].update(value="") for i in range(1, 7)]
        [window[f"defense_strat_{i}"].update(value="") for i in range(1, 7)]

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

        if player_2.username not in window["available_users"].get():
            combo_values.append(player_2.username)
            combo_values = list(set(combo_values))
            window["available_users"].update(values=combo_values, value=combo_values[0])

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
                f"key: {key} - {filtered_dict[key].question_category}"
                + f" - Correct: {filtered_dict[key].correct}"
                for key in sorted(list(filtered_dict.keys()), reverse=True)
            ]
        )
        window["filtered_metrics"].update(
            value=f"Total Correct: {total_filtered_correct}/{total_filtered_questions}"
        )
        window["output_questions"].update(value=result)

    # Calculate the HUN similarity between the two players (player 1 and opponent)
    if event == "calc_hun":
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

        player_1.calc_hun(player_2)

        hun_score = player_1.hun.get(player_2.username)
        window["hun_score"].update(value=round(hun_score, 3))
        if player_2.username not in window["available_users"].get():
            combo_values.append(player_2.username)
            combo_values = list(set(combo_values))
            window["available_users"].update(values=combo_values, value=combo_values[0])

    # Open a plotly web chart showing the similarity in metrics between the two players
    if event == "similarity_chart":
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

        player_1.calc_hun(player_2)

        hun_score = player_1.hun.get(player_2.username)
        window["hun_score"].update(value=round(hun_score, 3))
        if player_2.username not in window["available_users"].get():
            combo_values.append(player_2.username)
            combo_values = list(set(combo_values))
            window["available_users"].update(values=combo_values, value=combo_values[0])

        fig = Figure()
        config = {
            "displaylogo": False,
            "displayModeBar": True,
            "modeBarButtonsToRemove": ["lasso2d", "select2d"],
            "toImageButtonOptions": {
                "format": "png",
                "filename": f"{player_1.username}_{player_2.username}_similarity",
            },
        }
        fig.add_trace(
            Scatterpolar(
                r=[category.percent for category in player_1.category_metrics.values()],
                theta=[category for category in player_1.category_metrics.keys()],
                fill="toself",
                name=player_1.username,
            )
        )
        fig.add_trace(
            Scatterpolar(
                r=[category.percent for category in player_2.category_metrics.values()],
                theta=[category for category in player_2.category_metrics.keys()],
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
