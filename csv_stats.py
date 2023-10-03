import os

import matplotlib.pyplot as plt
import pandas as pd
from dotmap import DotMap

from logged_in_tools import login

ALL_DATA_BASE_URL = "https://www.learnedleague.com/lgwide.php?{}"


def stats_filter(field, value, operator="in", user_stats=DotMap()):
    if not set([True for u in user_stats.values() if field in u.toDict().keys()]):
        return user_stats
    if operator not in ["==", ">=", "<=", "<", ">", "in", "not in"]:
        print("Invalid Operator")
        return user_stats
    if operator == ">=":
        print("Greater than or Equal to operator")
        return DotMap({k: v for k, v in user_stats.items() if v[field] >= value})
    elif operator == ">":
        print("Greater than operator")
        return DotMap({k: v for k, v in user_stats.items() if v[field] > value})
    elif operator == "<=":
        print("Less than or Equal to operator")
        return DotMap({k: v for k, v in user_stats.items() if v[field] <= value})
    elif operator == "<":
        print("Less than operator")
        return DotMap({k: v for k, v in user_stats.items() if v[field] < value})
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


def calc_pct(user, field, value=None, mode="invquant"):
    if mode == "invquant":
        value = user_stats[user][field]
        return (df[field] < value).mean()
    elif mode == "quant":
        if 0 <= value <= 1:
            return df[field].quantile(value)
        else:
            raise ValueError("percentiles should all be in the interval [0, 1]")


def hist(field, bins=10):
    df[field].hist(bins=bins)
    plt.show()


season = 98

player_stats_url = ALL_DATA_BASE_URL.format(season)
file = f"LL{season}_Leaguewide.csv"
if not os.path.isfile(file):
    with open(file, "wb+") as out_file:
        sess = login()
        content = sess.get(player_stats_url, stream=True).content
        out_file.write(content)

raw = pd.read_csv(file, encoding="latin1")
raw.columns = [x.lower() for x in raw.columns]
user_stats = DotMap(raw.set_index("player").to_dict(orient="index"))
print("loaded file")

available_valid_fields = [
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


df = pd.DataFrame().from_dict(user_stats.toDict(), orient="index")

user = "FahmyG"
field = "tca"
value = user_stats[user][field]
std_deviation = df[field].std()
average = df[field].mean()

calc_pct(user, field, mode="invquant")
calc_pct(user, field, value=0.999999, mode="quant")

hist(field, 100)
df[field].max()
