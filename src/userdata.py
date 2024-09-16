import contextlib
import json
import os
import re

from bs4 import BeautifulSoup as bs
from bs4 import SoupStrainer as ss
from dotmap import DotMap

from .constants import BASE_URL, BASE_USER_DATA_DIR, USER_DATA_DIR
from .logged_in_tools import login

if not os.path.isdir(BASE_USER_DATA_DIR):
    os.mkdir(BASE_USER_DATA_DIR)

if not os.path.isdir(USER_DATA_DIR):
    os.mkdir(USER_DATA_DIR)


def load(username, sess=None):
    if not sess:
        print("Sess not provided, creating new session...")
        sess = login()
    username = username.lower()
    filename = f"{USER_DATA_DIR}/{username}.json"
    if os.path.isfile(filename):
        with open(filename, "r") as fp:
            # print(f"Loaded user {username} from file")
            user_data = UserData(username=username, sess=sess, load=False)
            user_data._map.update(DotMap(json.load(fp)))
            user_data._update_data()
            return user_data
    else:
        print(f"User {username} not found, downloading new data")
        return UserData(username=username, sess=sess, load=True)


class UserData(DotMap):

    def __init__(
        self,
        username=None,
        profile_id=None,
        sess=None,
        load=False,
        other_folder=None,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.sess = sess
        self.username = username.lower() if username else None
        self.formatted_username = (
            self.format_username(self, self.username) if self.username else None
        )
        if not profile_id:
            self.profile_id = self.sess.get(
                f"https://learnedleague.com/profiles.php?{self.username}"
            ).url.split("?")[-1]
        else:
            self.profile_id = profile_id
            if not self.username:
                try:
                    self.username = (
                        bs(
                            self.sess.get(
                                f"https://learnedleague.com/profiles.php?{self.profile_id}&1"
                            ).content,
                            "html.parser",
                        )
                        .find("h1", {"class": "namecss"})
                        .text
                    ).lower()
                except Exception:
                    return None
                self.formatted_username = (
                    self.format_username(self, self.username) if self.username else None
                )

        self.link = f"https://learnedleague.com/profiles.php?{self.profile_id}"
        if not self.profile_id.isnumeric():
            return None
        if load:
            self._get_full_data()
            self._save(other_folder)

    def _save(self, other_folder=None):
        folder = other_folder or ""
        if "question_history" not in self._map.keys():
            return

        with open(f"{USER_DATA_DIR}/{folder}" + f"/{self.username}.json", "w") as fp:
            with contextlib.suppress(KeyError):
                del self.sess
            json.dump(self._map, fp, indent=4)

    def _get_full_data(self):
        def _get_question_history():
            question_history = DotMap()
            for category in all_categories:
                category_name = re.sub(
                    " ", "_", category.find("span", {"class": "catname"}).text
                )
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

        def _get_category_metrics():
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

        question_page = bs(
            self.sess.get(
                f"https://learnedleague.com/profiles.php?{self.profile_id}&9"
            ).content,
            "html.parser",
        )

        all_categories = question_page.find_all("ul", {"class": "mktree"})
        if not all_categories:
            return None

        self.question_history = _get_question_history()
        self.ok = True

        stats_page = bs(
            self.sess.get(
                f"https://learnedleague.com/profiles.php?{self.profile_id}&2"
            ).content,
            "html.parser",
        )

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
        self.stats = stats

        category_metrics = DotMap()

        latest_page = bs(
            self.sess.get(
                f"https://learnedleague.com/profiles.php?{self.profile_id}"
            ).content,
            "html.parser",
            parse_only=ss("table"),
        )
        categories = latest_page.find(
            "table", {"class": "std sortable this_sea std_bord"}
        ).tbody.find_all("tr")

        self.category_metrics = _get_category_metrics()

        self.opponents = [
            val.img.get("title")
            for val in latest_page.find(
                "table", {"summary": "Data table for LL results"}
            ).find_all("tr")[1:]
        ]
        past_seasons = (
            bs(
                self.sess.get(
                    f"https://learnedleague.com/profiles.php?{self.profile_id}&7"
                ).content,
                "html.parser",
            )
            .find("div", {"class": "pastseasons"})
            .find_all("div", {"class": "fl_latest"})
        )
        self.past_seasons = DotMap()
        for season in past_seasons:
            details = DotMap()
            details["season"]["name"] = season.h2.text.split(" ")[0]
            details["season"]["link"] = BASE_URL + season.h2.a.get("href")
            details["rundle"]["name"] = season.h3.text.strip()
            details["rundle"]["link"] = f"{BASE_URL}/" + season.h3.a.get("href")
            details["matches"] = DotMap()
            details["results"]["wins"] = 0
            details["results"]["ties"] = 0
            details["results"]["losses"] = 0
            rows = season.table.tbody.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                match_day = cells[0].text.replace(" ", "_").lower()
                match_day_link = BASE_URL + cells[0].a.get("href")
                details["matches"][match_day] = DotMap()
                details["matches"][match_day]["link"] = match_day_link
                details["matches"][match_day]["opponent"] = cells[1].img.get("title")
                details["matches"][match_day]["result"] = (
                    "Win"
                    if cells[2].text == "W"
                    else "Tie" if cells[2].text == "T" else "Loss"
                )
                if details["matches"][match_day]["result"] == "Win":
                    details["results"]["wins"] += 1
                elif details["matches"][match_day]["result"] == "Tie":
                    details["results"]["ties"] += 1
                else:
                    details["results"]["losses"] += 1
                user_score, opp_score = cells[3].text.split("-")
                user_points, user_correct = [
                    val.replace(")", "") for val in user_score.split("(")
                ]
                opp_points, opp_correct = [
                    val.replace(")", "") for val in opp_score.split("(")
                ]
                details["matches"][match_day]["score"] = cells[3].text
                details["matches"][match_day]["detailed_link"] = BASE_URL + cells[
                    3
                ].a.get("href")
                details["matches"][match_day]["score_breakdown"]["points"] = user_points
                details["matches"][match_day]["score_breakdown"][
                    "correct"
                ] = user_correct

                details["matches"][match_day]["score_breakdown"][
                    "opp_points"
                ] = opp_points
                details["matches"][match_day]["score_breakdown"][
                    "opp_correct"
                ] = opp_correct

            self.past_seasons[season.h2.text.split(" ")[0]] = details

        self.hun = self.hun if self.get("hun") else DotMap()

    def _update_data(self):
        profile_id_page = self.sess.get(
            f"https://learnedleague.com/profiles.php?{self.profile_id}"
        )
        previous_day = bs(
            profile_id_page.content, "html.parser", parse_only=ss("table")
        )
        data_table = previous_day.find(
            "table", {"summary": "Data table for LL results"}
        )
        if not data_table:
            print("Data table issue, loading full data")
            self._extracted_from__update_data()
            return

        rows = data_table.find_all("tr")[1:]
        win_loss = DotMap()
        for row in rows:
            win_loss_text = row.find_all("td")[2].text
            if win_loss_text == "\xa0":
                continue

            current_day = f'S{re.sub("&", "D", row.find_all("td")[0].a.get("href").split("?")[-1])}'
            win_loss[current_day] = win_loss_text

        if not win_loss:
            self._extracted_from__update_data()
            return

        _key_lookup = f"{current_day}Q1"

        if not any(
            [
                _key_lookup in self.question_history,
                win_loss[list(win_loss.keys())[-1]] == "F",
            ]
        ):
            print(f"Retrieved Latest Data for {self.username}")
            self._extracted_from__update_data()

    def _extracted_from__update_data(self):
        self.formatted_username = self.format_username(self, self.username)
        self._get_full_data()
        self._save()

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

    @staticmethod
    def format_username(self, username):
        return bs(
            self.sess.get(
                f"https://learnedleague.com/profiles.php?{self.username}"
            ).content,
            "html.parser",
        ).h1.text
