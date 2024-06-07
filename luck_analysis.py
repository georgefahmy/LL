import argparse
import base64
import os

# import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import PySimpleGUI as sg
import requests

# import seaborn as sns
from bs4 import BeautifulSoup as bs
from scipy.stats import rankdata
from statsmodels.formula.api import ols

from src.constants import ALL_DATA_BASE_URL, BASE_URL
from src.logged_in_tools import login

# from src.userdata import load


def get_current_season(season=None):
    if season:
        url = BASE_URL + f"/allrundles.php?{season}"
    else:
        url = BASE_URL + "/allrundles.php"
    page = bs(requests.get(url).content, "html.parser")
    current_season = int(page.find("h1").text.split(":")[0].replace("LL", ""))
    matchday_table = page.find("table", {"class": "MDTable"}).find_all("tr")[1:-1]
    if (matchday_table[-1].find_all("td")[-1].text).isnumeric():
        current_matchday = int(
            matchday_table[-1].find_all("td")[0].text.replace("Match Day ", "").lower()
        )
    else:
        current_matchday = (
            int(
                (
                    matchday_table[
                        [i for i, row in enumerate(matchday_table) if not row.a][0]
                    ]
                    .find("td")
                    .text[10:]
                )
            )
            - 1
        )
    return (current_season, current_matchday)


def get_leaguewide_data(season=None, matchday=None):
    if not season or not matchday:
        current_season, current_matchday = get_current_season(season)
    if not season:
        season = current_season
    if not matchday:
        matchday = current_matchday
    player_stats_url = ALL_DATA_BASE_URL.format(season)
    file = (
        os.path.expanduser("~")
        + "/.LearnedLeague/"
        + f"LL{season}_Leaguewide_MD_{matchday}.csv"
    )
    if not os.path.isfile(file):
        with open(file, "wb+") as out_file:
            sess = login()
            content = sess.get(player_stats_url, stream=True).content
            out_file.write(content)
    try:
        data = (
            pd.read_csv(file, encoding="latin1", low_memory=False)
            .set_index("Player", drop=False)
            .rename(
                columns={
                    "Wins": "W",
                    "Losses": "L",
                    "Ties": "T",
                    "Pts": "PTS",
                    "Rundle Rank": "Rank",
                }
            )
        )
    except pd.errors.EmptyDataError:
        print("Empty Data")
        with open(file, "wb+") as out_file:
            sess = login()
            content = sess.get(player_stats_url, stream=True).content
            out_file.write(content)
        data = (
            pd.read_csv(file, encoding="latin1", low_memory=False)
            .set_index("Player", drop=False)
            .rename(
                columns={
                    "Wins": "W",
                    "Losses": "L",
                    "Ties": "T",
                    "Pts": "PTS",
                    "Rundle Rank": "Rank",
                }
            )
        )

    data = data.replace([np.inf, -np.inf, np.nan, "--"], 0)
    for col in data.columns:
        data[col] = pd.to_numeric(data[col], errors="ignore")
    return data


def calc_luck(data):
    count_stats = ["Rundle", "Player"]
    sum_stats = ["Rundle", "FL", "FW", "TCA", "QPlayed"]
    data["Matches"] = data["W"] + data["L"] + data["T"]
    data["Played"] = data["Matches"] - data["FL"]
    data["FPct"] = data["FL"] / data["Matches"]
    data["QPlayed"] = 6 * data["Played"]
    count = (
        data[count_stats]
        .groupby("Rundle", as_index=False)
        .count()
        .rename(columns={"Player": "Player_count"})
    )
    sum_data = (
        data[sum_stats]
        .groupby("Rundle", as_index=False)
        .sum()
        .rename(
            columns={"FL": "rFL", "FW": "rFW", "TCA": "rTCA", "QPlayed": "rQPlayed"}
        )
    )
    data = data.merge(count)
    data = data.merge(sum_data)
    data["Exp_FW"] = (
        ((data["rFL"] - data["FL"]) / (data["Player_count"] - 1)) / data["Matches"]
    ) * data["Played"]
    data["Exp_TMP"] = data["TMP"] * (data["Played"] - data["Exp_FW"]) / data["Played"]
    data["rQPCT"] = (data["rTCA"] - data["TCA"]) / (data["rQPlayed"] - data["QPlayed"])
    data["Exp_CAA"] = data["rQPCT"] * 6 * (data["Played"] - data["Exp_FW"])
    data["Exp_MPA"] = (
        data["PCAA"] * data["rQPCT"] * 6 * (data["Played"] - data["Exp_FW"])
    )
    data["SOS"] = data["CAA"] / (6 * (data["Matches"] - data["FW"]) * data["rQPCT"])
    data["PWP"] = 1 / (1 + (data["Exp_MPA"] / data["Exp_TMP"]) ** 1.93)
    data["Exp_PTS"] = (
        (2 * data["PWP"] * (data["Played"] - data["Exp_FW"]))
        + (2 * data["Exp_FW"])
        - data["FL"]
    )
    data["Exp_Rank"] = (
        pd.to_numeric(
            data.groupby("Rundle")["Exp_PTS"].rank(method="dense", ascending=False),
            errors="coerce",
        )
        .replace(np.nan, 0)
        .astype(int)
    )
    data["Luck"] = data["PTS"] - data["Exp_PTS"]
    data["Luck_Rank"] = (data["Rank"] - data["Exp_Rank"]).astype(int)
    data["LuckPctile"] = (
        (data.groupby("Rundle")["Luck"].rank() - 1) / data["Player_count"] * 100
    )
    data.set_index("Player", inplace=True, drop=False)
    return data


def norm_vars(data, normalize_vars):
    for var in normalize_vars:
        norm_var = f"norm_{var}"
        data[norm_var] = data.groupby("Rundle")[var].transform(
            lambda x: (x - x.mean()) / x.std()
        )
    return data


def stats_model_luck(data, formula):
    normalize_vars = ["OE", "DE", "QPct", "CAA", "FL"]
    data["Level"] = data["Rundle"].str[0]
    data["Matches"] = data["W"] + data["L"] + data["T"]
    data["Played"] = data["Matches"] - data["FL"]
    data["Player_count"] = data.groupby("Rundle")["Rundle"].transform("count")
    data["SOS"] = data["CAA"] / (
        6
        * (data["Matches"] - data["FW"])
        * data.groupby("Rundle")["QPct"].transform("mean")
    )
    data = norm_vars(data, normalize_vars)
    model = ols(formula, data=data).fit()
    data["Exp_PTS"] = model.predict(data)
    data = data.replace([np.inf, -np.inf, np.nan, "--"], 0)
    data["Exp_Rank"] = (
        data.groupby("Rundle")["Exp_PTS"]
        .rank(ascending=False, method="dense")
        .astype(int)
    )
    data["Luck"] = data["PTS"] - data["Exp_PTS"]
    data["Luck_Rank"] = (data["Exp_Rank"] - data["Rank"]).astype(int)
    data["Luck_Rank_adj"] = (data["Luck_Rank"] / data["Player_count"]) * data[
        "Player_count"
    ].mean()
    data["LuckPctile"] = (
        rankdata(data["Luck_Rank_adj"], method="max") / len(data) * 100
    ).round(2)
    data.sort_values(by="LuckPctile", ascending=False, inplace=True)
    return data, model


def display_data(data, usernames, fields, rundle=False):
    try:
        if rundle:
            rundle = data.loc[usernames]["Rundle"]
            if "Rundle" not in fields:
                fields.append("Rundle")
            luck_data = (data[data["Rundle"].isin(rundle)][fields]).sort_values(
                by=["Rundle", "LuckPctile"], ascending=[True, False]
            )
        else:
            luck_data = (data.loc[usernames][fields]).sort_values(
                by=["LuckPctile"], ascending=False
            )
        headers = luck_data.columns.tolist()
        values = luck_data.round(3).values.tolist()
        ind = luck_data.index.get_loc(
            luck_data[
                luck_data["Player"].str.len() == luck_data["Player"].str.len().max()
            ].values[0][0]
        )
        calc_widths = list(map(lambda x: len(str(x)) + 1, values[ind]))
        col_widths = [
            max(calc_widths[i], len(headers[i]) + 2) for i in range(0, len(headers))
        ]
        sg.theme("Reddit")
        sg.set_options(font=("Arial", 16))
        layout = [
            [
                sg.Table(
                    size=(None, len(values)),
                    values=values,
                    headings=headers,
                    auto_size_columns=False,
                    col_widths=col_widths,
                    expand_x=True,
                    expand_y=True,
                    alternating_row_color="light gray",
                )
            ]
        ]
        window = sg.Window("Luck Table", layout, resizable=True)
        return luck_data, window
    except Exception as e:
        print(e)


def get_args():
    parser = argparse.ArgumentParser(prog="luck_analysis.py")
    parser.add_argument(
        "-s",
        "--season",
        help="Enter the Season Number you want to get stats data for. (ex. -s 100) Default == Latest",
        default=None,
        type=int,
    )
    parser.add_argument(
        "-m",
        "--matchday",
        help="Enter the Matchday Number you want to get stats data for. (ex. -m 8) Default == Latest",
        default=None,
        type=int,
    )
    parser.add_argument(
        "-u",
        "--usernames",
        help="Enter the username(s) that you want to get information on. (ex. -u FrielP)",
        nargs="+",
        default=[
            "FahmyG",
            "FahmyB",
            "FahmyBoldsoul",
            "LefortS",
            "HarperD",
            "HulseM",
            "HammondM",
            "PantaloneG",
            "JenkinsK",
            "MooneyJ2",
        ],
    )
    parser.add_argument(
        "-f",
        "--fields",
        help="""Enter any optional data fields that you want to display in the output table.
        Available Fields:
        'MPD', 'TMP', 'TCA', 'PCA', 'UfPE', 'OE', 'QPct', 'TPA', 'CAA', 'PCAA', 'UfPA',
        'DE', 'NUfP', 'QPO', 'QPD', 'OPD', 'FW', 'FL', '3PT', 'MCW', 'Rank',
        'League', 'Branch', 'Level', 'Matches', 'Played', 'Player_count',
        'norm_OE', 'norm_DE', 'norm_QPct', 'norm_CAA', 'norm_3PT', 'Luck_Rank_adj'""",
        nargs="+",
        action="extend",
        default=[
            "Player",
            "W",
            "L",
            "T",
            "QPct",
            "PTS",
            "Exp_PTS",
            "Luck",
            "LuckPctile",
            "Rank",
            "Exp_Rank",
            "norm_CAA",
            "norm_QPct",
            "SOS",
        ],
    )
    parser.add_argument(
        "-r",
        "--rundle",
        help="Default: False. Set flag to display rundle information for specified Usernames",
        action="store_true",
        default=False,
    )
    parser.add_argument(
        "-F",
        "--formula",
        help="Advanced Usage for adding variables to the model. Default: Played, FL*norm_OE, FL*norm_QPct, norm_DE",
        default=[
            "0",
            "Played",
            "norm_OE*FL",
            "norm_QPct*FL",
            "norm_DE",
        ],
        action="extend",
        nargs="+",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = get_args()
    pd.options.display.float_format = "{:,.3f}".format
    icon_file = os.getcwd() + "/resources/ll_app_logo.png"
    sg.theme("Reddit")
    sg.set_options(icon=base64.b64encode(open(str(icon_file), "rb").read()))

    season = args.season
    matchday = args.matchday

    formula = "PTS ~ " + " + ".join(args.formula)

    data, model = stats_model_luck(
        get_leaguewide_data(season=args.season, matchday=args.matchday), formula=formula
    )
    print(model.summary())

    # data = calc_luck(get_leaguewide_data(season))
    if not args.rundle:
        args.fields.append("Rundle")

    luck_data, window = display_data(
        data, usernames=args.usernames, fields=args.fields, rundle=args.rundle
    )
    print(data["Luck"].sum())
    window.read()
