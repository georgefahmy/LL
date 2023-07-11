import requests
import PySimpleGUI as sg
import webbrowser
import sys
import os
import base64
import json

from bs4 import BeautifulSoup as bs, SoupStrainer as ss
from pprint import pprint
from time import sleep
from layout import layout
from check_for_updates import check_for_update
from random import choice


BASE_URL = "https://www.learnedleague.com"

try:
    WD = sys._MEIPASS
except AttributeError:
    WD = os.getcwd()

restart = check_for_update()
if restart:
    restart = False
    os.execv(sys.executable, ["python"] + sys.argv)


def get_new_data(season_number):
    try:
        with open(WD + "/resources/all_data.json", "r") as fp:
            all_data = json.load(fp)
    except:
        all_data = {}

    try:
        with open(WD + "/resources/rundle_info.json", "r") as fp:
            rundle_info = json.load(fp)
    except:
        rundle_info = {}

    url = BASE_URL + "/match.php?" + str(season_number)
    for i in range(1, 26):
        question_url = url + "&" + str(i)
        page = bs(requests.get(question_url).content, "html.parser")

        categories = [
            link.text.strip().split("-")[0].split(".")[-1].strip()
            for link in page.find_all("div", {"class": "ind-Q20 dont-break-out"})
        ]

        percentages = [
            cell.text for cell in page.find_all("tr")[-2].find_all("td", {"class": "ind-Q3"})
        ][2:-1]

        question_defense = [
            cell.text for cell in page.find_all("tr")[-1].find_all("td", {"class": "ind-Q3"})
        ][2:-1]

        questions = [
            "-".join(link.text.strip().split("-")[1:]).strip()
            for link in page.find_all("div", {"class": "ind-Q20 dont-break-out"})
        ]
        answers = [link.text.strip() for link in page.find_all("div", {"class": "a-red"})]

        rundles = [row.find_all("td", {"class": "ind-Q3"}) for row in page.find_all("tr")[1:8]]

        for j, question in enumerate(questions):
            question_num_code = "D" + str(i).zfill(2) + "Q" + str(j + 1)
            combined_season_num_code = "S" + season_number + question_num_code
            question_url = (
                BASE_URL + "/question.php?" + str(season_number) + "&" + str(i) + "&" + str(j + 1)
            )
            rundle_info[combined_season_num_code] = {
                "A":[cell.text for cell in rundles[0]][2:-1][j],
                "B":[cell.text for cell in rundles[1]][2:-1][j],
                "C":[cell.text for cell in rundles[2]][2:-1][j],
                "D":[cell.text for cell in rundles[3]][2:-1][j],
                "E":[cell.text for cell in rundles[4]][2:-1][j],
                "R":[cell.text for cell in rundles[5]][2:-1][j],
            }
            all_data[combined_season_num_code] = {
                "_question": question,
                "answer": answers[j],
                "season": season_number,
                "category": categories[j],
                "percent": percentages[j],
                "question_num": question_num_code,
                "defense": question_defense[j],
                "url": question_url,
            }

    with open("resources/all_data.json", "w+") as fp:
        json.dump(all_data, fp, sort_keys=True, indent=4)

    with open("resources/rundle_info.json", "w+") as fp:
        json.dump(rundle_info, fp, sort_keys=True, indent=4)

    return all_data


def filter_questions(all_questions_dict, min_threshold, max_threshold, category_filter, season_filter):
    min_threshold = int(min_threshold)
    max_threshold = int(max_threshold)

    if max_threshold <= min_threshold:
        max_threshold = min_threshold + 5

    if category_filter == "ALL":
        filtered_question_ids = [
            question_ids
            for question_ids, question in all_questions_dict.items()
            if int(question["percent"]) >= min_threshold
            and int(question["percent"]) < max_threshold
        ]
    else:
        filtered_question_ids = [
            question_ids
            for question_ids, question in all_questions_dict.items()
            if int(question["percent"]) >= min_threshold
            and int(question["percent"]) < max_threshold
            and question["category"].upper() == category_filter.upper()
        ]

    if season_filter != "ALL":
        filtered_question_ids = [
            question_ids
            for question_ids, question in all_questions_dict.items()
            if question["season"] == season_filter
        ]

    filtered_questions_dict = {
        i + 1: val
        for i, val in enumerate([all_questions_dict[key] for key in filtered_question_ids])
    }

    return filtered_questions_dict


def update_question(questions, window, values, i):
    if not values:
        min_per = 0
        max_per = 100
        category = "ALL"
        season = "ALL"
        # season_title = window["season_title"].get()

    else:
        min_per = values["min_%"]
        max_per = values["max_%"]
        category = values["category_selection"]
        season = values["season"]

    question_object = questions.get(i)
    if not question_object:
        return
    question = question_object.get("_question")

    window["question"].update(value=question)
    # window["season_title"].update(value=season)
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
    combined_season_num_code = "S" + question_object["season"] + question_object["question_num"]
    rundle_info = json.load(open("resources/rundle_info.json","r"))[combined_season_num_code]

    window["rundle_A"].update(value=rundle_info["A"] + "%")
    window["rundle_B"].update(value=rundle_info["B"] + "%")
    window["rundle_C"].update(value=rundle_info["C"] + "%")
    window["rundle_D"].update(value=rundle_info["D"] + "%")
    window["rundle_E"].update(value=rundle_info["E"] + "%")
    window["rundle_R"].update(value=rundle_info["R"] + "%")


    return question_object


latest_season = (
    bs(
        requests.get("https://www.learnedleague.com/allrundles.php").content,
        "html.parser",
        parse_only=ss("h1"),
    )
    .text.split(":")[0]
    .split("LL")[-1]
)

available_seasons = [str(season) for season in list(range(60, int(latest_season) + 1, 1))]


datapath = WD + "/resources/all_data.json"
if os.path.isfile(datapath):
    with open(datapath, "r") as fp:
        all_data = json.load(fp)
else:
    all_data = {}

season_in_data = list(set([val.split("D")[0].strip("S") for val in list(all_data.keys())]))
missing_seasons = sorted(
    list(set(available_seasons).symmetric_difference(set(season_in_data)))
)

if len(missing_seasons) > 0:
    icon_file = WD + "/resources/ll_app_logo.png"
    sg.set_options(icon=base64.b64encode(open(str(icon_file), "rb").read()))
    max_length = len(missing_seasons)
    loading_window = sg.Window(
        "Loading New Seasons",
        [
            [
                sg.ProgressBar(
                    max_length, orientation="h", expand_x=True, size=(20, 20), key="-PBAR-"
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
        event, values = loading_window.read(timeout=10)

        if event == "Cancel":
            loading_window["-PBAR-"].update(max=max_length)

        if event == sg.WIN_CLOSED or event == "Exit":
            break

        for season in missing_seasons:
            all_data = get_new_data(season)
            loading_window["-OUT-"].update("Loading New Season: " + str(season))
            loading_window["-PBAR-"].update(current_count=missing_seasons.index(season)+1)

        loading_window.close()


icon_file = WD + "/resources/ll_app_logo.png"
sg.set_options(icon=base64.b64encode(open(str(icon_file), "rb").read()))
window = sg.Window(
    "Learned League Practice Tool",
    layout=layout,
    finalize=True,
    resizable=False,
    element_justification="center",
)

all_questions_dict = all_data

categories = ["ALL"] + list(set([q["category"] for q in all_questions_dict.values()]))
seasons = ["ALL"] + sorted(list(set([q["season"] for q in all_questions_dict.values()])))

# window["season_title"].update(value=seasons[0])
window["category_selection"].update(values=categories, value="ALL")
window["season"].update(values=seasons, value="ALL")

questions = filter_questions(all_questions_dict, 0, 100, "ALL", "ALL")
window["dropdown"].update(values=list(questions.keys()))

window.bind("<s>", "show_key")

values = None
i = choice(list(questions.keys()))
question_object = update_question(questions, window, values, i)
if i > 1:
    window["previous"].update(disabled=False)

if i < len(list(questions.keys())):
    window["next"].update(disabled=False)

while True:
    event, values = window.read()

    # If the window is closed, break the loop and close the application
    if event in (None, "Quit", sg.WIN_CLOSED):
        window.close()
        break

    if event == "season":
        window.write_event_value("filter", "")
        question_object = update_question(questions, window, values, i)
        answer = question_object.get("answer")

    if event == "random_choice":
        i = choice(list(questions.keys()))
        question_object = update_question(questions, window, values, i)
        answer = question_object.get("answer")

    # if the category dropdown is changed from ALL, or the filter button is pressed, display the new questions
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
            all_questions_dict, values["min_%"], values["max_%"], values["category_selection"], values["season"]
        )

        if not questions:
            window["question"].update(value="No Questions Available")

        window["dropdown"].update(values=list(questions.keys()), value=1)
        i = 1

        question_object = update_question(questions, window, values, i)
        window["previous"].update(disabled=True)

    # display or hide the answer for the currently displayed question
    if event in ("show/hide", "show_key") :
        answer = question_object.get("answer")

        if window["show/hide"].get_text() == "Show Answer":
            try:
                window["show/hide"].update(text="Hide Answer")
                window["answer"].update(value=answer, font=("Arial", 16))
            except:
                continue

        elif window["show/hide"].get_text() == "Hide Answer":
            window["show/hide"].update(text="Show Answer")
            try:
                if answer:
                    window["answer"].update(value="******")
                else:
                    window["answer"].update(value="")
            except:
                continue

    # if the next or previous or a specific question is selected, display that question and its information
    # and hide the answer.
    if event in ["next", "previous", "dropdown"]:
        if event == "next":
            i += 1

        elif event == "previous":
            i -= 1

        elif event == "dropdown":
            i = values["dropdown"]

        question_object = update_question(questions, window, values, i)
        answer = question_object.get("answer")

        if not question_object:
            if event == "next":
                i -= 1
            elif event == "previous":
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

    # if the question number is clicked, open the link
    if event == "question_number":
        webbrowser.open(window["question_number"].metadata)
