import os
import pickle
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
CATEGORIES = [
    "AMER_HIST",
    "ART",
    "BUS/ECON",
    "CLASS_MUSIC",
    "CURR_EVENTS",
    "FILM",
    "FOOD/DRINK",
    "GAMES/SPORT",
    "GEOGRAPHY",
    "LANGUAGE",
    "LIFESTYLE",
    "LITERATURE",
    "MATH",
    "POP_MUSIC",
    "SCIENCE",
    "TELEVISION",
    "THEATRE",
    "WORLD_HIST",
]
STATS_DEFINITION = {
    "Seas.": "Season",
    "W": "Wins",
    "L": "Losses",
    "T": "Ties",
    "PTS": "Points (in standings) - This determines the order of the standings. Two points for a win, one for a tie, -1 for a forfeit loss",
    "TMP": "Total Match Points - Sum of points scored in all matches",
    "TPA": "Total Points Allowed",
    "MPD": "Match Points Differential - The difference between Match Points scored and Match Points allowed (TMP-TPA)",
    "TCA": "Total Correct Answers",
    "CAA": "Correct Answers Against - Total number of questions answered correctly by one's opponents in all matches",
    "PCAA": "Points Per Correct Answer Against - The average value allowed per correct answer of one's opponent",
    "UfPA": """Unforced Points Allowed -
The total number of points allowed above that which would have been allowed with perfect defense
(i.e. if one's opponent answered four correct and scored 7, he gave up 3 UfPA [7-4]).
Perfect defensive points - (1: 0, 2: 1, 3: 2, 4: 4, 5: 6, 6: 9)""",
    "DE": "Defensive Efficiency -\nThe total number of UfPA you could have but did not allow\ndivided by the total number you could have allowed. The higher the number the better",
    "FW": "Forfeit Wins",
    "FL": "Forfeit Losses",
    "3PT": "3-Pointers",
    "MCW": "Most Common Wrong Answers -\nNumber of answers submitted\nwhich were the Most Common Wrong Answer for its question",
    "QPct": "Percent of correct answers",
    "Rank": "Overall Rank in the Season",
}


class UserData(DotMap):
    def __init__(self, sess=None, username=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not sess:
            self.sess = login()
        else:
            self.sess = sess
        self.username = username
        self.profile_id = self.sess.get(
            f"https://learnedleague.com/profiles.php?{self.username}"
        ).url.split("?")[-1]

    @classmethod
    def load(cls, username):
        filename = USER_DATA_DIR + f"/{username}.pkl"
        if os.path.isfile(filename):
            with open(filename, "rb") as fp:
                print(f"Loaded user {username} from file")
                user_data = pickle.load(fp)
                user_data._update_data()
                return user_data
        else:
            user_data = cls(username=username.lower())
            user_data._get_full_data()
            user_data._save()
            return user_data

    def _save(self):
        with open(USER_DATA_DIR + f"/{self.username}.pkl", "wb") as fp:
            pickle.dump(self, fp)

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
                if values.correct == opponent.question_history[key].correct:
                    raw += 1

        if not total:
            hun_score = 0
        else:
            hun_score = raw / total

        self.hun[opponent.username] = hun_score
        opponent.hun[self.username] = hun_score
        self._save()
        opponent._save()
        # print(
        #     f"Hun Score for {self.username} and {opponent.username}: {hun_score: 0.3f}"
        # )
