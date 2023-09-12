import json
import os
import re

from bs4 import BeautifulSoup as bs
from bs4 import SoupStrainer as ss
from dotmap import DotMap

from logged_in_tools import login

BASE_URL = "https://www.learnedleague.com"
LOGIN_URL = BASE_URL + "/ucp.php?mode=login"
USER_QHIST = BASE_URL + "/profiles.php?%s&9"
USER_DATA_DIR = os.path.expanduser("~") + "/.LearnedLeague/user_data"
if not os.path.isdir(USER_DATA_DIR):
    os.mkdir(USER_DATA_DIR)


def load(username, sess=None):
    if not sess:
        print("Sess not provided, creating new session...")
        sess = login()
    username = username.lower()
    filename = USER_DATA_DIR + f"/{username}.json"
    if os.path.isfile(filename):
        with open(filename, "r") as fp:
            # print(f"Loaded user {username} from file")
            user_data = UserData(username=username, sess=sess, load=False)
            user_data._map.update(DotMap(json.load(fp)))
            user_data._update_data()
            return user_data
    else:
        return UserData(username=username, sess=sess, load=True)


class UserData(DotMap):
    def __init__(self, username=None, sess=None, load=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sess = sess
        self.username = username
        self.profile_id = self.sess.get(
            f"https://learnedleague.com/profiles.php?{self.username}"
        ).url.split("?")[-1]
        if load:
            self._get_full_data()
            self._save()

    def _save(self):
        with open(USER_DATA_DIR + f"/{self.username}.json", "w") as fp:
            try:
                del self.sess
            except KeyError:
                pass
            json.dump(self._map, fp, indent=4)

    def _get_full_data(self):
        question_page = bs(
            self.sess.get(
                f"https://learnedleague.com/profiles.php?{self.profile_id}&9"
            ).content,
            "html.parser",
        )

        all_categories = question_page.find_all("ul", {"class": "mktree"})
        question_history = DotMap()
        category_metrics = DotMap()
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
                q_id = (
                    f'S{q_id.split("&")[0]}D{q_id.split("&")[1]}Q{q_id.split("&")[2]}'
                )
                correct = "green" in question.find_all("td")[2].img.get("src")
                question_text = question.find_all("td")[1].text
                category_metrics[category_name].total += 1

                if correct:
                    category_metrics[category_name].correct += 1
                else:
                    category_metrics[category_name].correct += 0

                question_history[q_id] = DotMap(
                    question_category=category_name,
                    correct=correct,
                    question=question_text,
                    url=BASE_URL
                    + question.find_all("td")[0].find_all("a")[2].get("href"),
                )

            category_metrics[category_name].percent = (
                category_metrics[category_name].correct
                / category_metrics[category_name].total
            )
        self.category_metrics = category_metrics
        self.question_history = question_history
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

        latest_page = bs(
            self.sess.get(
                f"https://learnedleague.com/profiles.php?{self.profile_id}"
            ).content,
            "html.parser",
            parse_only=ss("table"),
        )

        self.opponents = [
            val.img.get("title")
            for val in latest_page.find(
                "table", {"summary": "Data table for LL results"}
            ).find_all("tr")[1:]
        ]

        self.hun = DotMap()

    def _update_data(self):
        profile_id_page = self.sess.get(
            f"https://learnedleague.com/profiles.php?{self.profile_id}"
        )
        previous_day = bs(
            profile_id_page.content, "html.parser", parse_only=ss("table")
        )

        rows = previous_day.find(
            "table", {"summary": "Data table for LL results"}
        ).find_all("tr")[1:]
        win_loss = DotMap()
        for row in rows:
            win_loss_text = row.find_all("td")[2].text
            if win_loss_text == "\xa0":
                continue

            current_day = (
                f'S{re.sub("&","D",row.find_all("td")[0].a.get("href").split("?")[-1])}'
            )
            win_loss[current_day] = win_loss_text
        _key_lookup = current_day + "Q1"
        if not any(
            [
                _key_lookup in self.question_history,
                win_loss[list(win_loss.keys())[-1]] == "F",
            ]
        ):
            print("Retrieved Latest Data")
            self._get_full_data()
            self._save()

    def calc_hun(self, opponent):
        raw = 0
        total = 0

        for key, values in self.question_history.items():
            if key in opponent.question_history.keys():
                total += 1
                if values.get("correct") == opponent.question_history[key].get(
                    "correct"
                ):
                    raw += 1

        if not total:
            hun_score = 0
        else:
            hun_score = raw / total
        if "hun" not in self.keys():
            self.hun = DotMap()
        if "hun" not in opponent.keys():
            opponent.hun = DotMap()

        self.hun[opponent.username] = hun_score
        opponent.hun[self.username] = hun_score
        self._save()
        opponent._save()
        # print(
        #     f"Hun Score for {self.username} and {opponent.username}: {hun_score: 0.3f}"
        # )
