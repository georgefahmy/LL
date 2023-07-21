import requests
import PySimpleGUI as sg
import webbrowser
import sys
import os
import base64
import json
import wikipedia
import re
import datetime

from bs4 import BeautifulSoup as bs, SoupStrainer as ss
from layout import layout
from PyDictionary import PyDictionary
from check_for_updates import check_for_update
from random import choice
from onedays import oneday_main
from answer_correctness import combined_correctness


BASE_URL = "https://www.learnedleague.com"

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
        answers = [link.text.strip() for link in page.find_all("div", {"class": "a-red"})]
        date = page.find_all("h1", {"class": "matchday"})[0].text.strip().split(":")[0]

        rundles = [row.find_all("td", {"class": "ind-Q3"}) for row in page.find_all("tr")[1:8]]

        for j, question in enumerate(questions):
            question_num_code = "D" + str(i).zfill(2) + "Q" + str(j + 1)
            combined_season_num_code = "S" + season_number + question_num_code
            question_url = (
                BASE_URL + "/question.php?" + str(season_number) + "&" + str(i) + "&" + str(j + 1)
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

    with open(WD + "/resources/all_data.json", "w+") as fp:
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
    question_object = questions.get(i)
    if not question_object:
        return
    question = question_object.get("_question")

    window["question"].update(value=question)
    window["question"].metadata = question_object.get("clickable_link")
    if question_object.get("clickable_link"):
        window["question"].set_tooltip("Click to Open: " + question_object.get("clickable_link"))
        window["question"].TooltipObject.timeout = 10
    else:
        window["question"].set_tooltip("")
        window["question"].TooltipObject.timeout = 10000
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
missing_seasons = sorted(list(set(available_seasons).symmetric_difference(set(season_in_data))))

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
        event, values = loading_window.read(timeout=1)

        if event == "Cancel":
            loading_window["-PBAR-"].update(max=max_length)

        if event == sg.WIN_CLOSED or event == "Exit":
            break

        for season in missing_seasons:
            loading_window["-OUT-"].update("Loading New Season: " + str(season))
            all_data = get_new_data(season)
            loading_window["-PBAR-"].update(current_count=missing_seasons.index(season) + 1)

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
                        [key + ": " + ", ".join(value) for key, value in definition.items()]
                    )
                )
                print(result)
                sg.popup_ok(result, title="Dictionary Result", font=("Arial", 16))
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

    if event == "season":
        window.write_event_value("filter", "")
        question_object = update_question(questions, window, i)
        answer = question_object.get("answer")

    if event in ("random_choice", "random_key"):
        if window.find_element_with_focus() and window.find_element_with_focus().Key in (
            "search_criteria",
            "answer_submission",
        ):
            continue
        i = choice(list(questions.keys()))
        question_object = update_question(questions, window, i)
        answer = question_object.get("answer")
        window["answer_submission"].update(value="", disabled=False)
        window["submit_answer_button"].update(disabled=False)
        window["correct_override"].update(disabled=True)

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
        if window.find_element_with_focus() and window.find_element_with_focus().Key in (
            "search_criteria",
            "answer_submission",
        ):
            continue

        answer = question_object["answer"]
        window["answer_submission"].update(disabled=True)
        window["submit_answer_button"].update(disabled=True)
        window["correct_override"].update(disabled=True)

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
    if event in ["next", "previous", "dropdown", "next_key", "previous_key"]:
        if window.find_element_with_focus() and window.find_element_with_focus().Key in (
            "search_criteria",
            "answer_submission",
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
        if not values[f"answer_submission"]:
            continue

        submitted_answer = values[f"answer_submission"].lower()
        answer = question_object["answer"]
        window["answer"].update(value=answer, font=("Arial", 16))
        window["answer_submission"].update(disabled=True)
        window["submit_answer_button"].update(disabled=True)

        answers = re.findall("([^\/,()]+)", answer)
        if len(answers) > 1:
            correct = [
                combined_correctness(submitted_answer, answer.strip(), True) for answer in answers
            ]
        else:
            correct = [combined_correctness(submitted_answer, answer.strip())]

        if any(correct):
            right_answer = True
            window["answer_submission"].Widget.configure(readonlybackground="light green")

        else:
            right_answer = False
            window["answer_submission"].Widget.configure(readonlybackground="red")

        window[f"question"].set_focus()
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
        with open(WD + "/resources/all_data.json", "w+") as fp:
            json.dump(all_data, fp, sort_keys=True, indent=4)

    if "correct_override" in event:
        if right_answer:
            right_answer = False
            window[f"answer_submission"].Widget.configure(readonlybackground="red")
        else:
            right_answer = True
            window[f"answer_submission"].Widget.configure(readonlybackground="light green")

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
        with open(WD + "/resources/all_data.json", "w+") as fp:
            json.dump(all_data, fp, sort_keys=True, indent=4)

    if event == "onedays_button":
        window.hide()
        unhide = oneday_main()
        window.un_hide()

    # if the question number is clicked, open the link
    if event == "question_number":
        webbrowser.open(window["question_number"].metadata)

    if "click_here" in event:
        webbrowser.open(window["question"].metadata)
