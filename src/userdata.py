import contextlib
import json
import os

from bs4 import BeautifulSoup as bs
from dotmap import DotMap

from src.constants import BASE_URL, BASE_USER_DATA_DIR, USER_DATA_DIR
from src.logged_in_tools import login

if not os.path.isdir(BASE_USER_DATA_DIR):
    os.mkdir(BASE_USER_DATA_DIR)

if not os.path.isdir(USER_DATA_DIR):
    os.mkdir(USER_DATA_DIR)


def load(username, profile_id=None, sess=None):
    if not sess:
        print("Sess not provided, creating new session...")
        sess = login()
    username = username.lower()
    filename = f"{USER_DATA_DIR}/{username}.json"
    if not os.path.isfile(filename):
        print(f"User {username} not found, downloading new data")
    else:
        with open(filename, "r") as fp:
            loaded_data = DotMap(json.load(fp))
            profile_id = loaded_data.profile_id
            username = loaded_data.username
    user_data = UserData(username=username, profile_id=profile_id, sess=sess)
    user_data._save()
    return user_data


class UserData(DotMap):
    def __init__(
        self,
        username,
        profile_id=None,
        sess=None,
        load=False,
        *args,
        **kwargs,
    ):

        def _get_category_metrics(self, latest_page):
            categories = latest_page.find(
                "table", {"class": "std sortable this_sea std_bord"}
            ).tbody.find_all("tr")
            category_metrics = DotMap()
            for category in categories:
                cells = category.find_all("td")
                cat_name = cells[0].text
                correct, total = cells[1].text.split("-")
                if not correct:
                    correct = 0
                if not total:
                    total = 0
                category_metrics[cat_name].correct = int(correct)
                category_metrics[cat_name].total = int(total)
                try:
                    category_metrics[cat_name].percent = int(correct) / int(total)
                except ZeroDivisionError:
                    category_metrics[cat_name].percent = 0.0
            return category_metrics

        def _get_opponents(self, latest_page):
            opponents = DotMap()
            op_table = latest_page.find(
                "table", {"summary": "Data table for LL results"}
            ).find_all("tr")[1:]
            for opp in op_table:
                opponents[opp.img.get("title")] = (
                    opp.find("a", {"class": "flag"}).get("href").split("?")[-1]
                )
            return opponents

        def _get_question_history(self, question_page):
            qhistory = question_page.find("div", {"class": "qhistory"})
            category_questions = qhistory.find_all("li")
            question_history = DotMap()
            for category in category_questions:
                category_name = category.find("span", {"class": "catname"}).text
                questions = category.find("table", {"class": "qh"}).find_all("tr")[1:]
                for question in questions:
                    q_id = (
                        question.find_all("td")[0]
                        .find_all("a")[2]
                        .get("href")
                        .split("?")[-1]
                    )
                    q_id = f'S{q_id.split("&")[0]}D{q_id.split("&")[1]}Q{q_id.split("&")[2]}'
                    correct = "green" in question.find_all("td")[2].img.get("src")
                    question_text = question.find_all("td")[1].text
                    question_history[q_id] = DotMap(
                        question_category=category_name,
                        correct=correct,
                        question=question_text,
                        url=BASE_URL
                        + question.find_all("td")[0].find_all("a")[2].get("href"),
                    )
            return question_history

        def _get_stats_data(self, stats_page):
            header = [
                val.text
                for val in stats_page.find("table", {"class": "std std_bord stats"})
                .find("thead")
                .find_all("td")
            ]
            total = [
                val.text
                for val in stats_page.find("table", {"class": "std std_bord stats"})
                .find("tbody")
                .find("tr", {"class": "grandtotal-row"})
                .find_all("td")
            ]
            current_season = [
                val.text
                for val in stats_page.find("table", {"class": "std std_bord stats"})
                .find("tbody")
                .find("tr", {"class": ""})
                .find_all("td")
            ]
            stats = DotMap()
            total_stats = DotMap()
            current_season_stats = DotMap()
            for i, header_value in enumerate(header):
                header_value = "Seas." if header_value == "Season" else header_value
                total_stats[header_value] = "Total" if i == 0 else total[i]

            for i, header_value in enumerate(header):
                header_value = "Seas." if header_value == "Season" else header_value
                current_season_stats[header_value] = current_season[i]
            stats.total = total_stats
            stats.current_season = current_season_stats
            return stats

        def _get_past_season_data(self, past_seasons_page):
            past_seasons = past_seasons_page.find(
                "div", {"class": "pastseasons"}
            ).find_all("div", {"class": "fl_latest"})
            past_seasons_dict = DotMap()
            for season in past_seasons:
                details = DotMap(
                    season=DotMap(
                        name=season.h2.text.split(" ")[0],
                        link=BASE_URL + season.h2.a.get("href"),
                    ),
                    rundle=DotMap(
                        name=season.h3.text.strip(),
                        link=f"{BASE_URL}/{season.h3.a.get('href')}",
                    ),
                    results=DotMap(
                        wins=0,
                        ties=0,
                        losses=0,
                    ),
                    matches=DotMap(),
                )
                rows = season.table.tbody.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    match_day = cells[0].text.replace(" ", "_").lower()
                    user_score, opp_score = cells[3].text.split("-")
                    user_points, user_correct = [
                        val.replace(")", "") for val in user_score.split("(")
                    ]
                    opp_points, opp_correct = [
                        val.replace(")", "") for val in opp_score.split("(")
                    ]
                    details.matches[match_day] = DotMap(
                        link=BASE_URL + cells[0].a.get("href"),
                        opponent=cells[1].img.get("title"),
                        result=(
                            "Win"
                            if cells[2].text == "W"
                            else "Tie" if cells[2].text == "T" else "Loss"
                        ),
                        score=cells[3].text,
                        detailed_link=BASE_URL + cells[3].a.get("href"),
                        score_breakdown=DotMap(
                            points=user_points,
                            correct=user_correct,
                            opp_points=opp_points,
                            opp_correct=opp_correct,
                        ),
                    )
                    if details.matches[match_day]["result"] == "Win":
                        details.results.wins += 1
                    elif details.matches[match_day]["result"] == "Tie":
                        details.results.ties += 1
                    else:
                        details.results.losses += 1

                past_seasons_dict[season.h2.text.split(" ")[0]] = details
            return past_seasons_dict

        super().__init__(*args, **kwargs)
        self.sess = sess
        self.username = username.lower()
        if profile_id:
            # print("profile_id given")
            self.profile_id = profile_id
            latest_page = bs(
                self.sess.get(
                    f"https://learnedleague.com/profiles.php?{self.profile_id}&1"
                ).content,
                "html.parser",
            )
        else:
            # print("no profile_id given")
            latest_page = bs(
                self.sess.get(
                    f"https://learnedleague.com/profiles.php?{self.username}&1"
                ).content,
                "html.parser",
            )
            self.profile_id = (
                latest_page.find("div", {"class": "flagdiv"})
                .a.get("href")
                .split("?")[-1]
            )
        if not self.profile_id.isnumeric():
            return None
        self.formatted_username = latest_page.h1.text

        self.link = f"https://learnedleague.com/profiles.php?{self.profile_id}"

        question_page = bs(self.sess.get(f"{self.link}&9").content, "html.parser")
        stats_page = bs(self.sess.get(f"{self.link}&2").content, "html.parser")
        past_seasons_page = bs(self.sess.get(f"{self.link}&7").content, "html.parser")

        self.opponents = _get_opponents(self, latest_page)
        self.category_metrics = _get_category_metrics(self, latest_page)
        self.question_history = _get_question_history(self, question_page)
        self.stats = _get_stats_data(self, stats_page)
        self.past_seasons = _get_past_season_data(self, past_seasons_page)

        self.ok = True
        self._save()

    def _save(self):
        if "question_history" not in self._map.keys():
            return

        with open(f"{USER_DATA_DIR}" + f"/{self.username}.json", "w") as fp:
            with contextlib.suppress(KeyError):
                del self.sess
            json.dump(self._map, fp, indent=4)

    def calc_hun(self, opponent, show=False):
        raw = 0
        total = 0
        if not self.profile_id.isnumeric():
            return None
        if not opponent.profile_id.isnumeric():
            return None

        for key, values in self.question_history.items():
            if key in opponent.question_history.keys():
                total += 1
                if values.get("correct") == opponent.question_history[key].get(
                    "correct"
                ):
                    raw += 1

        hun_score = raw / total if total else 0
        if "hun" not in self.keys():
            self.hun = DotMap()
        if "hun" not in opponent.keys():
            opponent.hun = DotMap()

        self.hun[opponent.username] = hun_score
        opponent.hun[self.username] = hun_score
        self._save()
        opponent._save()
        if show:
            print(
                f"Hun Score for {self.username} and {opponent.username}: {hun_score: 0.3f}"
            )
