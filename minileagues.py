import requests
import datetime
import webbrowser
import wikipedia
import unicodedata
import base64
import os
import PySimpleGUI as sg
import re
import json

from bs4 import BeautifulSoup as bs
from random import choice
from pprint import pprint
from answer_correctness import combined_correctness
from PyDictionary import PyDictionary
from time import sleep
from collections import OrderedDict


BASE_URL = "https://www.learnedleague.com"
WD = os.getcwd()



def get_full_list_of_mini_leagues():
    data = {
        info.find("td", {"class": "std-left"}).text: {
            "title": info.find("td", {"class": "std-left"}).text,
            "url": BASE_URL + info.find("td", {"class": "std-left"}).a.get("href"),
            "date": info.find("td", {"class": "std-midleft"}).text,
            "number_of_players": info.find("td", {"class": "std-mid"}).text
        }
        for info in bs(requests.get(BASE_URL + "/mini/").content, "html.parser")
            .find("table", {"class": "std min"})
            .find("tbody").find_all("tr")[3:-1]
            if info.find("td", {"class": "std-left"})
    }
    return data


def search_minileagues(data, search_word=None):
    if not search_word:
        return list(data.keys())
    else:
        return [val for val in list(data.keys()) if search_word.lower() in val.lower()]


def get_specific_minileague(data, mini_league_key):
    return data.get(mini_league_key)


def get_mini_data(specific_mini):
    page = bs(requests.get(specific_mini["url"]).content, "lxml")
    matches = {re.split("(Match[^M]*|Champ[C]+)",match.text)[0]:BASE_URL + match.a.get("href")
        for match in page.find("table", {"class": "mtch"}).find_all("tr") if match.text
        }
    for key in list(matches.keys()):
        if "12" in matches[key]:
            del matches[key]
    mini_details = {"raw_matches":matches}
    mini_details["match_days"] = OrderedDict()

    for i, match in enumerate(mini_details["raw_matches"].values()):
        mini_details["match_days"][str(i+1)] = {}
        match_page = bs(requests.get(match).content, "lxml")
        for q, a in zip(match_page.find_all(True, {"class":["ind-Q20","a-red"]})[0::2], match_page.find_all(True, {"class":["ind-Q20","a-red"]})[1::2]):
            mini_details["match_days"][str(i+1)][q.text.strip().split("-")[0].strip().split(".")[0]] = {"question": "-".join(q.text.strip().split("-")[1:]).strip(), "answer":a.text.strip()}
        for j in range(1, 7):
            mini_details["match_days"][str(i+1)][f"Q{j}"]["%_correct"] = [v.text.strip() for v in match_page.find("table", {"class":"std sortable"}).find("tfoot").find_all("td", {"class":"ind-Q3-t"})][2:-1][j-1]

    specific_mini["data"] = mini_details
    total = [int(specific_mini.get("data").get("match_days").get(day).get(f"Q{i}").get("%_correct")) for i in range(1, 7) for day in specific_mini.get("data").get("match_days")]
    specific_mini["overall_correct"] = round(sum(total)/len(total),2)
    return specific_mini

data = get_full_list_of_mini_leagues()
filtered_results = search_minileagues(data)
specific_mini = get_specific_minileague(data, choice(filtered_results))
specific_mini = get_mini_data(specific_mini)

specific_mini.get("data").get("match_days")
