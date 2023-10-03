# import matplotlib.pyplot as plt
import pandas as pd
from dotmap import DotMap

from logged_in_tools import login

ALL_DATA_BASE_URL = "https://www.learnedleague.com/lgwide.php?{}"
season = 98

player_stats_url = ALL_DATA_BASE_URL.format(season)
file = f"LL{season}_Leaguewide.csv"
with open(file, "wb+") as out_file:
    sess = login()
    content = sess.get(player_stats_url, stream=True).content
    out_file.write(content)

raw = pd.read_csv(file, encoding="latin-1")
raw.columns = [x.lower() for x in raw.columns]
user_stats = DotMap(raw.set_index("player").to_dict(orient="index"))

field = "rundle"
value = "Orange"


valid_fields = [
    "wins",
    "losses",
    "ties",
    "pts",
    "mpd",
    "tmp",
    "tca",
    "pca",
    "ufpe",
    "oe",
    "qpct",
    "tpa",
    "caa",
    "pcaa",
    "ufpa",
    "de",
    "nufp",
    "qpo",
    "qpd",
    "opd",
    "fw",
    "fl",
    "3pt",
    "mcw",
    "rundle",
    "rundle rank",
    "league",
    "branch",
]


def stats_filter(field, value, operator="in", user_stats=user_stats):
    if not set([True for u in user_stats.values() if field in u.toDict().keys()]):
        return user_stats
    valid_operators = ["==", ">=", "<=", "in", "not in"]
    if operator not in valid_operators:
        print("Invalid Operator")
        return user_stats
    if operator == ">=":
        print("Greater than operator")
        return DotMap({k: v for k, v in user_stats.items() if v[field] >= value})
    elif operator == "<=":
        print("Less than operator")
        return DotMap({k: v for k, v in user_stats.items() if v[field] <= value})
    elif operator == "==":
        print("Equals operator")
        return DotMap({k: v for k, v in user_stats.items() if v[field] == value})
    elif operator == "in":
        print("In operator")
        return DotMap({k: v for k, v in user_stats.items() if value in v[field]})
    elif operator == "not in":
        print("Not In operator")
        return DotMap({k: v for k, v in user_stats.items() if value not in v[field]})
    else:
        return user_stats
