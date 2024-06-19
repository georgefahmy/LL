import io
import json
import os

import requests
from bs4 import BeautifulSoup as bs
from bs4 import SoupStrainer as ss
from PIL import Image

from .constants import BASE_URL


def get_season_and_day():
    raw = requests.get("https://www.learnedleague.com/allrundles.php").content
    day_header = bs(
        raw,
        "html.parser",
        parse_only=ss("h3"),
    )
    season_header = bs(
        raw,
        "html.parser",
        parse_only=ss("h1"),
    )

    try:
        current_day = int(day_header.h3.text.split()[-1])
        current_season = int(season_header.text.split(":")[0].split("LL")[-1])
        return (current_season, current_day)
    except:
        return (101, 0)


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


def get_image_data(url):
    img_data = requests.get(url).content
    pil_image = Image.open(io.BytesIO(img_data))
    png_bio = io.BytesIO()
    pil_image.save(png_bio, format="PNG")
    return png_bio.getvalue()
