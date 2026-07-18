import io
import json
import os
import time
import requests
from bs4 import BeautifulSoup as bs
from bs4 import SoupStrainer as ss
from PIL import Image

from .constants import BASE_URL
from src.db import load_all_data, save_question

# Create a persistent session with a standard User-Agent header
session = requests.Session()
session.headers.update({
    "User-Agent": "LearnedLeaguePracticeTool/2.0 (+https://github.com/georgefahmy/LL)"
})

def get_season_and_day():
    try:
        raw = session.get("https://www.learnedleague.com/allrundles.php").content
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
        md_table = (
            bs(
                raw,
                "html.parser",
                parse_only=ss("table"),
            )
            .find_all("table", {"class": "MDTable"})[0]
            .find_all("tr")
        )

        current_day_table = [
            i - 1 for i, row in enumerate(md_table) if "Active" in row.text
        ]

        try:
            current_day = int(day_header.h3.text.split()[-1])
            current_season = int(season_header.text.split(":")[0].split("LL")[-1])
            return (current_season, current_day)
        except Exception:
            try:
                current_day = current_day_table[0]
                current_season = int(season_header.text.split(":")[0].split("LL")[-1])
                return (current_season, current_day)
            except Exception:
                return (108, 0)
    except Exception:
        return (108, 0)


def get_new_data(season_number):
    """Get the latest data from the season number provided, skipping already cached days

    Args:
        season_number (int): Season number

    Returns:
        all_data: Data structure of all questions and answers (and metrics)
    """
    all_data = load_all_data()

    url = f"{BASE_URL}/match.php?{str(season_number)}"
    for i in range(1, 26):
        # Optimisation: Check if this match day is already cached (all 6 questions present)
        day_cached = True
        for q_num in range(1, 7):
            q_code = f"S{season_number}D{str(i).zfill(2)}Q{q_num}"
            if q_code not in all_data:
                day_cached = False
                break
        
        if day_cached:
            continue

        # Add a small politeness delay between requests
        time.sleep(0.100)

        question_url = f"{url}&{str(i)}"
        try:
            resp = session.get(question_url)
            if not resp.ok:
                continue
            page = bs(resp.content, "html.parser")
        except Exception as e:
            print(f"Network error fetching match day {i}: {e}")
            continue

        if not page.find_all("tr"):
            continue

        try:
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
                question_num_code = f"D{str(i).zfill(2)}Q{str(j + 1)}"
                combined_season_num_code = f"S{season_number}{question_num_code}"
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

                question_data = {
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
                
                # Save to database
                save_question(combined_season_num_code, question_data)
                
                # Keep in memory to return
                all_data[combined_season_num_code] = question_data
        except Exception as e:
            print(f"Error parsing match day {i}: {e}")
            continue

    return all_data


def get_image_data(url):
    try:
        img_data = session.get(url).content
        pil_image = Image.open(io.BytesIO(img_data))
        png_bio = io.BytesIO()
        pil_image.save(png_bio, format="PNG")
        return png_bio.getvalue()
    except Exception as e:
        print(f"Error downloading image: {e}")
        return b""
