import requests
from bs4 import BeautifulSoup as bs
import json
import base64
import os
from cryptography.fernet import Fernet
import PySimpleGUI as sg
from random import choice
import re
from pprint import pprint
import datetime
import webbrowser
import wikipedia
from answer_correctness import combined_correctness
from oneday_layout import layout

BASE_URL = "https://www.learnedleague.com"
WD = os.getcwd()


def encrypt_answer(answer):
    key = Fernet.generate_key()
    return (Fernet(key).encrypt(answer.encode()).decode(), key.decode())


def decrypt_answer(question):
    encrypted_answer = question.get("answer")
    key = question.get("key")

    if type(encrypted_answer) != bytes:
        encrypted_answer = encrypted_answer.encode()
    if type(key) != bytes:
        key = key.encode()
    return Fernet(key).decrypt(encrypted_answer).decode()


def get_full_list_of_onedays():
    if os.path.isfile("resources/oneday_data.json"):
        with open("resources/oneday_data.json", "r") as fp:
            data = json.load(fp)
    else:
        data = {}
    data = {
        info.find("td", {"class": "std-left"}).text: {
            "title": info.find("td", {"class": "std-left"}).text,
            "url": BASE_URL + info.find("td", {"class": "std-left"}).a.get("href"),
            "date": info.find("td", {"class": "std-midleft"}).text,
        }
        for info in bs(
            requests.get(BASE_URL + "/oneday/onedaysalpha.php").content, "html.parser"
        ).find_all("tr")[1:-1]
    }
    for key in list(data.keys()):
        if datetime.datetime.strptime(data[key]["date"], "%b %d, %Y") >= datetime.datetime.now():
            del data[key]
    with open("resources/oneday_data.json", "w") as fp:
        json.dump(data, fp, sort_keys=True, indent=4)
    return data


def search_onedays(data, search_word=None):
    if not search_word:
        return list(data.keys())
    else:
        return [val for val in list(data.keys()) if search_word.lower() in val.lower()]


def get_specific_oneday(data, onedaykey):
    return data.get(onedaykey)


def get_oneday_data(oneday):
    page = bs(requests.get(oneday["url"]).content, "lxml")
    try:
        metrics_page = bs(
            requests.get(BASE_URL + page.find("ul", {"id": "profilestabs"}).a.get("href")).content,
            "lxml",
        )
    except:
        metrics_page = None
    try:
        questions = [
            ". ".join(q.text.split(".")[1:]).strip()
            for q in page.find("div", {"id": "qs_close", "class": "qdivshow_wide"}).find_all("p")
        ]
    except:
        return None
    answers = [
        a.text.strip().split("\n")[-1]
        for a in page.find("div", {"id": "qs_close", "class": "qdivshow_wide"}).find_all(
            "div", {"class": "answer3"}
        )
    ]
    if metrics_page:
        question_metrics = [
            int(m.text.strip().split()[1])
            for m in metrics_page.find("div", {"class": "q_container"})
            .find("table", {"class": "tbl_q"})
            .find_all("tr")[1:]
        ]
    else:
        question_metrics = [0] * len(questions)

    check_blurb = page.find("div", {"id": "blurb_close"})
    if check_blurb:
        blurb = re.sub("[\r\n]+", "\n", "".join(check_blurb.text.split("blurb")[1:]).strip())
    else:
        blurb = ""
    if "ModKos" in blurb.split():
        ratings = set(["G", "PG", "PG-13", "R", "X"])
        ind = [
            i
            for i, e in enumerate([val.replace(".", "").strip() for val in blurb.split()])
            if e in ratings
        ]
        if ind:
            modkos_rating = blurb.split()[ind[0]].replace(".", "").strip()
        else:
            modkos_rating = "None"
    else:
        modkos_rating = "None"

    oneday["blurb"] = blurb
    oneday["difficulty_rating"] = modkos_rating.replace(",", "")
    oneday["overall_average"] = round(sum(question_metrics) / len(question_metrics), 2)
    oneday_data = {}
    for j, question in enumerate(questions):
        encrypted_answer, key = encrypt_answer(answers[j])
        oneday_data[j + 1] = {
            "_question": question,
            "answer": encrypted_answer,
            "key": key,
            "percent": question_metrics[j],
            "question_num": str(j + 1),
        }
    oneday["data"] = oneday_data
    return oneday


list_of_onedays = get_full_list_of_onedays()  # one time use? store this data in a json file?
font = "Arial", 16

icon_file = WD + "/resources/ll_app_logo.png"
sg.set_options(icon=base64.b64encode(open(str(icon_file), "rb").read()))
window = sg.Window("OneDay Trivia", layout=layout, finalize=True, return_keyboard_events=True)

window["oneday_selection"].update(values=search_onedays(list_of_onedays))
window.bind("<s>", "show_key")
window.bind("<n>", "next_key")
window.bind("<p>", "previous_key")
window.bind("<m>", "money_key")
window["question"].bind("<ButtonPress-2>", "press")
window["question"].bind("<ButtonPress-1>", "click_here")
window["answer_submission"].bind("<Return>", "answer_sub_enter_button")

filtered_results = search_onedays(list_of_onedays)
oneday = get_oneday_data(get_specific_oneday(list_of_onedays, choice(filtered_results)))
while not oneday:
    oneday = get_oneday_data(get_specific_oneday(list_of_onedays, choice(filtered_results)))

data = oneday["data"]
i = 1
score = 0
num_of_money_questions_left = 5
question_object = data[i]
window["oneday_title"].update(value=oneday["title"])
window["difficulty"].update(value=oneday["difficulty_rating"])
window["percent_correct"].update(value=str(oneday["overall_average"]) + "%")
window["blurb_text"].update(value=oneday["blurb"])
window["oneday_date"].update(value=oneday["date"])
window["oneday_selection"].update(value=oneday["title"])
window["next"].update(disabled=False)
window["previous"].update(disabled=True)
window["question"].update(value=question_object["_question"])
window["answer"].update(value="*******")
window["dropdown"].update(value=1, values=[x for x in data.keys()])
window["score"].update(value=score)
window["num_of_money_questions_left"].update(value=num_of_money_questions_left)
submitted_answers = {}

while True:
    event, values = window.read()

    if event in (None, "Quit", sg.WIN_CLOSED):
        window.close()
        break

    # if event:
    #     print(event, values)

    if "Escape" in event:
        window["question"].set_focus()

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
        try:
            result = wikipedia.summary(selected_text, sentences=2, auto_suggest=True, redirect=True)
        except:
            result = "No results available - Try another search."

        sg.popup_ok(result, title="Wiki Summary", font=("Arial", 16))

    if "money_key" in event:
        if window.find_element_with_focus().Key in ("oneday_search", "answer_submission"):
            continue
        if window["money_check"].get():
            window["money_check"].update(value=False)
        else:
            window["money_check"].update(value=True)

    if event == "show_hide_blurb":
        size = window["blurb_frame"].get_size()
        if size[1] == 150:
            window["blurb_frame"].set_size((300, 1))
            window["show_hide_blurb"].update(text="Show Description")
        else:
            window["blurb_frame"].set_size((size[0], 150))
            window["show_hide_blurb"].update(text="Hide Description")

    if event == "random_oneday":
        oneday = get_oneday_data(get_specific_oneday(list_of_onedays, choice(filtered_results)))
        data = oneday["data"]
        i = 1
        score = 0
        question_object = data[i]
        window["oneday_title"].update(value=oneday["title"])
        window["difficulty"].update(value=oneday["difficulty_rating"])
        window["percent_correct"].update(value=str(oneday["overall_average"]) + "%")
        window["blurb_text"].update(value=oneday["blurb"])
        window["oneday_date"].update(value=oneday["date"])
        window["oneday_selection"].update(value=oneday["title"])
        window["next"].update(disabled=False)
        window["previous"].update(disabled=True)
        window["question"].update(value=question_object["_question"])
        window["answer"].update(value="*******")
        window["dropdown"].update(value=1, values=[x for x in data.keys()])
        window["score"].update(value=score)
        window["num_of_money_questions_left"].update(value=num_of_money_questions_left)
        window["money_check"].update(value=False)
        submitted_answers = {}

    if event == "oneday_filter_search":
        filtered_results = search_onedays(list_of_onedays, search_word=values["oneday_search"])
        window["oneday_selection"].update(value=filtered_results[0], values=filtered_results)
        window["oneday_search"].update(value="")
        oneday = get_oneday_data(get_specific_oneday(list_of_onedays, filtered_results[0]))
        data = oneday["data"]
        i = 1
        score = 0
        question_object = data[i]
        window["oneday_title"].update(value=oneday["title"])
        window["difficulty"].update(value=oneday["difficulty_rating"])
        window["percent_correct"].update(value=str(oneday["overall_average"]) + "%")
        window["blurb_text"].update(value=oneday["blurb"])
        window["question"].update(value=question_object["_question"])
        window["answer"].update(value="*******")
        window["dropdown"].update(value=1, values=[x for x in data.keys()])
        window["next"].update(disabled=False)
        window["previous"].update(disabled=True)
        window["score"].update(value=score)
        window["question_percent_correct"].update(value="")
        window["num_of_money_questions_left"].update(value=num_of_money_questions_left)
        submitted_answers = {}

    if event == "oneday_selection":
        oneday = get_oneday_data(get_specific_oneday(list_of_onedays, values["oneday_selection"]))
        data = oneday["data"]
        i = 1
        score = 0
        question_object = data[i]
        window["oneday_title"].update(value=oneday["title"])
        window["difficulty"].update(value=oneday["difficulty_rating"])
        window["percent_correct"].update(value=str(oneday["overall_average"]) + "%")
        window["blurb_text"].update(value=oneday["blurb"])
        window["question"].update(value=question_object["_question"])
        window["answer"].update(value="*******")
        window["dropdown"].update(value=1, values=[x for x in data.keys()])
        window["next"].update(disabled=False)
        window["previous"].update(disabled=True)
        window["score"].update(value=score)
        window["question_percent_correct"].update(value="")
        window["num_of_money_questions_left"].update(value=num_of_money_questions_left)
        submitted_answers = {}

    if event in ("show/hide", "show_key"):
        if window.find_element_with_focus().Key in ("oneday_search", "answer_submission"):
            continue

        answer = decrypt_answer(question_object)

        if not values["answer_submission"]:
            confirm, _ = sg.Window(
                "Confirm",
                element_justification="c",
                layout=[
                    [sg.T("You have not submitted an answer.", font=("Arial", 14))],
                    [sg.T("Do you want to continue? (and forfeit your guess)", font=("Arial", 14))],
                    [
                        sg.Yes(s=12),
                        sg.No(s=12),
                    ],
                ],
                disable_close=False,
            ).read(close=True)

        if confirm == "Yes":
            window["answer_submission"].update(disabled=True)
            window["submit_answer_button"].update(disabled=True)
        else:
            continue

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
                    window["answer"].update(value="*******")
                else:
                    window["answer"].update(value="")
            except:
                continue

    if event in ["next", "previous", "dropdown", "next_key", "previous_key"]:
        if window.find_element_with_focus().Key in ("oneday_search", "answer_submission"):
            continue

        if event in ("next", "next_key"):
            if event == "next_key" and i == len(data.keys()):
                continue
            i += 1

        elif event in ("previous", "previous_key"):
            if event == "previous_key" and i == 1:
                continue
            i -= 1

        elif event == "dropdown":
            i = values["dropdown"]

        question_object = data[i]

        window["question"].update(value=question_object["_question"])
        window["answer"].update(value="*******")
        window["dropdown"].update(value=i)
        window["show/hide"].update(text="Show Answer")
        window["answer_submission"].update(value="")
        window["question_percent_correct"].update(
            value="Submit answer to see", font=("Arial Italic", 10)
        )
        window["answer_submission"].update(disabled=False)
        window["submit_answer_button"].update(disabled=False)

        if not question_object:
            if event in ("next", "next_key"):
                i -= 1
            elif event in ("previous", "previous_key"):
                i += 1
            elif event == "dropdown":
                i = values["dropdown"]
            continue

        if i == len(data.keys()):
            window["next"].update(disabled=True)
        else:
            window["next"].update(disabled=False)
        if i == 1:
            window["previous"].update(disabled=True)
        else:
            window["previous"].update(disabled=False)

        if submitted_answers.get(str(i)):
            prev_answer = submitted_answers.get(str(i))
            window["answer"].update(value=prev_answer.get("correct_answer"))
            window["answer_submission"].update(disabled=True)
            window["submit_answer_button"].update(disabled=True)
            window["money_check"].update(disabled=True, value=prev_answer.get("money_question"))
            window["question_percent_correct"].update(value=question_object["percent"], font=font)
            window["show/hide"].update(text="Hide Answer", disabled=True)
        else:
            if int(window["num_of_money_questions_left"].get()) == 0:
                window["money_check"].update(disabled=True, value=False)
            else:
                window["money_check"].update(disabled=False, value=False)

    if event in ("submit_answer_button", "answer_submissionanswer_sub_enter_button"):
        if not values["answer_submission"]:
            continue
        submitted_answer = values["answer_submission"].lower()
        answer = decrypt_answer(question_object)
        window["answer"].update(value=answer, font=("Arial", 16))
        window["show/hide"].update(text="Hide Answer")
        window["question_percent_correct"].update(value=question_object["percent"], font=font)

        answers = re.findall("([^\/,()]+)", answer)
        if len(answers) > 1:
            correct = [combined_correctness(submitted_answer, answer) for answer in answers]
        else:
            correct = [combined_correctness(submitted_answer, answer)]

        if any(correct):
            score += 15

            if values["money_check"]:
                wrong_percent = 100 - question_object["percent"]
                score += wrong_percent

        if values["money_check"]:
            num_of_money_questions_left -= 1
            window["num_of_money_questions_left"].update(value=num_of_money_questions_left)

        if values["money_check"] == 0:
            window["money_check"].update(disabled=True, value=False)

        window["money_check"].update(disabled=True, value=False)
        window["score"].update(value=score)
        window["submit_answer_button"].update(disabled=True)
        submitted_answers[question_object["question_num"]] = {
            "correct_answer": answer,
            "submitted_answer": submitted_answer,
            "money_question": values["money_check"],
            "correct": any(correct),
        }
        pprint(submitted_answers)
        window["question"].set_focus()

    if event == "difficulty_tooltip":
        webbrowser.open(window["difficulty_tooltip"].metadata)
